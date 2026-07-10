#!/usr/bin/env bash
# Public-surface content gate (security remediation, branch fix/public-surface-scrub).
#
# Self-contained redaction lint for the PUBLIC agents-never-sleep repo. Greps every git-tracked
# file for a small, conservative set of unambiguously-internal tokens (the maintainer's real
# name, internal infra paths/product names, internal ticket IDs, and obviously-real-looking
# secret shapes) and FAILS if any hit lands outside the narrow, documented allowlists below.
#
# This replaces a previously broken CI step that shelled out to
# `site-src/tools/redact_lint.py` — a script that only exists in the private repo, so that gate
# never actually ran here. Deliberately plain bash + `git grep` (no Python, no third-party
# tooling, no network) so this script cannot itself go stale/missing the same way.
#
# Exit 0 = no hits (gate passes). Exit 1 = at least one hit (gate fails; file:line printed).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

SELF="scripts/redact_lint.sh"
hits=0

# fail_pattern <label> <regex> <filter_out_regex_or_empty> -- <extra pathspec excludes...>
# `filter_out_regex`, if non-empty, drops matched LINES that are known, narrowly-scoped false
# positives (documented at each call site) — it never widens what counts as a hit, only excludes
# specific already-reviewed non-leaks.
fail_pattern() {
  local label="$1" pattern="$2" filter="$3"; shift 3
  local out
  out="$(git grep -nE "$pattern" -- . ":!${SELF}" "$@" 2>/dev/null || true)"
  if [ -n "$filter" ] && [ -n "$out" ]; then
    out="$(printf '%s\n' "$out" | grep -Ev "$filter" || true)"
  fi
  if [ -n "$out" ]; then
    echo "FORBIDDEN PATTERN [$label]: $pattern"
    echo "$out"
    echo
    hits=$((hits + 1))
  fi
}

# --- the maintainer's real first name ----------------------------------------------------------
fail_pattern "maintainer-name" '\bMes\b' ''

# --- internal server path/username -------------------------------------------------------------
fail_pattern "internal-server-path" '/home/claude' ''

# --- internal orchestrator product name/path ---------------------------------------------------
fail_pattern "internal-orchestrator-path" '/opt/hermes-orch-beta' ''
fail_pattern "internal-orchestrator-name" 'hermes-orch-beta' ''

# --- internal InterIP web/publish path (/interip/ and the /internip/ misspelling) --------------
fail_pattern "internal-web-path" '/intern?ip/' ''

# --- internal ticket IDs -------------------------------------------------------------------------
# Scoped to the public doc/config surface (CHANGELOG.md, SEMVER.md, README*, docs/, hooks/,
# pyproject.toml, .gitignore, workflows, this script). `agents_never_sleep/` and `acceptance/` are
# EXCLUDED from this specific pattern: INT-<n> there is either a functional engineering comment
# (development history, not a maintainer-identity/infra leak) or literal test-fixture data
# (e.g. acceptance/test_paperclip.py and acceptance/test_classify_override_wiring.py construct
# real `Ticket(id="INT-1781", ...)` objects to exercise the ticket parser) — rewriting those would
# break the acceptance suite for no security benefit. A future audit can narrow this exclusion
# deliberately if a stricter code-comment gate is wanted; do it explicitly, not by widening this
# regex.
fail_pattern "internal-ticket-id" 'INT-[0-9]+' '' ':!agents_never_sleep' ':!acceptance'

# --- past-incident phrase (avoid re-describing this remediation on the public surface) ----------
fail_pattern "incident-phrase" 'security purge' ''

# --- secret shapes --------------------------------------------------------------------------------
# acceptance/test_redact.py and acceptance/test_keysource.py intentionally contain obviously-fake
# token fixtures (e.g. ghp_ABCDEF..., AKIAIOSFODNN7EXAMPLE, a placeholder PEM block) to exercise
# the redaction code paths themselves — excluded here by design, not a leak.
FIXTURE_EXCLUDES=(":!acceptance/test_redact.py" ":!acceptance/test_keysource.py")
# `pcp_id_by_ticket` is a real, load-bearing identifier in agents_never_sleep/run.py and
# acceptance/test_paperclip.py (a dict keyed by Paperclip ticket id) — it is not a token and the
# forbidden-pattern regex below matches it as a false positive; filtered out by name, not by path,
# so an actual pcp_ token accidentally pasted into either file would still be caught.
fail_pattern "paperclip-token" 'pcp_[A-Za-z0-9]' 'pcp_id_by_ticket' "${FIXTURE_EXCLUDES[@]}"
fail_pattern "github-token" 'ghp_[A-Za-z0-9]' '' "${FIXTURE_EXCLUDES[@]}"
fail_pattern "anthropic-openai-key" 'sk-[A-Za-z0-9]{20}' '' "${FIXTURE_EXCLUDES[@]}"
fail_pattern "aws-access-key" 'AKIA[0-9A-Z]{16}' '' "${FIXTURE_EXCLUDES[@]}"
fail_pattern "private-key-block" '-----BEGIN[A-Z ]+PRIVATE KEY-----' '' "${FIXTURE_EXCLUDES[@]}"

if [ "$hits" -gt 0 ]; then
  echo "REDACT LINT: FAILED — ${hits} forbidden-pattern group(s) matched above." >&2
  exit 1
fi
echo "REDACT LINT: PASSED — 0 hits across the tracked tree."
