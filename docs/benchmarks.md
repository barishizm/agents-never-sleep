# ANS Benchmarks — methodology, not claimed results

> **30-second version.** This is **how to measure** the autonomy of an unattended run — not a table of
> results we are claiming. ANS's value is "the run made real, reversible progress without a human", and
> this doc defines the metrics that capture that (uninterrupted runtime, completed-backlog ratio, recovery
> success, retry efficiency, interruption reduction, parked ratio, human dependency, and a composite
> autonomy index), the controlled backlog to measure them on, how each metric is read from the durable
> state, what environment facts a result must ship with, and — honestly — what each metric does and does
> **not** prove. Numbers appear only in a clearly-dated appendix *when actually run*. See
> [recovery](recovery.md), [scheduling](scheduling.md), [state machine](state-machine.md), [glossary](glossary.md).

> **Honesty bar (non-negotiable).** The metrics below are **not yet measured — no results exist.**
> Nothing in this document is a benchmark *result*. No fabricated comparison, no invented figure, no
> "X% faster than". When a metric is run for real, it goes in a dated, reproducible appendix with the
> exact setup — never inline as a bare number. Any number you do see below is a *design parameter* of
> the methodology (a backlog size, a threshold), never a measured outcome.

## Why an "autonomy" benchmark, not a "quality" benchmark

ANS does not write code and does not judge whether code is correct — so it would be dishonest to benchmark
it on code quality or bug-catching. What ANS *does* is govern an unattended run: keep it going, keep it
reversible, recover from failure, and defer (not guess) the high-stakes unknowns. The right thing to
measure is therefore **autonomy** — how much useful, reversible progress a run makes without a human in
the loop — not correctness, which belongs to the deterministic gate and the delegated verification layer.

## Where the measurements come from

Every metric below is read from artifacts the harness already writes durably — nothing requires
instrumenting the run after the fact:

- **`.unattended/state/<ticket>.json`** — one `TicketOutcome` per ticket (`state.py`): `state`, `why`,
  `category`, `attempts`, `human_action_required`, `exact_blocker`, `dependents_quarantined`,
  `contamination_scope`, `review_coverage`, `created_at`/`updated_at` (epoch seconds).
- **`.unattended/state/ledger.json`** — durable attempt counts per ticket and recorded failure
  signatures (`ledger.py`).
- **The run report** (`report.py`, default `night-report.md` per `report.local_path`) — the per-state
  sections, the "N/M DONE clean" summary line, and per-ticket `next action` / `category` lines.
- **The launcher log** (`.unattended/logs/ans-*.log`) and, for hang/restart events, the watchdog's
  output within it.
- **`git log` on the run branch** — one snapshot/commit trail per ticket; the reversibility evidence.

## The metrics — precise definitions

### 1. Uninterrupted runtime

**Definition.** Wall-clock time during which the run advanced with zero human interventions, measured
from the first durable write to the last (`min(created_at)` to `max(updated_at)` across the run's
`TicketOutcome` records, cross-checked against the launcher log timestamps).
**Interventions** are defined observably: any human keystroke into the session, edit of the repo or
config during the run, or manual process signal. A watchdog restart is *not* a human intervention (it
is the machinery working); it is counted separately under recovery.
**Does NOT prove:** anything about the quality or value of what was produced during that time; a run
that parks everything also runs uninterrupted (see the parked-ratio caveat).

### 2. Completed-backlog ratio

