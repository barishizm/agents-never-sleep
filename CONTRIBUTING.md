# Contributing to agents-never-sleep

Thanks for your interest! This is a platform-neutral skill + Python harness that
runs a coding-agent backlog to completion unattended — PROCEED / PARK / HALT,
never ASK, never irreversible unsupervised.

## Layout

- `SKILL.md` — the agent-facing contract (start here).
- `harness/` — deterministic stdlib engine (state machine, gates, council routing,
  budget gate, ledger, report). No third-party deps; no network/LLM calls — the
  agent makes those.
- `hooks/` — per-platform enforcement (Claude Code / Cursor / Gemini / Codex / …).
- `acceptance/` — the test suite. `python3 acceptance/run_acceptance.py` must end
  `RESULT: ✅ GREEN`.

## Development

```bash
python3 acceptance/run_acceptance.py     # full acceptance — must stay GREEN
python3 acceptance/test_budget.py        # a single suite
```

Pure standard library, Python 3.10+. No build step.

## Pull requests

- Keep the two structural guarantees intact: **never ASK in unattended mode**,
  **never act irreversibly unsupervised**. New code paths must respect them.
- Add/extend acceptance tests for behaviour changes; the suite must stay GREEN.
- Never commit secrets, runtime state (`.unattended/`, `state/`, reports), or real
  credentials. Test fixtures must be obviously fake.
- Surgical, focused changes; match the existing style.

## Publishing

This repo is **generated** from an upstream canonical copy via a one-way mirror — do not
hand-edit it expecting changes to stick, as the next sync overwrites the tree. Land changes
upstream; maintainers publish with a dry-runnable mirror script (diff vs this remote first,
then an explicit, supervised push). Outside contributions are welcomed as PRs and folded in
upstream.

## Security

Report vulnerabilities privately — see [SECURITY.md](./SECURITY.md).

Contributions are licensed under the repo's [MIT license](./LICENSE).
