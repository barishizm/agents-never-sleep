---
name: agents-never-sleep
description: >-
  Run large, multi-step work UNATTENDED — a backlog of tickets or milestones — without stopping
  to ask the human trivial clarifying questions. Use this whenever the user hands off a big job to
  run overnight / "while I'm away" / "keep going till it's done", points you at a list of tickets or
  a milestone, or says "unattended", "don't stop and ask", "work through the backlog", or "finish
  this tonight". Also use when a long autonomous run keeps stalling on questions. It gives you a
  durable per-ticket state machine, an ASK/PARK/HALT autonomy contract (never block the run on a
  single ticket), deterministic-gate quality checks with a failure taxonomy, git-backed
  reversibility, attempt/loop caps, and a morning report — so the night never idles and nothing
  irreversible happens unsupervised. Make sure to reach for this even when the user does not say
  "unattended" but is clearly handing off long, autonomous, run-to-completion work.
---

# Agents Never Sleep (ANS)

Run a backlog to completion overnight without the run ever soft-halting on a question. The hard
part is not doing the work — it is **state durability + concrete park-vs-continue semantics +
anti-starvation**, so that is what this skill is built around. The heavy multi-model review funnel
is deliberately Phase 2 (see `BUILD-PLAN.md`); ship reliability first.

> Full rationale: `agents-never-sleep-design.md` (13 design threads + 3 council reviews).
> The MVP spine is implemented as a small Python harness under `harness/` and proven by
> `acceptance/run_acceptance.py` (the only test that maps to the "stops at 2am" pain).

## The autonomy contract — three distinct states, never collapsed

A run has exactly three responses to uncertainty. Keep them separate; collapsing them is how a run
inverts into the very stalling it exists to prevent.

- **ASK** — ask the human. **Forbidden while unattended.** Do not emit `AskUserQuestion`; there is
  nobody to answer at 2am, and a single question wastes the whole night. This is enforced
  structurally, not by discipline: the `deny_ask.sh` PreToolUse hook (matcher `AskUserQuestion`,
  env-gated `CLAUDE_UNATTENDED=1`) DENIES the tool and steers you back into PARK/PROCEED — the mirror
  of the never-stop guarantee.
- **PARK** — defer *this decision or ticket* and **keep the run moving** to the next independent
  ticket. Parking is normal and healthy, not a stop.
- **HALT** — stop the *whole run*. Only on genuinely irreversible danger that the hook layer would
  block anyway, or when there is no reversibility safety net at all (read-only fs, no VCS and none
  creatable).

When unattended you only ever choose PROCEED, PARK, or HALT. Never ASK.

## Decide PROCEED vs PARK by blast radius (so "unsure" is rare)

Make the tiering concrete — guessing on a high-blast-radius item and being confidently wrong all
night is the worst outcome, worse than parking.

