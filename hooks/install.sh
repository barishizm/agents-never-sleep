#!/usr/bin/env bash
# install.sh — wire the agents-never-sleep enforcement snippet into one platform, in one command.
#
# Replaces the manual "copy the snippet + hand-edit <SKILL_DIR> + chmod" dance. Renders the platform
# snippet with <SKILL_DIR> resolved to this skill's absolute path and writes it to the platform's
# hooks location. Default is a DRY RUN (prints what it would do); pass --apply to write.
#
# Usage:
#   hooks/install.sh <platform> [--apply] [--skill-dir DIR] [--target PATH]
#     <platform>      gemini | codex | copilot | cursor | windsurf
#     --apply         actually write (default: dry-run to stdout)
#     --skill-dir DIR absolute path the wired hook should point at (default: this skill's root)
#     --target PATH   write here instead of the platform default (required for copilot/cursor)
#
# Safety: if the target already exists, the rendered snippet is written to "<target>.ans-fragment"
# instead of overwriting it — these are MERGE targets (e.g. ~/.gemini/settings.json), never clobber
# a user's existing config. The dispatcher stays inert unless UE_UNATTENDED=1/CLAUDE_UNATTENDED=1.
set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$HOOKS_DIR/.." && pwd)"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

[ $# -ge 1 ] || die "usage: install.sh <platform> [--apply] [--skill-dir DIR] [--target PATH]"
PLATFORM="$1"; shift
APPLY=0
SKILL_DIR="$SKILL_ROOT"
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --skill-dir) SKILL_DIR="${2:?--skill-dir needs a value}"; shift 2 ;;
    --target) TARGET="${2:?--target needs a value}"; shift 2 ;;
    *) die "unknown option: $1" ;;
  esac
done

# platform -> snippet file (relative to hooks/platforms) + default target (~ = $HOME)
case "$PLATFORM" in
  gemini)   SRC="gemini/settings.json";              DEFAULT_TARGET="$HOME/.gemini/settings.json" ;;
  codex)    SRC="codex/hooks.json";                  DEFAULT_TARGET="$HOME/.codex/hooks.json" ;;
  windsurf) SRC="windsurf/hooks.json";               DEFAULT_TARGET="$HOME/.codeium/windsurf/hooks.json" ;;
  copilot)  SRC="copilot/unattended-execution.json"; DEFAULT_TARGET="" ;;  # repo .github/hooks/ — needs --target
  cursor)   SRC="cursor/hooks.json";                 DEFAULT_TARGET="" ;;  # project .cursor/ — needs --target
  *) die "unknown platform '$PLATFORM' (use: gemini | codex | copilot | cursor | windsurf)" ;;
esac

SNIPPET="$HOOKS_DIR/platforms/$SRC"
[ -f "$SNIPPET" ] || die "snippet not found: $SNIPPET"
[ -n "$TARGET" ] || TARGET="$DEFAULT_TARGET"
[ -n "$TARGET" ] || die "platform '$PLATFORM' has no default target — pass --target <path>"

# Render: substitute the <SKILL_DIR> placeholder. '#' delimiter avoids clashing with path slashes.
RENDERED="$(sed "s#<SKILL_DIR>#${SKILL_DIR}#g" "$SNIPPET")"

if [ "$APPLY" -eq 0 ]; then
  printf '# DRY RUN — would write to: %s\n' "$TARGET" >&2
  printf '# (pass --apply to write; existing targets get a .ans-fragment for manual merge)\n' >&2
  printf '%s\n' "$RENDERED"
  exit 0
fi

# Apply: make enforce.sh executable, then write (never clobber an existing config).
chmod +x "$HOOKS_DIR/enforce.sh" 2>/dev/null || true
OUT="$TARGET"
if [ -e "$TARGET" ]; then
  OUT="${TARGET}.ans-fragment"
  printf 'NOTE: %s exists — writing fragment to %s; merge it into your config.\n' "$TARGET" "$OUT" >&2
fi
mkdir -p "$(dirname "$OUT")"
printf '%s\n' "$RENDERED" > "$OUT"
printf 'wired %s -> %s (skill: %s)\n' "$PLATFORM" "$OUT" "$SKILL_DIR" >&2
[ "$OUT" = "$TARGET" ] || printf 'remember to merge %s into %s\n' "$OUT" "$TARGET" >&2
