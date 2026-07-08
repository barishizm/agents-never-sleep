"""Tokonomix onboarding gate — the deterministic half of a keyless bootstrap for the review gateway.

The council + specialist reviewers need a tokonomix credential. The config enables them only when one
is present, so if a previously-working key later goes missing (rotated / expired / unset), review
silently turns off — and an unattended night loses ALL multi-model vetting with no signal. This module
makes that gap explicit and, where possible, actionable:

  * INTERACTIVE: surface the keyless onboard handshake (`tokonomix_onboard` -> `tokonomix_onboard_verify`,
    run by the AGENT via MCP — the harness can't call the gateway), then re-probe.
  * UNATTENDED: the verify step needs a human, so onboarding can't run; instead record a graceful
    DEGRADATION blind-spot for the morning report and let the night proceed with review disabled.

It fires ONLY when the project is configured for tokonomix (`integrations.tokonomix.enabled`) but no
live credential is found — i.e. a real, actionable "the key went away" case — so projects that never
wanted tokonomix are never nagged. The harness owns only this decision + directive; the MCP calls are
the agent's, exactly as the council calls are.
"""
from __future__ import annotations

import os

_DEFAULT_CRED_FILE = "~/.tokonomix/credentials.json"

# How to CONNECT the tokonomix MCP server. The onboarding/handshake tools
# (tokonomix_onboard, tokonomix_*) only exist once this server is registered with
# the agent's MCP client — without it the agent knows it needs onboarding but has
# no way to act. One npx line; works in Claude Code, Cursor, Cline, Continue, Zed.
_MCP_INSTALL = (
    "FIRST connect the tokonomix MCP server (its tools won't exist otherwise). "
    "Claude Code: `claude mcp add tokonomix -- npx -y tokonomix-council-mcp`. "
    "Other clients (Cursor/Cline/Continue/Zed): add to the MCP config "
    '`{"mcpServers":{"tokonomix":{"command":"npx","args":["-y","tokonomix-council-mcp"]}}}` '
    "then reload so the tokonomix_* tools load."
)

# Shared keyless-onboard protocol text, consumed by directive() (interactive branch) and by
# first_run_offer() (the keyless-first-run case). Fixes two stale-copy defects: the server is
# BETA-gated on accept_beta_terms (a 400 without it), and the resulting key auto-lands in
# ~/.tokonomix/credentials.json (no env var needed) once the MCP tools reload.
_ONBOARD_PROTOCOL = (
    _MCP_INSTALL + " THEN run the keyless onboarding via MCP. The server is in BETA: "
    "tokonomix_onboard requires accept_beta_terms — first show your human the beta terms "
    "(https://tokonomix.ai/beta) and, ONLY after the human confirms, call tokonomix_onboard(email, "
    "accept_beta_terms=true). It emails a 6-digit code; then call tokonomix_onboard_verify(email, "
    "code). On success the API key is written to ~/.tokonomix/credentials.json (shown once) and is "
    "loaded automatically — no env var needed — after the tools reload. Distinguish the two failure "
    "modes: a 400 asking to accept the beta terms means confirm-and-recall; ANY OTHER error (or if "
    "the email already has an account) means STOP the keyless flow and use an existing key instead "
    "— get one at https://tokonomix.ai/dashboard/keys and set TOKONOMIX_API_KEY (or drop it in "
    "~/.tokonomix/credentials.json). Adding the MCP server surfaces its tools only after a Claude "
    "Code reload/new session, so review activates on the NEXT run, not mid-session."
)


def credential_present() -> bool:
    """Same probe as preflight: a tokonomix credential in env or the well-known creds file. The
    file path can be overridden with TOKONOMIX_CREDS_FILE (keeps the probe testable on any box)."""
    if os.environ.get("TOKONOMIX_API_KEY"):
        return True
    path = os.environ.get("TOKONOMIX_CREDS_FILE", _DEFAULT_CRED_FILE)
    return os.path.exists(os.path.expanduser(path))


def _review_enabled(config: dict) -> bool:
    """True if any tokonomix-credential CONSUMER is enabled (council or specialist review). This is
    the right signal — not `integrations.tokonomix.enabled` — because council.enabled()/specialists
    .enabled() default that sub-key to True, so keying off it would miss a config that enables the
    council without an explicit integrations block (the exact silent blind-spot this gate exists for)
    and would falsely fire when the integration is on but every consumer is off."""
    from . import council, specialists
    return council.enabled(config) or specialists.enabled(config)


def needs_onboarding(config: dict) -> bool:
    """True iff a credential consumer (council/specialists) is enabled but no live credential is
    present — a real, actionable "the key went away" case. Matches exactly when a review would try to
    run and fail; never nags a project with no review enabled."""
    return _review_enabled(config) and not credential_present()


def degradation_note() -> str:
    return ("tokonomix credential missing — multi-model council + specialist review ran DISABLED "
            "this night. Before the next run: connect the tokonomix MCP server "
            "(`claude mcp add tokonomix -- npx -y tokonomix-council-mcp`), then onboard interactively "
            "(tokonomix_onboard -> tokonomix_onboard_verify) OR set TOKONOMIX_API_KEY, to restore vetting.")


def directive(config: dict, *, interactive: bool):
    """The onboarding action to surface, or None when nothing is needed. Interactive => guide the
    keyless onboard; unattended => a graceful-degradation blind-spot (cannot onboard without a human)."""
    if not needs_onboarding(config):
        return None
    if interactive:
        return {
            "action": "onboard",
            "summary": "[onboarding] tokonomix configured but NO credential found — review is OFF",
            "mcp_install": _MCP_INSTALL,
            "protocol": _ONBOARD_PROTOCOL,
        }
    return {
        "action": "degraded",
        "summary": "[onboarding] tokonomix configured but NO credential — review DISABLED this night",
        "blind_spot": degradation_note(),
    }
