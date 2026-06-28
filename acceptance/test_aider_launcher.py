#!/usr/bin/env python3
"""Aider wrapper-adapter test — proves the hardened launch preset is correct without running
aider. Aider has no hook, so there is no dispatcher path to exercise; instead we assert the
argv the wrapper produces (never-ASK + the deny-irreversible PREVENTION flags) and the matrix
row + honesty flags. Exit 0 = GREEN.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep import capabilities as C  # noqa: E402
from agents_never_sleep.aider_launcher import build_aider_argv, FORBIDDEN_FLAGS  # noqa: E402


def main() -> int:
    failures = []

    argv = build_aider_argv(".unattended/ticket-7.prompt", ["app.ts", "lib/x.ts"])

    # never-ASK + deny-irreversible-PREVENTION + the smoke-test headless flags must be present
    for flag in ("--yes-always", "--no-suggest-shell-commands", "--no-auto-test",
                 "--no-auto-lint", "--no-detect-urls", "--no-show-model-warnings"):
        if flag not in argv:
            failures.append(f"[aider] preset missing hardening flag {flag}")

    # the caller-enforced wall-clock cap (how never-stop is enforced for aider) is exported
    from agents_never_sleep.aider_launcher import RECOMMENDED_TIMEOUT_SECONDS
    if not isinstance(RECOMMENDED_TIMEOUT_SECONDS, int) or RECOMMENDED_TIMEOUT_SECONDS <= 0:
        failures.append("[aider] RECOMMENDED_TIMEOUT_SECONDS must be a positive int")

    # the prompt goes via --message-file (NOT a positional), argv[0] is aider
    if argv[0] != "aider":
        failures.append(f"[aider] argv[0] should be 'aider': {argv[0]!r}")
    if "--message-file" not in argv or argv[argv.index("--message-file") + 1] != ".unattended/ticket-7.prompt":
        failures.append(f"[aider] prompt must be wired via --message-file: {argv}")

    # the operator test/lint command flags must NEVER appear (un-interceptable shell)
    for bad in ("--test-cmd", "--lint-cmd", "--auto-test", "--auto-lint"):
        if bad in argv:
            failures.append(f"[aider] forbidden flag {bad} must never be in the preset: {argv}")

    # files are appended (added to the chat)
    for f in ("app.ts", "lib/x.ts"):
        if f not in argv:
            failures.append(f"[aider] file {f} should be appended to argv")

    # a forbidden flag via `extra` must RAISE (refuse the un-interceptable shell path)
    for bad in sorted(FORBIDDEN_FLAGS):
        try:
            build_aider_argv("p.prompt", extra=[bad])
            failures.append(f"[aider] extra={bad!r} should have raised")
        except ValueError:
            pass

    # missing message_file must raise (aider needs the prompt by file)
    try:
        build_aider_argv("", ["a.ts"])
        failures.append("[aider] empty message_file should raise")
    except ValueError:
        pass

    # model pin is wired when given
    argv_m = build_aider_argv("p.prompt", model="openrouter/anthropic/claude-sonnet-4-6")
    if "--model" not in argv_m or argv_m[argv_m.index("--model") + 1] != "openrouter/anthropic/claude-sonnet-4-6":
        failures.append(f"[aider] model pin not wired: {argv_m}")

    # capability matrix + honesty: aider breaks the deny-everywhere invariant (all soft),
    # wrapper shape, not a dispatcher platform, not live-verified, drift-guard recorded
    if C.guarantees("aider") != {C.DENY_IRREVERSIBLE: C.DEGRADED, C.NEVER_STOP: C.DEGRADED,
                                 C.NEVER_ASK: C.DEGRADED}:
        failures.append(f"[aider] matrix row should be all-soft: {C.guarantees('aider')}")
    if C.is_native("aider", C.DENY_IRREVERSIBLE):
        failures.append("[aider] deny-irreversible must NOT be native (no hook API)")
    if C.adapter_shape("aider") != C.WRAPPER:
        failures.append("[aider] adapter shape should be wrapper")
    if "aider" in C.dispatcher_platforms():
        failures.append("[aider] wrapper adapter must NOT be a dispatcher platform")
    if len(C.degradation_notes("aider")) != 3:
        failures.append(f"[aider] should have 3 degradation notes (all soft): {C.degradation_notes('aider')}")
    if "aider" in C.LIVE_VERIFIED:
        failures.append("[aider] must NOT be live-verified until Mes runs the smoke-test")
    if "contract" not in C.hook_contract("aider"):
        failures.append("[aider] missing a recorded behavioral-contract version")

    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — Aider wrapper adapter not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — Aider preset carries the hardening flags, refuses the un-interceptable "
          "shell flags, wires the prompt via --message-file; matrix (all-soft) + honesty flags correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
