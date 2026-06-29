# Agents Never Sleep (ANS)

**A governance/workflow layer that sits *above* a coding agent so it can make real progress on a
backlog unattended — without one unanswered question stalling the rest of the work.**

ANS is not a model, an IDE, or a coding agent. It **composes with** Claude Code, OpenAI Codex,
Cursor, OpenHands, Aider and CI/CD: they do the work; ANS governs *how the agent behaves when it
works autonomously for hours*. It is a portable
[Agent Skill](https://www.agensi.io/learn/agent-skills-open-standard) (`SKILL.md`) plus a small
zero-dependency Python harness.

- **Version:** 1.0.0
- **Install today:** `pip install git+https://github.com/TokonoMix/agents-never-sleep@v1.0.0`
  (PyPI publish is pending — see [Installation](#7-installation)).
- **Source:** [TokonoMix/agents-never-sleep](https://github.com/TokonoMix/agents-never-sleep) · MIT

---

## 1. The problem

Most coding agents stop the moment they hit a question. That is fine when you are sitting there to
answer it. It is the failure mode of every *unattended* run — overnight, "while I'm away", a long CI
job, a milestone you handed off and walked away from.

A single ambiguous ticket ("which migration direction?", "is this the intended interface?") collapses
the whole session into a blocking prompt that nobody is there to answer. The agent waits. The other
forty tickets that did *not* depend on that question never get touched. You come back to a run that
spent eight hours, and real money, stalled on one decision a human could have made in five seconds.

The inverse failure is just as expensive: an agent that *doesn't* stop charges ahead and does
something irreversible — force-pushes, drops a column, deletes a secret — that you cannot undo in the
morning.

## 2. Why existing tools stall

A coding agent has exactly one lever for uncertainty: it asks the human. That single lever is
overloaded to mean three completely different things, and collapsing them is the root cause:

- *"I need a human to decide this."* — a genuine decision (schema direction, an API contract).
- *"I'm not sure, so I'll stop."* — defensible caution, but it shouldn't stop **everything**.
- *"This is irreversibly dangerous."* — the one case where stopping is correct.

Without structured autonomy, all three become the same prompt, and an unattended agent has no
principled way to keep moving past the first one. The agent is the *worker*; nothing above it owns
the question "what should an autonomous run do when it isn't sure?" That missing layer — between the
model and the developer — is what ANS provides.

## 3. How ANS solves it — the ASK / PARK / HALT autonomy contract

ANS gives the agent a contract with three distinct, never-collapsed responses to uncertainty. While
unattended the agent only ever chooses **PROCEED**, **PARK**, or **HALT** — it never **ASK**s.

| Response | What it means | Effect on the run |
|---|---|---|
| **PROCEED** | Assume + log + continue. For low-blast-radius, reversible choices (naming, internal structure, log wording, equivalent local implementations). The assumption is committed so it can be reverted. | Run keeps moving. |
| **PARK** | Defer *this one ticket/decision* and move to the next independent ticket. Normal and healthy — **not** a stop. Records why, the candidate interpretations, the exact human next-action, and the contamination scope. | Run keeps moving. |
| **HALT** | Stop the *whole run*. Only on genuinely irreversible danger with no safety net (e.g. read-only filesystem, no VCS and none creatable). | Run ends; operator must intervene. |
| ~~**ASK**~~ | **Forbidden while unattended** — nobody is there to answer. Converted to PARK. | — |

The discipline that keeps "unsure" rare is **deciding PROCEED vs PARK by blast radius**, made
concrete so the agent isn't guessing about whether to guess:

- **Hard-PARK (never guess):** DB schema / migration direction, public or shared API contract,
  security / auth / tenant-isolation boundary, money / billing / pricing, a cross-ticket interface
  others build on, and *requirement meaning* (you don't know **what** to build) — unless it is both
  locally reversible and isolated, in which case build it reversibly behind a flag **and** park the
  decision (a hybrid).
- **PROCEED:** naming, internal structure, log/comment/error wording, test fixtures, a choice between
  two equivalent local implementations, trivially-toggled defaults.

A wrongly-parked small item costs a five-second morning decision; a wrongly-assumed big one costs a
night of wrong work. **PARK is the safe default:** anything that does not clearly meet the PROCEED bar
(or the HALT bar) is parked, so the contract covers the whole decision space rather than leaving a
gap. Blast-radius classification is the system's weakest link — it is the agent's judgment, helped by
the harness auto-classifier — which is exactly why every PROCEED change is made reversible (below).

This contract is enforced **structurally**, not by trusting the agent's 2 a.m. discipline — see the
architecture below. The guarantees are opt-in and env-gated (`CLAUDE_UNATTENDED=1`), completely inert
in normal interactive sessions.

## 4. Architecture

The agent **is** the worker. ANS owns scheduling, safety, reversibility and bookkeeping. The pieces:

### Per-ticket state machine

Every ticket runs through a durable, resume-safe loop (`agents_never_sleep/driver.py`,
`state.py`):

1. **Preflight** (`preflight.py`) measures capabilities — VCS/reversibility, platform, gates,
   execution mode, optional Tokonomix/Vault/Paperclip. A missing capability never stops the run; it
   lowers expected yield and raises conservatism. No VCS → establish a safety net (git init /
   timestamped backup) before any risky edit, or stay non-destructive.
2. **Decide** PROCEED / PARK / HALT by blast radius (`decide.py`). Unattended: ASK → PARK.
3. **Implement** — the agent edits files for exactly one PROCEED ticket.
4. **Gate** (`gates.py`) — deterministic, the only HARD gate (see below).
5. **Record** exactly one durable outcome (`state.py`) — atomic writes, resume-safe.
6. **Next ticket** — attempt/loop caps (`ledger.py`) force-park a cursed item; a low-yield circuit
   breaker stops and alerts if most work is parking/blocking.

### Deterministic gates — the only HARD gate

A **gate** is a shell command (your test suite) run after every edit. Exit 0 = green; non-zero = red.
The harness classifies a red as *introduced-by-the-diff* (revert to last green + park/fail) vs
*pre-existing / flaky / env* (downgrade confidence, keep the work, note it as a blind spot) via
snapshot comparison. Every gate runs with a per-step timeout and a non-interactive environment, so it
can never hang on a TTY prompt; a timeout yields `BLOCKED_ENV`, never a run halt. **The deterministic
gate is the only thing that can hard-block a ticket** — the review council (below) is advisory and
never reverts. ANS never deletes or skips a failing test to go green; doing so is a blocking blind
spot.

### Git-backed snapshot / revert

Each PROCEED ticket is snapshotted before edits (`vcs.py`); a red gate reverts to the last green
commit. If the snapshot commit cannot be made (git lock / timeout / read-only object store), the
ticket is recorded `BLOCKED_ENV` rather than edited unrevertibly. Every PROCEED assumption is
committed so it can be reverted in daylight.

### Attempt / loop caps

`ledger.py` enforces a cross-resume attempt cap per ticket and detects provable loops, force-parking
anything that would otherwise burn the night on one cursed item. A low-yield breaker halts the run
and alerts when most outcomes are parks/blocks.

### The launcher (`bin/ans-run`) — preflight + working-tree flock

`preflight.py` measures capabilities only *after* the agent session boots — by then the first tokens
are spent. For headless/cron launches, `bin/ans-run` (installed as `ans-run`) is a deterministic
GO/NO-GO gate that runs **before** the agent CLI boots:

- **Config trust (TOFU):** `.claude/agents-never-sleep.json` travels with the repo and describes
  commands the launcher will execute. A new/changed config must be trusted once per user (keyed on
  its SHA-256, recorded outside the repo). Headless + untrusted = NO-GO.
- **Identity / root-guard:** configurable `launcher.target_user`; started as root with a target user
  → re-exec as that user; as root with none configured → NO-GO.
- **Agent selection:** named, human-confirmed presets (`--agent`). No launch-time platform detection
  (env markers are spoofable and gone under cron). Each preset must pass a 5 s `--version` capability
  probe (catches flag drift before tokens are spent) and carry `autonomy_confirmed: true`.
- **Autonomy flags are an explicit human decision, never a default.** A detached run with permissions
  fully on stalls at the first approval prompt; the flag that prevents that grants real power
  (`--permission-mode acceptEdits`, `--sandbox workspace-write`, `--yolo`, `--allow-all-tools`). The
  wizard shows what the flag grants before the preset can be marked launchable.
- **Atomic mutual exclusion:** a non-blocking `flock(2)` on `<repo>/.unattended/ans-run.lock`, held by
  the long-lived agent process and released by the kernel on any crash/kill. Two simultaneous starts
  → exactly one winner (no TOCTOU-racy pidfiles). Exit codes: `0` GO, `64` NO-GO, `65` tree busy.
- **Token-refs, never literal keys:** a preset's `env` can point the CLI at a gateway via `env:VAR`
  or `vault:<mount>/<path>[#field]`, resolved through the keysource and registered for redaction. A
  failed resolution is a blocking NO-GO, never a silent empty value.

### Optional advisory review — council & specialists

When configured (and a Tokonomix gateway is reachable), high-risk diffs are reviewed by a multi-model
**council** (`council.py`) and specialist **lenses** (`specialists.py`: architect/security always,
plus tenant-safety/mobile/ux/i18n/performance/seo when the diff touches them). This is **advisory and
never blocks the run** — it only withholds the "trusted" stamp: a HEAVY-risk diff whose council raised
concerns, errored, or never ran is recorded `DONE_LOW_CONFIDENCE` + **NEEDS DAYLIGHT REVIEW**. The
council is a recall amplifier (proposers blind+parallel, an independent cross-family judge), not a
truth oracle — agreement is not correctness. Per-night euro and call-count caps brake the spend.

### Watchdog, secret redaction, key source, Paperclip

- **Watchdog** (`watchdog.py`) — a sidecar that runs the unattended command as a child and restarts
  it resumably when the heartbeat goes stale (the hang a Stop-hook can't see); on exhausted restarts
  it alerts and exits 75. Composes with `claude-run`; never rewrites it.
- **Secret redaction** (`redact.py`) — every report, log, saved gate-output, Paperclip comment and
  emitted JSON is scrubbed of credentials by *shape* (tokens, JWTs, private keys, connection-string
  passwords) plus a registry of known secret values, without mangling ordinary text or git SHAs.
- **Vault key source** (`keysource.py`) — optional tokens resolve from env or HashiCorp Vault
  (AppRole / `VAULT_TOKEN`, KV-v2); a resolved value is auto-registered for redaction and degrades to
  a morning-report blind spot, never a hard stop, when unreadable.
- **Paperclip integration** (`sources/paperclip.py`) — optionally pull open issues from one project
  as the work source and push per-ticket status transitions + parked/daylight comments back, with
  graceful degrade-to-local when the board can't be read.

These are all **built in 1.0**, not future phases.

## 5. Workflow

The harness cannot call the agent from inside a Python loop, so the agent drives a two-command loop
until the backlog drains. Each command prints one JSON object to stdout.

```bash
# Hand me ONE ready ticket (auto-parks ambiguous / high-blast-radius ones), or a terminal signal.
python3 -m agents_never_sleep.run next     --repo . --tickets <dir-of-.md-tickets>
#   …implement ONLY ticket.body by editing files in the repo…
python3 -m agents_never_sleep.run complete --repo . --attempted "one-line summary of what you did"
#   …repeat next/complete until next returns a terminal status.
```

`next` reads the JSON `status`:

- **`PROCEED`** → implement the ticket, then call `complete`. If the payload carried a `council` /
  `specialists` block, feed the review results back on `complete`
  (`--council-verdict pass|concerns|error --council-cost <€>`, `--specialist-concerns …`), or the
  advisory trust-gating silently never fires.
- **`DRAINED` / `HALTED` / `LOW_YIELD`** → the run is over; the morning report is written. Stop.
- **`NON_DESTRUCTIVE`** → unattended with no saved config; do a configuring interactive run first.

`next` owns the never-stop sentinel that blocks a premature stop; never invent your own loop or stop
early. Operator escapes for a confused resume: `reset-attempts <id>` (clear one ticket's attempt
counter), `reset-spend` (zero the per-night spend accounting), `parked` (protect/restore parked WIP),
`report` (re-write the morning report from the store).

### Outcome states

Exactly one durable outcome is recorded per ticket:

| State | Meaning |
|---|---|
| `DONE` | Implemented, gate green. |
| `DONE_LOW_CONFIDENCE` | Implemented, gate green, but a HEAVY-risk diff's review raised concerns / errored / never ran. **Needs daylight review.** |
| `PARKED_DECISION` | Requires a human decision before implementation. Parked cleanly. |
| `PARKED_FOUNDATIONAL` | Depends on a not-yet-completed prerequisite. |
| `BLOCKED_ENV` | Gate timed out / environment issue — not a code bug. |
| `FAILED_RETRYABLE` | Gate caught a bug the diff introduced; reverted, can retry. |
| `FAILED_BUG_IN_AGENT` | Repeated failures suggest a systematic problem. |

### The morning report

A single ranked report (`report.py`): what's **done & trusted**, what **needs daylight review**, what's
**parked** (with candidate interpretations and the exact next action), what's **blocked**, and any
**blind spots** (a degraded guarantee, a missing review credential, an unresolved secret). A LOW-YIELD
night is flagged loudly so "the run finished" is never mistaken for "the work got done".

## 6. Examples

Drive a backlog of local `.md` tickets from the repo root (`--repo .` keeps the never-stop sentinel
path auto-aligned):

```bash
cd /path/to/your/project

# Get a ticket
python3 -m agents_never_sleep.run next --repo . --tickets docs/backlog
# → {"status":"PROCEED","ticket":{"id":"add-rate-limit","body":"…","path":"…"},"snapshot":"<sha>", …}

#   …you (the agent) implement only that ticket…

# Record the outcome (gate runs here)
python3 -m agents_never_sleep.run complete --repo . --attempted "added token-bucket limiter + tests"
# → {"status":"RECORDED","ticket_id":"add-rate-limit","state":"DONE","next":"call `next`"}

# Loop until DRAINED / HALTED / LOW_YIELD, then read the report
python3 -m agents_never_sleep.run report --repo .
```

A ticket is a Markdown file with optional YAML front-matter (the body is the only required part):

```markdown
---
id: add-rate-limit
title: Add rate limiting to the public API
blast_radius: medium      # optional hint; the harness auto-classifies
---

Add a token-bucket rate limiter to POST /api/submit. 100 req/min per key.
Reject over-limit with HTTP 429 + Retry-After. Cover it with tests.
```

Launch a detached, headless run through the preflight launcher (installed as `ans-run`):

```bash
ans-run --repo /path/to/project --agent claude "work through the backlog unattended"
#   GO/NO-GO preflight runs BEFORE any token is spent; one winner per working tree.
ans-run --repo /path/to/project --check          # preflight report only; never starts/disturbs a run
```

Self-test the harness (hermetic, no credentials, no network):

```bash
for t in acceptance/test_*.py acceptance/run_acceptance.py; do
  python3 "$t" >/dev/null && echo "$t ✅" || echo "$t ❌"
done
```

## 7. Installation

The harness is pure Python standard library — **zero runtime dependencies**.

**Today (PyPI not yet live):**

```bash
# From the tagged GitHub release:
pip install git+https://github.com/TokonoMix/agents-never-sleep@v1.0.0

# Or from a checkout (editable, to hack on it):
git clone https://github.com/TokonoMix/agents-never-sleep
cd agents-never-sleep
pip install .          # or: pip install -e .
```

**Once published to PyPI** (publish is a pending, deliberate release step — not yet available):

```bash
pip install agents-never-sleep      # ← will work after the PyPI publish; not yet
```

Either install puts two console scripts on PATH: `ans` (= `python3 -m agents_never_sleep.run`, the
per-ticket loop) and `ans-run` (the preflight launcher). A checkout also works without installing —
run `bin/ans-run` and `python3 -m agents_never_sleep.run` directly (set `PYTHONPATH` to the skill root
for the latter).

> **Migration note (pre-1.0 → 1.0):** the import package was renamed `harness` → `agents_never_sleep`.
> A back-compat `harness` shim keeps the old form working (`import harness`, `python3 -m harness.run`,
> `-m harness.enforce`) **through all of 1.x** — it emits one `DeprecationWarning` and is removed in
> 2.0. New code should use `agents_never_sleep`.

## 8. Quick Start

Five minutes from zero to a first unattended run.

1. **Install** (above) — `pip install git+https://github.com/TokonoMix/agents-never-sleep@v1.0.0`.
2. **Understand the contract:** unattended, the agent only ever **PROCEEDs** (assume + log + continue,
   reversibly), **PARKs** (defer this one ticket, keep going), or **HALTs** (only on irreversible
   danger). It never **ASKs** — there's nobody to answer. PARK keeps the run moving; that's the whole
   point.
3. **Write a few tickets** as `.md` files in a directory (see §6 for the format). The body is the only
   required content; the harness auto-classifies blast radius.
4. **First (interactive) run** to create the per-project config via the wizard, then drive the loop:

   ```bash
   cd /path/to/project
   python3 -m agents_never_sleep.run next     --repo . --tickets ./backlog
   #   …implement the ticket it hands you…
   python3 -m agents_never_sleep.run complete --repo . --attempted "what you did"
   #   …repeat until DRAINED.
   ```

5. **Integrate / go unattended:** install the Claude Code enforcement hooks (opt-in, `hooks/README.md`)
   so the contract is enforced structurally, then launch detached through `ans-run` (§9). For other
   platforms, see `hooks/platforms/README.md`.
6. **Read the morning report** (`python3 -m agents_never_sleep.run report --repo .`): done & trusted,
   needs-daylight-review, parked, blocked, blind spots.

## 9. Integration

ANS composes with coding agents — it is the governor, they are the worker. There are three distinct
ways a platform plugs in. **Be precise about which:** *live-verified*, *built-to-contract*, or
*portable preset*.

- **Hook-enforced platforms** (the enforcement matrix in §4 / the table below) — the never-ASK /
  deny-irreversible / never-stop guarantees are wired into the platform's native hook system from one
  shared decision core (`agents_never_sleep/enforce.py`). **Claude Code is live-verified;** Gemini /
  Codex / Copilot / Cursor / Windsurf are **built to each platform's documented hook contract** (run
  `acceptance/` on the real tool to promote a cell).
- **Launcher-preset platforms** — selected via `--agent <preset>` in `bin/ans-run`, with autonomy
  flags confirmed once by a human. The shipped preset map (`agents_never_sleep/agent_clis.py`) keeps
  the autonomy flag and what it grants explicit:

  | CLI | unattended invocation | the autonomy flag grants |
  |---|---|---|
  | Claude Code | `claude -p --permission-mode acceptEdits` | file edits auto-approved; shell/network stay gated |
  | OpenAI Codex | `codex exec --sandbox workspace-write` | edits/commands inside the workspace sandbox |
  | Gemini | `gemini --yolo -p` | EVERYTHING — run in a container/throwaway checkout |
  | GitHub Copilot | `copilot --allow-all-tools -p` | everything (required for programmatic `-p`) |

- **Portable SKILL.md platforms** — OpenHands, CI/CD pipelines (GitHub Actions, etc.), and any of the
  30+ tools that read the open `SKILL.md` standard. There is **no bespoke enforcement adapter** for
  these in 1.0; ANS runs via the portable skill contract + the launcher preset, and any guarantee the
  host can't enforce natively is surfaced as a loud **BLIND SPOT** in the morning report — never a
  silent gap.

**Aider** is a launcher-preset/**wrapper** adapter (`agents_never_sleep/aider_launcher.py`): Aider
0.86.2 has no hook/plugin API, so the guarantees are approximated with launch flags (`--yes-always`,
`stdin < /dev/null`, `--no-suggest-shell-commands`), git-revert reversibility, and the SKILL.md prose
contract. **Honest caveat:** a 2026-06-28 smoke-test showed Aider can hang on a network/OAuth wait
that stdin redirection does not defuse, so the Aider preset **requires** a hard wall-clock timeout
(kill → PARK) and a pre-flight that a model + key are configured. It is built-to-contract, **not**
live-verified to the standard of the hook-enforced platforms.

**CI/CD:** run `ans-run` as a step (or the `next`/`complete` loop directly) as the job's user; gate
on `ans-run --check`; the working-tree flock makes concurrent jobs safe.

### Enforcement capability matrix

| Platform | deny-irreversible | never-stop | never-ASK | status |
|---|:---:|:---:|:---:|---|
| **Claude Code** | ✅ | ✅ | ✅ | **live-verified** |
| **GitHub Copilot CLI** | ✅ | ✅ | ✅ | built-to-contract |
| **Gemini CLI** | ✅ | ✅ | 🟡 prose | built-to-contract |
| **OpenAI Codex CLI** | ✅ | ✅ | 🟡 prose | built-to-contract |
| **Cursor** | ✅ | 🟡 prose | 🟡 prose | built-to-contract |
| **Windsurf** | ✅ | 🟡 prose | 🟡 prose | built-to-contract |

✅ = the platform's native hook enforces the guarantee at the tool layer. 🟡 prose = the platform
exposes **no native hook** for that guarantee (a limitation of the host CLI, not of ANS) → the skill
falls back to the SKILL.md written contract and reports any residual gap as a loud BLIND SPOT.
**Only Claude Code is live-verified on the real tool** (`capabilities.py: LIVE_VERIFIED`); the other
five are built to the platform's documented hook contract and verified by the hermetic test suite —
run `acceptance/` there to promote a cell.

Two further built-to-contract adapters ship under `hooks/platforms/` — **Crush** and **OpenCode**
(deny-irreversible native, never-stop / never-ASK in the prose-fallback class, same as Cursor/Windsurf;
OpenCode has a documented caveat that subagent/task-tool calls bypass the deny hook). An internal
**Hermes** in-process adapter also exists. None of these are live-verified yet.

## 10. Best Practices

- **Backlog shape.** Independent tickets parallelize cleanly across the run; coupled tickets that
  share an interface should name the interface explicitly (or Hard-PARK the interface decision so it
  isn't guessed differently by two tickets).
- **When to PARK vs PROCEED.** PROCEED only when the choice is *locally reversible and isolated*
  (naming, internal structure, equivalent local implementations). Hard-PARK anything in the
  high-blast-radius classes (schema/migration, auth/tenant boundary, money, public API, cross-ticket
  interface, unclear requirement meaning). When genuinely unclassifiable → PARK.
- **Fresh session per N for long backlogs.** A single agent session degrades as it accumulates
  context (empirically around ticket ~19 it starts deferring large work and losing earlier
  constraints). The *harness state* never degrades — each `next`/`complete` is a fresh subprocess —
  but the driving agent context does. For long, independent backlogs set
  `launcher.fresh_session_every: N` (opt-in, default 0/off) so a fresh agent session takes over every
  N tickets and re-reads the durable state, giving ticket 40 the same quality as ticket 1. Never use a
  mid-task %-compaction trigger — it summarizes lossily, busts the prompt cache, and drops design
  constraints.
- **Council cadence.** When the advisory council is enabled, the default caps are sized for ~3 calls
  per ticket (plan / mid / diff review). Per-call review on every change is possible but only worth it
  when explicitly requested, given the per-night euro and call caps. Always report the real charged
  cost (`--council-cost`) so the spend brake stays accurate.

## 11. FAQ

**Does ANS replace Claude Code / Codex / Cursor / Aider?**
No. ANS is a layer *above* them. They are the worker that writes the code; ANS governs how that worker
behaves across a long unattended run. It complements your coding agent, it does not compete with it —
and it is not a model or an IDE.

**Does it only work overnight?**
No. "Overnight" is the obvious case, but it works just as well during the day — hand off the backlog
and do other work while it runs, without watching every step.

**Does it need an LLM API key of its own?**
No. The harness is provider-neutral stdlib Python. The *agent* you drive has whatever credentials it
already uses. The optional review council needs the Tokonomix gateway (or your own provider keys); the
DIY path stays fully functional without it.

**What happens if it can't undo something?**
It doesn't get there. Deny-hooks block irreversible/outward actions at the source (force-push, remote
branch deletes, destructive SQL, secret deletion, disk wipes). If there's no reversibility safety net
at all and none creatable, the run HALTs rather than proceed.

**Can I run two at once on the same repo?**
The launcher's atomic working-tree lock yields exactly one winner per working tree. For intentionally
disjoint worktrees, opt out with `ANS_RUN_NO_LOCK=1`.

### Limitations (read this)

ANS is a governance layer, not a correctness oracle. Concretely:

- **It does not guarantee the code is correct.** The deterministic gate (your test suite) is the
  **only HARD gate**, and ANS does not replace it — regression-catching is exactly your tests' job.
  What ANS adds is orthogonal: it governs *whether an autonomous agent should have touched a given
  surface at all*, and keeps every change it does make reversible.
- **The review council is advisory.** It can raise concerns and withhold the "trusted" stamp
  (`DONE_LOW_CONFIDENCE` + NEEDS DAYLIGHT REVIEW), but it never blocks the run and never reverts.
  Model agreement is not correctness — frontier models share training data and can be uniformly wrong.
- **PARK can defer real work.** A run that parks heavily is honest about it (LOW-YIELD flag, ranked
  report), but you can still come back to a night where most tickets are waiting on your decisions.
- **A wrong PROCEED assumption is possible.** Blast-radius tiering reduces the odds, but a misjudged
  PROCEED can be wrong. **This is precisely why every PROCEED change is built to be reversible** —
  git-backed snapshot/revert and every assumption committed — while the genuinely irreversible
  operations are blocked outright by deny-hooks (they HALT). So a wrong call in the night is a
  five-minute daylight revert, not a disaster.
- **Cross-platform enforcement is live-verified only on Claude Code.** Everywhere else it is built to
  the platform's documented hook contract and hermetically tested, but not yet confirmed on the real
  tool.

## 12. Benchmarks — methodology, not claimed results

> **Honesty note:** the autonomy metrics below are a **reproducible methodology**, not results we are
> claiming. Most are **not yet measured**. This section describes *how to measure* unattended-run
> autonomy and the harness to do it. When we run them for real, results will go in a clearly-dated,
> reproducible appendix with the exact setup — never inline as a bare number.

The metric of interest is an **autonomy-index** — a function of:

- **continuous runtime** without a human touch,
- **tickets completed** per run / per session,
- **human interruptions** (target: 0),
- **recovery after failure** (does a red gate / crash / stale heartbeat resume cleanly?),
- **unfinished tickets** (parked + blocked, with reasons).

**Measurement procedure:** run a fixed, controlled backlog twice — once with a normal agent, once with
ANS — on the same repo + gate, and record the five quantities above. The reproducible harness lives in
`acceptance/` (hermetic `test_*.py` + `run_acceptance.py`, exit 0 = green), which exercises the loop
end-to-end with a deterministic worker.

**What each metric does and doesn't prove:** continuous runtime and zero-interruption show the
never-stop/never-ASK contract held; tickets-completed and unfinished-tickets show *throughput vs
deferral* (a high park rate is honest, not necessarily a win); recovery-after-failure shows the
durability spine works. None of these is a code-correctness measure — that is the gate's job, and it is
out of scope for an autonomy benchmark.

A controlled "normal-agent vs ANS on a backlog" comparison is scoped as the **first reproducible
experiment** (tracked internally as Paperclip `18eee818`); it will be folded in here *when run*, with
its setup, not before.

## 13. Roadmap

Direction, not promises. The current published state is the baseline.

- **PyPI publish.** 1.0.0 is distributed via the GitHub release today; a bare
  `pip install agents-never-sleep` becomes available once the package is published to PyPI (a
  deliberate, separate release step).
- **More live-verified platforms.** Today only Claude Code is live-verified. Gemini / Codex / Copilot
  / Cursor / Windsurf are built-to-contract; promoting each to live-verified is a ~5-minute smoke-test
  on the real tool (`hooks/platforms/README.md`). Aider (wrapper preset) hardening — particularly the
  network/OAuth hang — is on the same track.
- **Run the benchmark methodology for real** (§12) and publish a dated, reproducible appendix.
- **Deprecation cleanup:** the `harness` back-compat shim is removed in 2.0; `agents_never_sleep` is
  the going-forward import name.

The exact, checkable surface-stability policy is in `SEMVER.md`; the per-version record is in
`CHANGELOG.md`.

---

## Layout

```
SKILL.md                     the portable skill (read by the agent)
AGENTS.md                    router for file-based agents
bin/ans-run                  launcher: pre-token GO/NO-GO preflight + atomic working-tree lock
agents_never_sleep/          stdlib-Python engine (state machine, gates, driver, council, …)
  enforcement.py             shared cross-platform decision core
  enforce.py                 cross-platform hook dispatcher
  capabilities.py            per-platform capability matrix + degradation reporting
harness/                     back-compat shim for the old `harness` import name (removed in 2.0)
hooks/                       Claude bash hooks + platforms/ config snippets
acceptance/                  hermetic acceptance tests (run each test_*.py; exit 0 = green)
references/                  design docs
```

## License

MIT — see `LICENSE`.
