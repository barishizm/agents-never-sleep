"""Canonical Aider launch preset for ANS (WRAPPER adapter — Aider has no hook API).

Aider 0.86.2 has no hook / plugin / event API, so the three guarantees cannot be wired
through enforce.py. Instead the adapter is a launch-preset + git-reversibility + prose:

  * never-ASK   — `--yes-always` auto-answers prompts; the caller redirects `stdin < /dev/null`
                  so any unanticipated prompt EOFs to a clean exit (aider can't hang).
  * deny-irreversible (soft) — `--no-suggest-shell-commands` kills the LLM-suggested-shell
                  path; NEVER wiring `--test-cmd`/`--auto-test`/`--lint-cmd` closes the only
                  un-interceptable shell path (cmd_test/cmd_run run shell with no confirm + no
                  hook). Recovery is git-revert (below). The residual hole is reported as a
                  morning-report BLIND SPOT.
  * never-stop (soft) — aider is one-shot in `--message` mode (run() returns after one turn);
                  continuation is the OUTER ANS loop re-invoking aider per ticket. BUT preset
                  flags alone do NOT prevent hangs: a live smoke-test (2026-06-28) showed aider
                  can hang on a NETWORK wait that stdin=/dev/null does not defuse — keyless it
                  opens an OAuth browser onboarding ("Waiting up to 5 minutes…"), and an
                  invalid/slow key stalls the LLM call. So never-stop for aider REQUIRES the
                  caller to (a) run under a hard wall-clock timeout (kill → PARK) and (b)
                  pre-flight that a model + key are configured. RECOMMENDED_TIMEOUT_SECONDS below.

Reversibility: aider auto-commits each change. The ANS driver records the pre-invocation HEAD
SHA and reverts to THAT on a gate failure (never `HEAD~1` — one `--message` can emit multiple
commits: the edit plus a separate "Ran the linter" commit). See hooks/platforms/aider/README.md.
"""
from __future__ import annotations

# Flags that must NEVER be added — they run arbitrary shell with no confirm and no hook
# (commands.py cmd_test/cmd_run). The preset refuses them even via `extra`.
FORBIDDEN_FLAGS = frozenset({"--test-cmd", "--auto-test", "--lint-cmd", "--auto-lint"})

# Hard wall-clock cap the CALLER must enforce around the aider subprocess (e.g. `timeout`,
# subprocess timeout=). Live smoke-test finding: aider has network/onboarding hang paths that
# no flag closes, so this kill-on-timeout is how never-stop is actually enforced for aider.
RECOMMENDED_TIMEOUT_SECONDS = 600

# The hardened base flags every unattended aider invocation carries.
BASE_FLAGS = (
    "--yes-always",            # never-ASK: auto-answer prompts
    "--no-detect-urls",        # no network URL-scraping at startup (not ANS-interceptable)
    "--no-suggest-shell-commands",  # kill the LLM-suggested-shell path
    "--no-auto-test",          # never run an operator test command (un-interceptable shell)
    "--no-auto-lint",          # never run an operator lint command (un-interceptable shell)
    "--no-show-model-warnings",  # smoke-test: the model-warnings prompt otherwise stalls headless
)


def build_aider_argv(message_file, files=None, *, model=None, extra=None):
    """Build the hardened `aider` argv for one unattended ticket.

    `message_file` is the per-ticket prompt file (aider reads it via --message-file; aider
    takes the prompt by FILE, not as a positional — positionals are filenames). `files` are
    the files to add to the chat. `model` optionally pins the LLM. `extra` are additional
    flags (a forbidden flag raises). The caller MUST run this with `stdin` redirected from
    /dev/null and capture the pre-invocation HEAD SHA for reversibility.
    """
    if not message_file:
        raise ValueError("aider preset requires a --message-file path")
    argv = ["aider", "--message-file", str(message_file), *BASE_FLAGS]
    if model:
        argv += ["--model", str(model)]
    for flag in extra or []:
        if flag in FORBIDDEN_FLAGS:
            raise ValueError(
                f"refused forbidden aider flag {flag!r}: runs arbitrary shell with no confirm "
                "and no hook (deny-irreversible cannot see it)")
        argv.append(str(flag))
    for f in files or []:
        argv.append(str(f))
    return argv