**Hard-PARK (never guess):** DB schema / migration direction, public or shared API contract,
security / auth / tenant-isolation boundary, money / billing / pricing, a cross-ticket interface
others build on, and **requirement meaning** (you don't actually know *what* to build) unless it is
both locally reversible and isolated — then build it reversibly behind a flag / draft change AND
park the decision (hybrid).

**Proceed (assume + log + continue):** naming, internal structure, log / comment / error wording,
test fixtures, a choice between two equivalent local implementations, trivially-toggled defaults.

**When genuinely unclassifiable → PARK.** A wrongly-parked small item costs a 5-second morning
decision; a wrongly-assumed big one costs a night of wrong work.

Every PROCEED assumption must be an immediately-revertible commit, and every PARK must record: why,
the candidate interpretations, the exact human next-action, and its contamination scope.

## The per-ticket loop (what the harness enforces)

1. **Preflight measures capabilities** (`harness/preflight.py`) — VCS/reversibility, platform,
   gates, execution mode, tokonomix/Vault/Paperclip. Missing capability never stops the run; it
   lowers expected yield and raises conservatism. No VCS → establish a safety net (git init /
   timestamped backup) before any risky edit; if impossible → non-destructive only.
2. **Decide** ASK/PARK/HALT for the ticket (above). Unattended: ASK→PARK.
3. **Implement** the PROCEED ticket — *you, the agent, are the worker*: read the ticket the harness
   hands you and edit files. You drive this one ticket at a time via the two subcommands below; the
   harness owns scheduling, parking, snapshot/revert and the never-stop sentinel.
4. **Gate** deterministically (`harness/gates.py`) — the BACKBONE. Classify failures:
   introduced-by-the-diff → hard-block (revert to last green + park/fail); pre-existing / flaky /
   env → downgrade confidence, continue or park (never report as "the ticket failed"); timeout/env
   → BLOCKED_ENV. Every gate runs with a per-step timeout and a non-interactive environment so it
   can never hang on a TTY prompt. **Never delete or skip a failing test to go green** — that is a
   blocking blind-spot.
5. **Record** exactly one durable outcome (`harness/state.py`): DONE, DONE_LOW_CONFIDENCE,
   PARKED_DECISION, PARKED_FOUNDATIONAL, BLOCKED_ENV, FAILED_RETRYABLE, FAILED_BUG_IN_AGENT — with
   the required fields. Atomic writes; resume-safe.
6. **Next ticket.** Attempt + loop caps (`harness/ledger.py`) force-park a ticket that exceeds its
   cross-resume attempt cap or is provably looping, so the night is never burned on one cursed item.
   A low-yield circuit breaker stops and alerts if most work is parked/blocked.

## Running it — the agent IS the worker (drive this loop)

The harness cannot call you from inside a Python loop, so you drive it. Alternate these two
subcommands until the backlog drains. Each prints one JSON object to stdout.

```
# 1. Ask the harness for the next thing to do. It auto-parks ambiguous/high-blast-radius tickets
#    and only ever hands you ONE ready-to-implement ticket, or a terminal signal.
python3 -m harness.run next --repo <project> --tickets <dir-of-.md-tickets>
```

Read the JSON `status`:
- **`PROCEED`** → implement ONLY `ticket.body` by editing files in the repo (do NOT touch other
  tickets, do NOT stop, do NOT ask). Then call `complete`:
  ```
  python3 -m harness.run complete --repo <project> --attempted "one-line summary of what you did"
  ```
  Use `--cannot-implement` (with `--attempted` explaining why) if you genuinely cannot do it — the
  harness reverts your partial edits and records BLOCKED_ENV. After `complete`, call `next` again.

  **If the `PROCEED` payload carried a `council` or `specialists` block, you ran reviews — you MUST
  feed the results back on `complete`, or the advisory trust-gating silently never fires:**
  `... complete --attempted "…" [--council-verdict pass|concerns|error --council-cost <€>] \
  [--specialist-concerns architect,security,… --specialist-cost <€>] [--review-coverage "<who ran>"]`.
  Omit a flag only when you ran no such review. (Details: the Council and Specialist sections below.)
- **`DRAINED` / `HALTED` / `LOW_YIELD`** → the run is over; the morning report is written. Stop.
- **`NON_DESTRUCTIVE`** → unattended with no saved config; do a configuring interactive run first.

**Never invent your own loop or stop early.** `next` owns the `.unattended/run-incomplete` sentinel
that the Stop-hook uses to block a premature 2am stop; keep calling `next` until it returns a
terminal status. The harness handles snapshot-before-edit, gate-after-edit, revert-on-red, the
attempt cap, loop detection and the low-yield breaker — your only job is the edits.

> **Sentinel path contract (load-bearing, enforced).** The Stop-hook checks
> `${UE_RUN_INCOMPLETE:-$PWD/.unattended/run-incomplete}` and the driver writes the same path. They
> agree automatically **only when the agent runs from the repo root** (so `$PWD == --repo`; use
> `--repo .`). For an unattended run where CWD may differ from `--repo` (cron / `claude-run`),
> export `UE_RUN_INCOMPLETE=<repo>/.unattended/run-incomplete` at launch. To stop never-stop from
> breaking silently, `next` **hard-fails** (`status:"ERROR"`, exit 2) when unattended + CWD ≠
> `--repo` + `UE_RUN_INCOMPLETE` unset — fix the launch (cd into the repo, or set the env var).

First interactive run triggers a minimal per-project wizard (`.claude/agents-never-sleep.json`).
The skill never schedules itself — running unattended (cron / `claude-run`) is always the user's
explicit act, so the wizard always gets to run first. Unattended with no config → non-destructive
only + a loud note in the report.

> Legacy `python3 -m harness.run run` drives the loop in-process with a deterministic Worker; it is
> only for the hermetic acceptance demo. Real runs use the `next`/`complete` flow above.

## Council review (multi-model, advisory) — when configured

If the project config enables `council` (needs the tokonomix gateway), each `PROCEED` ticket carries a
`council` block. **You run the council via the tokonomix MCP** (the harness can't call LLMs) — it is
ADVISORY and never blocks the run; it only decides whether finished high-risk work is auto-trusted.

Per ticket, when a `council` block is present:
1. **Pre-work:** read `council.hint_tier` (a non-binding hint). Plan to convene a council on your
   implementation. LIGHT = a de-anchoring pass ("what am I not seeing?"). HEAVY (schema/migration,
   security/auth/tenant, money/billing, public API, cross-service) = review the plan AND the diff.
2. **Pull FRESH model slugs** from `tokonomix_list_models` (the configured slugs drift). Prefer the
   `proposers`/`judges` in the block but swap any that 404 / are slow. Call
   `tokonomix_consensus_ask(models=[...], judge_models=[...], mode="consensus")`.
3. **ALWAYS show** the pre-council summary (`council.summary`: task · proposers · judges · mode · est
   €) before the call, and the post-call summary + the REAL charged cost + which proposers
   errored/timed-out afterward. Unattended: show and continue. Interactive: show and get approval.
4. **Graceful degradation:** if the council errors / times out / has no key, log it as a blind-spot
   and PROCEED — never stop. Report it as `--council-verdict error`.
5. **Feed the result back** on `complete`:
   `... complete --council-verdict pass|concerns|error --council-cost <€charged> --review-coverage
   "<proposers that ran, who errored, € cost>"`. Omit `--council-verdict` only if you ran no council.

**Cost safety (unattended runs spend real money).** The harness enforces a per-night brake from
`--council-cost`: once `budget.per_night_euro_cap` or `budget.max_council_calls_per_night` is reached,
`next` returns `council: {disabled: ...}` — stop convening councils (high-risk diffs are still flagged
for daylight review). Also check `tokonomix_get_balance` before convening; if balance is below
`budget.balance_threshold_euro`, stop convening councils, log a blind-spot, and proceed. Always report
the real charged cost via `--council-cost` so the brake is accurate.

The harness then re-routes from the ACTUAL diff (overriding the hint) and decides disposition: a
HEAVY-risk diff whose council raised **concerns**, **errored**, or **was never run** is recorded
`DONE_LOW_CONFIDENCE` and flagged **NEEDS DAYLIGHT REVIEW** in the morning report — done, but not
trusted to merge blind. Deterministic gates remain the only HARD gate; the council never reverts.

### Specialist reviewers (when `specialists` is enabled)

A finer-grained companion to the whole-diff council: distinct review **lenses**. A `PROCEED` payload
carries a `specialists` hint — `architect` + `security` always, plus `tenant-safety` / `mobile` /
`ux` / `i18n` / `performance` / `seo` only when the diff (or, for the hint, the ticket text) touches
that domain. **You run each lens as a focused tokonomix review** of your plan/diff; it is ADVISORY
and never blocks. On `complete`, report any lens that raised a **material concern** via
`--specialist-concerns architect,security,…` and the real € via `--specialist-cost`. The harness
records which lenses applied (from the actual diff) as coverage, and folds a concern in a
**high-blast-radius** lens (`architect` / `security` / `tenant-safety`) into the SAME daylight-review
disposition as the council — `DONE_LOW_CONFIDENCE` + **NEEDS DAYLIGHT REVIEW**, composed alongside any
council reason, never clobbering it. Specialist € shares the council's per-night spend cap (it does
not consume a council-call slot). If `budget_exhausted` trips, `specialists` is returned `disabled` —
stop convening lenses; high-risk diffs are still flagged.

**Recommended council cadence:** run a council at ticket **start** (plan review), **mid** (after a
significant implementation choice), and **end** (diff review) — approximately 3 calls per ticket.
Running a council on every individual change (per-call) is possible but only recommended when the
user explicitly requests it, given the per-night call cap and credit cost. The default caps
(`max_council_calls_per_night`, `per_night_euro_cap`) are sized for the 3-calls-per-ticket cadence.

Mode detection is layered: `CLAUDE_UNATTENDED=1` (set by `claude-run`/cron) or a keyword →
unattended (no prompts, ever); otherwise interactive.

## Portability

This is the open `SKILL.md` standard — it runs in Claude Code, Codex, Gemini CLI, Copilot, Cursor
and 30+ other tools. The body above is written by ROLE, not by Claude-specific tool names. Enforcement
(Stop-hook to prevent premature stop, deny-hooks for irreversible actions and for asking the human)
is a thin per-platform adapter; the Claude adapter lives in `hooks/` and is opt-in (env-gated to
`CLAUDE_UNATTENDED=1`).
An `AGENTS.md` router lets file-based tools discover this skill.

## What is deferred to Phase 2

The agent-as-worker bridge, the multi-model council (diff-routed light/heavy review, advisory
trust-gating), the never-ASK enforcement hook, the conditional specialist reviewers
(architect/security/tenant-safety daylight-fold, diff-routed lenses), and shape-anchored secret
redaction (scrubs credentials from the report, gate artifacts, Paperclip comments and emitted JSON;
a literal-value registry the Vault slice will feed) are now built. Still deferred: full Paperclip
integration (pull tickets / push status + parked comments) and cross-platform enforcement
adapters. The spine ships and is proven first; quality machinery layers on top.

The heartbeat watchdog is built and proven (`harness/watchdog.py`, `acceptance/test_watchdog.py`): a
sidecar that runs the unattended command as a child, restarts it resumable when the heartbeat goes
stale (the hang the Stop-hook can't see), and on exhausted restarts alerts + exits 75. Integrating it
with `claude-run` is **opt-in composition** (wrap the call; see `WATCHDOG.md`) — never a rewrite of
that shared wrapper.

Vault as a key source is built: a `token_ref` of `env:VAR` or `vault:<mount>/<path>[#field]` (the
form the wizard already writes) resolves the Paperclip token and tokonomix key from env or the configured
Vault (AppRole / `VAULT_TOKEN`, KV-v2), registers the resolved value with the redaction layer, and
DEGRADES to a morning-report blind spot — never a hard stop — when a configured source can't be read.

The tokonomix onboarding gate is built: when a credential consumer (council/specialists) is enabled
but no tokonomix credential is found, a `PROCEED` payload carries an `onboarding` directive — run the
keyless `tokonomix_onboard` → `tokonomix_onboard_verify` handshake (interactive), or, unattended, the
night proceeds with review disabled and the morning report carries a **BLIND SPOT** note. The MCP
calls are yours; the harness owns only the gate.
