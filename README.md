# Agents Never Sleep (ANS)

Run a backlog to completion **unattended** — without the run ever soft-halting on a question.
Overnight is the obvious case, but it works just as well **during the day**: hand off the backlog
and carry on with other work while it runs, without watching the process or approving every step. A
portable [Agent Skill](https://www.agensi.io/learn/agent-skills-open-standard)
(`SKILL.md`) plus a small stdlib-Python harness that gives a coding agent: durable per-ticket state,
a concrete **ASK / PARK / HALT** autonomy contract (never block the whole run on one ticket),
deterministic test-gates with a failure taxonomy, git-backed reversibility, attempt/loop caps, an
optional multi-model review council, secret redaction on every write, and a run report.

> The pain it solves: *"the agent stalls on a dumb question and wastes the stretch you weren't
> watching"* — whether that's overnight or the hour you stepped away to do something else.

## The autonomy contract

Three responses to uncertainty — never collapsed:

- **PROCEED** — assume + log + continue (low blast-radius, reversible).
- **PARK** — defer *this* ticket/decision, keep moving to the next. Normal and healthy.
- **HALT** — stop the whole run (only on irreversible danger with no safety net).
- **ASK is forbidden unattended** — there is nobody watching to answer.

This is enforced structurally (not by agent discipline) via opt-in, env-gated hooks.

## Quick start

```bash
# 1. (Claude Code) install the enforcement hooks — opt-in, see hooks/README.md
#    other platforms: hooks/platforms/README.md
# 2. drive the per-ticket loop (the agent IS the worker):
python3 -m harness.run next     --repo <project> --tickets <dir-of-.md-tickets>
python3 -m harness.run complete --repo <project> --attempted "what you did"
#    repeat next/complete until it returns DRAINED/HALTED/LOW_YIELD.
```

`next` hands you exactly one ready ticket (auto-parking ambiguous / high-blast-radius ones) and owns
the never-stop sentinel; `complete` gates + records the outcome. Both echo the resolved repo + tickets
paths so a mis-target is obvious. Operator escapes when a resume gets confused: `reset-attempts <id>`
(clear one ticket's attempt counter) and `reset-spend` (zero the per-night spend accounting). See
`SKILL.md` for the full loop, the council/specialist review flow, and the cost brakes.

## Cross-platform

The harness is provider-neutral Python and runs anywhere. The cross-platform enforcement (never-ASK /
deny-irreversible / never-stop) is wired per platform from one shared decision core
(`harness/enforcement.py`) via `python3 -m harness.enforce <platform> <event>`. (Claude Code *also*
ships a self-contained bash deny-hook, `hooks/deny_irreversible.sh`, as the `bypassPermissions`
backstop — it mirrors the same patterns but does not call the Python core, so it keeps working even
if Python is unavailable.)

| Platform | deny-irreversible | never-stop | never-ASK |
|---|---|---|---|
| Claude Code | ✅ | ✅ | ✅ |
| Gemini CLI | ✅* | ✅* | ⚠️ degraded |
| Codex CLI | ✅* | ✅* | ⚠️ degraded |
| Copilot CLI | ✅* | ✅* | ✅* |
| Cursor | ✅* | ⚠️ degraded | ⚠️ degraded |
| Windsurf | ✅* | ⚠️ degraded | ⚠️ degraded |

**✅ = native + live-verified · ✅\* = native, built to the platform's documented hook contract but
not yet live-verified on the real tool (run `acceptance/` there to promote it) · ⚠️ = no native hook
for this guarantee → falls back to the SKILL.md prose contract AND is surfaced as a run-report BLIND
SPOT, never silent.** Only Claude Code is live-verified today (`capabilities.py: LIVE_VERIFIED`).
Install snippets per platform live in `hooks/platforms/`.

## Layout

```
SKILL.md                     the portable skill (read by the agent)
AGENTS.md                    router for file-based agents
harness/                     stdlib-Python engine (state machine, gates, driver, council, …)
  enforcement.py             shared cross-platform decision core
  enforce.py                 cross-platform hook dispatcher
  capabilities.py            per-platform capability matrix + degradation reporting
hooks/                       Claude bash hooks + platforms/ config snippets
acceptance/                  hermetic acceptance tests (run each test_*.py; exit 0 = green)
references/                  design docs
```

## Tests

```bash
for t in acceptance/test_*.py acceptance/run_acceptance.py; do python3 "$t" >/dev/null && echo "$t ✅" || echo "$t ❌"; done
```

## License

MIT — see `LICENSE`.
