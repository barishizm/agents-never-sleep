# Aider enforcement adapter (wrapper / launch-preset)

Aider (0.86.2) has **no hook / plugin / event API of any kind** — there is no pre-execution
seam to deny on. So Aider is ANS's first **wrapper-shaped** adapter: a hardened launch preset
+ git-reversibility + the prose contract, **not** a hook dispatcher. It does **not** go through
`enforce.py`. Aider is also the first platform where **deny-irreversible is not native** — it
breaks the old "deny-irreversible works on every platform" invariant.

## Capability matrix row — all three soft-enforced

| Guarantee | Status | How (and the residual) |
|---|---|---|
| deny-irreversible | 🟡 soft | `--no-suggest-shell-commands` + never wiring `--test-cmd`/`--auto-test`/`--lint-cmd` closes the LLM-suggested shell and the operator-cmd shell paths. **Residual hole:** `cmd_test`/`cmd_run` (`commands.py`) run shell with no confirm and no hook — un-interceptable. Recovery = git-revert to the captured pre-SHA. Reported as a BLIND SPOT. |
| never-stop | 🟡 soft (structurally strong) | aider is one-shot in `--message` mode (`run()` returns after one turn); continuation is the OUTER ANS loop, not a stop hook. |
| never-ASK | 🟡 soft (structurally strong) | `--yes-always` auto-answers prompts; `stdin < /dev/null` makes any unanticipated prompt EOF to a clean exit. Aider structurally cannot hang waiting for a human. |

never-stop / never-ASK are *soft-but-structurally-strong*; deny-irreversible is the genuine
🟡 with a residual hole.

## The launch preset

ANS drives aider as a subprocess, **once per ticket**. The canonical argv is built by
`agents_never_sleep.aider_launcher.build_aider_argv()`:

```bash
# what the builder produces (run with stdin redirected from /dev/null):
aider --message-file .unattended/ticket-<id>.prompt \
      --yes-always --no-detect-urls --no-suggest-shell-commands \
      --no-auto-test --no-auto-lint <files...> < /dev/null
```

Per ticket the ANS driver:
1. records the **pre-invocation HEAD SHA**;
2. runs the preset above;
3. runs **its own** deterministic gate (tsc / tests) — never aider's;
4. on gate failure: `git reset --hard <pre-SHA>` (revert the whole ticket — note one
   `--message` can emit multiple commits, so revert to the captured SHA, never `HEAD~1`).

Keep aider's **auto-commit ON** (the default) — it is the reversibility anchor.

## Blast warnings (carry these)

- **NEVER** wire `--test-cmd` / `--auto-test` / `--lint-cmd` (or let the prompt use `/run`,
  `/test`): they run arbitrary shell with no confirm and no hook. `build_aider_argv` refuses
  these flags via `extra`, but an operator config could still set them — a hard prohibition.
- Aider needs its **own LLM key**; that spend is **outside** ANS's billing/guardrails.
- Run under a **sandbox** for egress control (startup version-check / URL-scrape are not
  ANS-interceptable; the preset passes `--no-detect-urls`).
- Aider passes git `--no-verify` by default (`--git-commit-verify` default false), so a repo
  pre-commit hook would **not** fire on aider's commits — a `decide()` pre-commit bridge is a
  *future* option, not the v1.1 adapter.

## Verification status

Built to the documented behavioral contract + hermetically tested
(`acceptance/test_aider_launcher.py`). **Not** in `LIVE_VERIFIED` — the live smoke-test (run a
real unattended aider ticket; confirm an irreversible command can't escape and a question
doesn't hang) is Mes-side.
