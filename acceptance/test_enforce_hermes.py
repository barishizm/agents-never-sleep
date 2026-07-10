#!/usr/bin/env python3
"""Hermes in-process plugin test — proves agents_never_sleep.hermes_plugin.ans_pre_tool emits
the correct {"action":"block",...} directive from Hermes's pre_tool_call payload (the achievable
hermetic bar; a live smoke-test on real Hermes is maintainer-side — systemctl --user is unreachable here).

Hermes is the first IN-PROCESS adapter: it does NOT go through enforce.py's stdin→stdout
dispatcher, so this test calls the hook callback directly. Exit 0 = GREEN.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep import capabilities as C  # noqa: E402
from agents_never_sleep.hermes_plugin import ans_pre_tool  # noqa: E402


def _unattended_env():
    """Set UE_UNATTENDED for the duration; the plugin reads os.environ."""
    os.environ.pop("CLAUDE_UNATTENDED", None)
    os.environ["UE_UNATTENDED"] = "1"


def main() -> int:
    failures = []
    saved = dict(os.environ)
    try:
        _unattended_env()

        # deny-irreversible: a force-push (and other irreversible commands) must BLOCK
        for cmd in ("git push --force origin main", "rm -rf /", "vault kv delete secret/x",
                    "drop table users"):
            r = ans_pre_tool("terminal", {"command": cmd})
            if not (isinstance(r, dict) and r.get("action") == "block"):
                failures.append(f"[hermes] irreversible {cmd!r} should block: {r!r}")
        # the block message must carry a reason
        r = ans_pre_tool("terminal", {"command": "git push --force origin main"})
        if "irreversible" not in (r or {}).get("message", ""):
            failures.append(f"[hermes] block message should name the irreversible action: {r!r}")

        # never-ASK: the `clarify` tool must BLOCK with the PARK/PROCEED steer (preempting the
        # fail-open clarify-timeout) — the headline guard.
        r = ans_pre_tool("clarify", {"question": "which approach should I take?",
                                      "choices": ["a", "b"]})
        if not (isinstance(r, dict) and r.get("action") == "block"):
            failures.append(f"[hermes] clarify should block (never-ASK): {r!r}")
        if "PARK" not in (r or {}).get("message", "") or "PROCEED" not in (r or {}).get("message", ""):
            failures.append(f"[hermes] clarify block should steer PARK/PROCEED: {r!r}")

        # benign command -> ALLOW (None)
        for cmd in ("ls -la", "git status", "npm test", "git reset --hard HEAD"):
            r = ans_pre_tool("terminal", {"command": cmd})
            if r is not None:
                failures.append(f"[hermes] benign {cmd!r} should allow (None): {r!r}")

        # a tool with no command string -> ALLOW (deny-irreversible is command-pattern based)
        r = ans_pre_tool("memory", {"note": "remember this"})
        if r is not None:
            failures.append(f"[hermes] non-command tool should allow (None): {r!r}")

        # the `code` arg key is also recognised as a command
        r = ans_pre_tool("code_execution", {"code": "rm -rf /home"})
        if not (isinstance(r, dict) and r.get("action") == "block"):
            failures.append(f"[hermes] irreversible via `code` arg should block: {r!r}")

        # HARDENING (consensus 88eca593): a destructive command under a DIFFERENT or NESTED
        # arg key must STILL block — we scan all string leaves, not a fixed key allowlist
        # (a miss would execute it; over-matching only PARKs).
        for label, a in (
            ("unknown-key", {"sql": "drop table users"}),
            ("nested-dict", {"params": {"shell": "git push --force origin main"}}),
            ("nested-list", {"steps": ["echo hi", "vault kv delete secret/x"]}),
        ):
            r = ans_pre_tool("some_tool", a)
            if not (isinstance(r, dict) and r.get("action") == "block"):
                failures.append(f"[hermes] irreversible via {label} should block: {r!r}")
        # a benign nested payload with no destructive text still allows
        r = ans_pre_tool("some_tool", {"params": {"path": "src/app.ts", "mode": "read"}})
        if r is not None:
            failures.append(f"[hermes] benign nested payload should allow (None): {r!r}")

        # inert when NOT unattended: even a force-push must pass through (no interference in
        # interactive Hermes sessions)
        os.environ.pop("UE_UNATTENDED", None)
        os.environ.pop("CLAUDE_UNATTENDED", None)
        r = ans_pre_tool("terminal", {"command": "git push --force origin main"})
        if r is not None:
            failures.append(f"[hermes] should be inert when not unattended: {r!r}")
        r = ans_pre_tool("clarify", {"question": "x"})
        if r is not None:
            failures.append(f"[hermes] clarify should be inert when not unattended: {r!r}")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    # capability matrix + honesty: hermes row, adapter shape, drift-guard, not-live-verified
    if C.guarantees("hermes") != {C.DENY_IRREVERSIBLE: C.NATIVE, C.NEVER_STOP: C.DEGRADED,
                                  C.NEVER_ASK: C.NATIVE}:
        failures.append(f"[hermes] matrix row wrong: {C.guarantees('hermes')}")
    if C.adapter_shape("hermes") != C.IN_PROCESS:
        failures.append("[hermes] adapter shape should be in_process")
    if "hermes" in C.dispatcher_platforms():
        failures.append("[hermes] in-process adapter must NOT be a dispatcher platform")
    notes = C.degradation_notes("hermes")
    if len(notes) != 1 or "never-stop" not in notes[0]:
        failures.append(f"[hermes] should have exactly one never-stop blind-spot: {notes}")
    if "hermes" in C.LIVE_VERIFIED:
        failures.append("[hermes] must NOT be live-verified until the maintainer runs the smoke-test")
    if "contract" not in C.hook_contract("hermes"):
        failures.append("[hermes] missing a recorded hook-contract version")

    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — Hermes in-process adapter not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — Hermes pre_tool_call hook denies irreversible + clarify (never-ASK), "
          "allows benign, inert when not unattended; matrix + honesty flags correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