**Definition.** `(DONE + DONE_LOW_CONFIDENCE) / tickets offered`, with the two states **always reported
separately** (they are different claims: gate-green-and-trusted vs gate-green-needs-daylight-review).
"Offered" = tickets the scheduler actually handed out, so quarantined dependents are visible as a
separate count, not silently missing from the denominator.
**Read from:** counting `state` values across the outcome records; the report's summary line is the
cross-check.
**Does NOT prove:** that each diff is *correct* — DONE means the deterministic gate passed, nothing
more (see [state machine](state-machine.md#limitations)).

### 3. Recovery success

**Definition.** Of the failures deliberately injected (red gate, process kill mid-ticket, stalled
command / stale heartbeat), the fraction after which the run resumed to a known-good tree and continued
scheduling: tree clean or equal to the pending snapshot (`git status` / snapshot hash), the interrupted
ticket re-offered or correctly terminal, and subsequent tickets still processed.
**Read from:** the outcome records after resume, `ledger.json` attempts (the interrupted ticket's count
survives), the run branch history, and watchdog restart lines in the launcher log.
**Does NOT prove:** that the retried ticket then *passes* — recovery is about the run, not the ticket.

### 4. Retry efficiency

**Definition.** `total attempts / completed tickets` (from `ledger.json` `attempts`), plus two counts:
tickets force-parked by the attempt cap and tickets force-parked by loop detection (same failure
signature recurring).
**Read from:** `ledger.json` (`attempts`, `signatures`) joined with final `state` per ticket.
**Does NOT prove:** that a force-parked ticket was truly unsolvable — the cap bounds spend, it does not
diagnose (a human retry with `reset-attempts` may well succeed; see [recovery](recovery.md)).

### 5. Interruption reduction

**Definition.** Count of run-blocking questions or stops that required a human, compared between the
two arms of the controlled procedure (baseline agent vs ANS-governed agent) on the identical backlog.
The ANS target is **0**; the baseline arm's count is *measured*, never assumed.
**Read from:** session transcripts/logs of both arms (a blocking question is observable as the agent
idling on a prompt); ANS-side cross-check: `AskUserQuestion` denials in the hook path and the absence
of stops while the sentinel existed.
**Does NOT prove:** the *value* of the work done between interruptions, and it says nothing when the
baseline agent happens to hit no ambiguity (which is why the backlog plants ambiguity deliberately —
see below).

### 6. Parked ratio

**Definition.** `(PARKED_DECISION + PARKED_FOUNDATIONAL + BLOCKED_ENV) / tickets processed`, reported
with the per-ticket `category` breakdown. (The low-yield breaker's internal "bad ratio" additionally
counts failures; when citing that mechanism, cite it under its own name — see
[scheduling](scheduling.md#the-low-yield-circuit-breaker).)
**Read from:** `state` + `category` across outcome records; the report's per-state sections.
**Does NOT prove:** a low ratio is not automatically good, and a high ratio is not automatically bad.
**This caveat is load-bearing:** a run that parks *everything* scores zero interruptions while doing no
work. Parked ratio and completed-backlog must always be read *together*; neither alone is a success
signal. Correct parks on planted high-blast-radius tickets are the mechanism *working*.

### 7. Human dependency

**Definition.** The count and kind of decisions left for a human after the run: outcome records with a
non-empty `human_action_required`, broken down by `category` and by state (a parked decision vs a
failed-needs-look are different kinds of dependency). Optionally, time-to-clear: how long the human
needed to action the morning list (measured in the experiment, not assumed).
**Read from:** `human_action_required`, `category`, `state` per record; the report renders exactly
these as `next action` lines.
**Does NOT prove:** whether those decisions were easy or hard, nor whether the run *should* have made
them (that judgment is the decision model's contract, audited separately).

### 8. Autonomy index (composite)

**Definition.** A single comparable summary computed from the sub-metrics above. Its **inputs** are:
uninterrupted runtime (normalized to scheduled run length), completed-backlog ratio, recovery success,
retry efficiency (inverted: fewer attempts per completion is better), interruption count (target 0),
and parked ratio *read against* the planted-park expectations.
**The weighting is a declared choice, not a discovered truth.** Any published index MUST state its
weights alongside the raw sub-metrics, and the raw sub-metrics must always be published with it. Two
indices computed with different declared weights are not comparable; we do not claim a canonical
weighting yet.
**Does NOT prove:** anything its inputs don't — a composite can hide a bad sub-metric, which is exactly
why raw metrics travel with it, always.

## The controlled backlog design

Comparability requires a backlog designed for measurement, not a convenience sample. The reference
design (parameters are design choices, adjustable but reported):

- **Repo + gate held constant.** A defined repo at a pinned commit; a deterministic gate (test suite)
  with a known-green baseline; gate command and timeout recorded.
- **Ticket mix** (target ~20 tickets, so the low-yield breaker's `min_tickets = 8` is comfortably
  exceeded and ratios are meaningful):
  - **Clean feature tickets** (~half the backlog) — small, independent, low blast-radius; expected
    outcome DONE. Right-sized: one reversible change each, acceptance check stated in the body.
  - **Bugfix tickets with repro** — "write the failing test, then fix"; expected DONE with the gate
    witnessing the fix.
  - **Ambiguity plants** — tickets deliberately carrying requirement-meaning ambiguity signals
    ("decide which…", "TBD"); expected PARKED_DECISION, *not* an assumed guess. These make
    interruption-reduction measurable: the baseline agent should stop and ask exactly here.
  - **Hard-park plants** — at least one ticket in an enumerated high-blast-radius category (e.g.
    schema-migration wording); expected PARKED_FOUNDATIONAL with dependents quarantined (include one
    dependent ticket to observe the quarantine).
  - **A gate-breaking ticket** — implements something that turns the suite red; expected revert +
    FAILED_RETRYABLE, then force-park at the attempt cap. This exercises retry efficiency and
    reversibility.
  - **Failure injections** (not tickets): one process kill mid-ticket and one stalled command / frozen
    heartbeat during the run, at pre-declared points. These exercise recovery success and the watchdog.
- **Size discipline.** Ticket bodies written to a common template (intent, constraints, acceptance
  check); expected-diff size bounded and recorded per ticket so throughput comparisons aren't skewed by
  one giant ticket.
- **Expected-outcome key.** Each ticket's *expected* terminal state is written down before the run;
  scoring compares actual vs expected (a plant that PROCEEDs is a finding, not a success).

## The measurement procedure (two arms)

1. **Fix the backlog** as designed above, on the pinned repo + gate.
2. **Run two arms on identical conditions:** (A) the *baseline* — the same coding agent driving the
   same backlog without ANS governance (it may stop at the first unanswerable question; that stop is a
   data point); (B) the same agent governed by ANS (`next`/`complete` loop, hooks active, watchdog on).
3. **Inject the same controlled failures** in both arms at the same pre-declared points.
4. **Touch nothing while either arm runs.** Any unavoidable intervention is recorded and ends the
   "uninterrupted" clock for that arm.
5. **Collect** the durable artifacts listed above (state records, ledger, report, logs, run branch) for
   each arm, and compute each metric per its definition.
6. **Publish setup + raw outcomes,** dated, alongside any derived number — never a derived number
   alone.

## Environment reporting requirements

A result without its environment is not reproducible. Every published run MUST report:

- **ANS version + commit** (`agents_never_sleep.__version__`, git SHA) and install method.
- **Agent CLI + version + model identifier** and the exact invocation (autonomy flag included) — from
  the preset actually launched. Verification status per platform (only Claude Code is live-verified;
  every other platform is built to its documented hook contract, not live-verified — a run on one *is*
  a verification run and must be labeled as such).
- **Gate command, timeout, and baseline status** (the suite and its runtime on the clean tree).
- **Config knobs that shape the run:** budget caps (`per_ticket_timeout_s`,
  `per_ticket_fix_iterations`, `max_tickets_per_run`), `fresh_session_every`, council/specialists
  on/off, watchdog settings.
- **Host facts:** OS + version, Python version, CPU/RAM class, disk headroom; whether the run shared
  the host with other load.
- **Timing facts:** start timestamp (UTC), scheduled duration, and the date of the run (API-side
  conditions vary over time and cannot be pinned — say so rather than pretend otherwise).
- **The backlog itself:** the ticket files, the expected-outcome key, and the injection schedule.

## The reproducible harness (`acceptance/`)

The harness that exercises the loop end-to-end already exists and is hermetic:

- **`acceptance/run_acceptance.py`** — the one verification that maps directly to the "mid-run stop" pain. It
  sets up a throwaway sandbox repo, runs the harness unattended over the three acceptance tickets with a
  deterministic `DemoWorker`, and asserts the harness drove all three without ever asking a live question /
  halting, produced the correct durable outcome state for each, **reverted the bad edit (tree clean) and
  kept the good edit**, and wrote a run report. Exit 0 = green.
- **`acceptance/test_*.py`** — focused hermetic tests for each spine + machinery component (resume,
  revert/backup, stop-hook, ask-hook, redaction, keysource, launcher mutual-exclusion, watchdog,
  fresh-session, classify narrowing/overrides, paperclip, …). `acceptance/run_all.sh` runs them all and
  exits non-zero on the first red.

These tests prove the *mechanism* (the contract holds, recovery works, secrets don't leak) deterministically
and with **fake fixtures only** — no real credentials, no model calls. They are the substrate a real
autonomy benchmark builds on; they are not themselves an autonomy *result*.

## Publication rules

Results will only ever be published **dated and reproducible**: the environment block above, the
backlog + expected-outcome key, the raw per-ticket outcomes, the raw sub-metrics, and only then any
composite — with its weights declared. **No results exist yet.** The controlled "baseline-agent vs ANS
on a backlog" comparison is scoped as the first reproducible experiment (tracked internally as
Paperclip `18eee818`); it is methodology-only until run, and its outcomes will be folded into a dated
appendix here — and not one moment before.

## Boundary

This benchmark measures *execution autonomy*. Measuring code quality or model performance is a different
job for a different building block (Benchmark / verification); ANS reports its own spend and outcomes but
does not benchmark the *quality* of the work. See the [glossary](glossary.md) ecosystem table.

## Limitations

Every metric here is a *methodology* until run; this document claims no results. A composite autonomy index
can mask a poor sub-metric, which is why the raw metrics (especially parked-ratio vs completed-backlog) are
always reported together. The planted-ticket design measures the classifier only against the plants it
contains — it cannot rule out mis-classification on wording it didn't plant. The `acceptance/` harness
proves mechanism deterministically but uses a synthetic worker, so it does not measure a real model's
behaviour on a real backlog — that is what the dated experiment will add. And a single experiment is a
single point: API-side conditions vary by day and model version, so even a published result generalizes
only as far as its environment block says.

---

*Verified against `agents_never_sleep/` (v1.0.0): `state.py` (`TicketOutcome` fields, `OutcomeState`),
`ledger.py` (`attempts`, failure signatures), `report.py` (summary line, per-state sections,
`next action`/`category` lines, `report.local_path`), `orchestrator.py` (`LowYieldBreaker`
`min_tickets`/bad-ratio), `acceptance/run_acceptance.py`, `acceptance/run_all.sh`, and Paperclip
`18eee818` (first experiment, methodology-only until run). No benchmark results are claimed.*
