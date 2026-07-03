# ANS Benchmarks — methodology, not claimed results

> **30-second version.** This is **how to measure** the autonomy of an unattended run — not a table of
> results we are claiming. ANS's value is "the run made real, reversible progress without a human", and
> this doc defines the metrics that capture that (uninterrupted runtime, completed backlog, recovery
> success, retry efficiency, interruption reduction, parked ratio, human dependency, and a composite
> autonomy score), the controlled procedure to measure them, the reproducible `acceptance/` harness, and —
> honestly — what each metric does and does **not** prove. Numbers appear only in a clearly-dated appendix
> *when actually run*. See [recovery](recovery.md), [scheduling](scheduling.md), [glossary](glossary.md).

> **Honesty bar (non-negotiable).** The metrics below are **mostly not yet measured.** Nothing in this
> document is a benchmark *result*. No fabricated comparison, no invented figure, no "X% faster than".
> When a metric is run for real, it goes in a dated, reproducible appendix with the exact setup — never
> inline as a bare number.

## Why an "autonomy" benchmark, not a "quality" benchmark

ANS does not write code and does not judge whether code is correct — so it would be dishonest to benchmark
it on code quality or bug-catching. What ANS *does* is govern an unattended run: keep it going, keep it
reversible, recover from failure, and defer (not guess) the high-stakes unknowns. The right thing to
measure is therefore **autonomy** — how much useful, reversible progress a run makes without a human in
the loop — not correctness, which belongs to the deterministic gate and the delegated verification layer.

## The metrics (defined, not claimed)

The headline quantity is a composite **autonomy-index**, a function of the metrics below. Each is defined
so it is reproducible and so its limits are explicit.

| Metric | Definition | What it proves | What it does NOT prove |
|---|---|---|---|
| **Uninterrupted runtime** | Continuous wall-clock the run advanced without a human touch. | The never-stop / never-ASK contract held. | Nothing about code quality. |
| **Completed backlog** | Tickets reaching DONE (and DONE_LOW_CONFIDENCE) per run / per session. | Throughput under autonomy. | Not that each diff is correct (that's the gate). |
| **Recovery success** | Fraction of injected failures (red gate, crash/kill, stale heartbeat) that resumed cleanly to a known-good tree. | The durability spine + watchdog work. | Not that the retried ticket then *passes*. |
| **Retry efficiency** | Attempts per completed ticket; how often the attempt cap / loop detector force-parked. | Anti-starvation is bounding wasted effort. | Not that a force-parked ticket was truly unsolvable. |
| **Interruption reduction** | Human interruptions, **target 0** (vs a baseline agent that stops at the first question). | The core problem ANS exists to solve is solved. | Not the *value* of the work done between interruptions. |
| **Parked ratio** | (parked + blocked) / processed, with reasons. | Honest deferral rate. | A high park rate is **honest, not necessarily a win** — see below. |
| **Human dependency** | Count + kind of decisions that required a human action afterward. | How much the run actually offloaded. | Not whether those decisions were easy or hard. |
| **Autonomy score** | A composite of the above (continuous runtime, tickets completed, interruptions→0, recovery, unfinished tickets). | A single comparable summary. | Only as meaningful as its inputs; a composite can hide a bad sub-metric. |

**The parked-ratio caveat is load-bearing.** A run that parks *everything* would score "zero
interruptions" while doing no work. Parked ratio and completed-backlog must always be read *together*;
neither alone is a success signal. This is exactly why the honesty bar forbids a single headline number.

## The measurement procedure (controlled backlog)

To compare meaningfully, hold everything constant except the governance layer:

1. **Fix the backlog.** A defined set of tickets on a defined repo at a defined commit, with a defined
   deterministic gate.
2. **Run it twice on the same repo + gate:** once with a *normal* coding agent (no governance — it stops
   at the first unanswerable question), once with ANS governing the same agent.
3. **Inject the same controlled failures** in both arms (a deliberately-breaking ticket, a kill mid-run, a
   stalled command) so recovery is exercised identically.
4. **Record the metrics above** for each arm, plus the per-ticket outcome states from the durable store and
   the run report.
5. **Publish setup + raw outcomes**, dated, alongside any derived number — never a derived number alone.

## The reproducible harness (`acceptance/`)

The harness that exercises the loop end-to-end already exists and is hermetic:

- **`acceptance/run_acceptance.py`** — the one verification that maps directly to the "2am stop" pain. It
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

## The first reproducible experiment

A controlled "normal-agent vs ANS on a backlog" comparison is scoped as the **first reproducible
experiment** (tracked internally as Paperclip `18eee818`). It is **methodology only until run**: when it is
executed, its setup and raw outcomes will be folded into a dated appendix here — and not one moment before.

## Boundary

This benchmark measures *execution autonomy*. Measuring code quality or model performance is a different
job for a different building block (Benchmark / verification); ANS reports its own spend and outcomes but
does not benchmark the *quality* of the work. See the [glossary](glossary.md) ecosystem table.

## Limitations

Every metric here is a *methodology* until run; this document claims no results. A composite autonomy score
can mask a poor sub-metric, which is why the raw metrics (especially parked-ratio vs completed-backlog) are
always reported together. The `acceptance/` harness proves mechanism deterministically but uses a synthetic
worker, so it does not measure a real model's behaviour on a real backlog — that is what the dated
experiment will add.

---

*Verified against `agents_never_sleep/` (v1.0.0): `acceptance/run_acceptance.py`, `acceptance/run_all.sh`,
`acceptance/test_*.py`, the autonomy-index sketch in the project spec §7, and Paperclip `18eee818` (the
first experiment, methodology-only until run). No benchmark results are claimed.*
