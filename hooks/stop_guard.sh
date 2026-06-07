#!/usr/bin/env bash
# Stop-hook — prevent a PREMATURE stop while there is still unattended work to do.
#
# A Stop hook fires when the agent is about to end its turn. During an unattended run we only want
# the turn to end when the backlog is genuinely drained — otherwise the agent "soft-halts". This
# guard blocks the stop while a run-incomplete sentinel exists, and (critically) honours
# stop_hook_active so it can never create an infinite stop loop.
#
# Env-gated to CLAUDE_UNATTENDED=1; inert in normal interactive sessions.
set -euo pipefail

if [[ "${CLAUDE_UNATTENDED:-}" != "1" ]]; then
  exit 0
fi

payload="$(cat)"

# Never loop: if we already blocked once this turn, allow the stop.
already="$(printf '%s' "$payload" | python3 -c 'import json,sys;
try: print("1" if json.load(sys.stdin).get("stop_hook_active") else "0")
except Exception: print("0")')"
if [[ "$already" == "1" ]]; then
  exit 0
fi

# The orchestrator writes this sentinel at run start and removes it when the backlog is drained.
sentinel="${UE_RUN_INCOMPLETE:-$PWD/.unattended/run-incomplete}"
if [[ -f "$sentinel" ]]; then
  cat <<'JSON'
{"decision":"block","reason":"agents-never-sleep: backlog not drained — continue with the next ticket (PARK ambiguous/high-blast-radius items, do not stop or ask). When every ticket is in a terminal state, remove .unattended/run-incomplete and write the morning report."}
JSON
  exit 0
fi

exit 0
