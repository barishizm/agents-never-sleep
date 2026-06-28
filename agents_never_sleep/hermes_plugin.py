"""ANS in-process enforcement for Hermes (hermes-orch-beta, Mes's own orchestrator).

Hermes is an in-process Python orchestrator with a native `pre_tool_call` hook that fires
BEFORE the clarify / inline special-cases on every dispatch path (run_agent.py:9299/9815,
model_tools.py:687). So — unlike the out-of-process dispatcher platforms (enforce.py) — ANS
enforces here by registering a hook that calls the shared `decide()` core DIRECTLY, in
process. This is ANS's first in-process adapter; it reuses only `decide()`, not the
dispatcher's payload-normalize / per-platform emit.

The high-value guard: denying the `clarify` tool preempts Hermes's fail-OPEN clarify-timeout
(cli.py:8655-8664, "the user did not provide a response … use your best judgement and
proceed" = invented consent). Instead of fabricating approval, the action is DENIED and the
ASK_DENY_REASON steers the model to PARK and PROCEED.

Inert unless UE_UNATTENDED=1 (or CLAUDE_UNATTENDED=1), so interactive Hermes sessions are
untouched. The thin Hermes plugin entrypoint lives in hooks/platforms/hermes/__init__.py and
just registers `ans_pre_tool` on the `pre_tool_call` hook.
"""
from __future__ import annotations

import os

from .enforcement import Action, decide

_UNATTENDED_ENV = ("UE_UNATTENDED", "CLAUDE_UNATTENDED")
_MAX_DEPTH = 5  # bounded recursion — Hermes tool args are shallow; cap pathological nesting.


def _unattended(env=None) -> bool:
    env = os.environ if env is None else env
    return any(env.get(k) == "1" for k in _UNATTENDED_ENV)


def _command_blob(args, _depth: int = 0) -> str:
    """Join ALL string leaf values in a tool's args (bounded recursion) into one blob for the
    irreversible-pattern scan. We do NOT key on a fixed set of arg names (command/code/…): a
    Hermes tool could carry its destructive command under a different or nested key, and a miss
    would let it through. Over-matching is the SAFE direction here — a false hit only PARKs the
    action, a miss would execute it. Mirrors enforce.py's `_blob` (the same reason the dispatcher
    joins all values). decide() pattern-matches over the blob."""
    if _depth > _MAX_DEPTH or args is None:
        return ""
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        return " ".join(_command_blob(v, _depth + 1) for v in args.values())
    if isinstance(args, (list, tuple)):
        return " ".join(_command_blob(v, _depth + 1) for v in args)
    return ""


def ans_pre_tool(tool_name, args=None, **_kw):
    """Hermes `pre_tool_call` hook body. Returns a {"action": "block", "message": ...} block
    directive (honoured by get_pre_tool_call_block_message) when ANS's decide() denies — an
    ask-tool (incl. `clarify`) or an irreversible/outward command — else None (allow). Inert
    outside an unattended run. Never raises: enforcement must not wedge Hermes's loop."""
    try:
        if not _unattended():
            return None
        d = decide("pre_tool", tool_name=tool_name, command=_command_blob(args))
        if d.action == Action.DENY:
            return {"action": "block", "message": d.reason}
    except Exception:
        return None  # fail OPEN — a guard bug must never break the orchestrator
    return None
