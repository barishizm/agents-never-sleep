# Cross-platform enforcement adapters (opt-in)

The autonomy contract — **never-ASK**, **deny-irreversible**, **never-stop** — is enforced at the code
layer so it does not rely on the agent's 2am judgment. The Claude adapter is the three bash hooks one
level up (`../*.sh`). This folder wires the **same decisions** into the other supported platforms via
one shared dispatcher: `python3 -m harness.enforce <platform> <event>` (launched by `../enforce.sh`).

**Strategy: best-effort + graceful degradation.** Each platform enforces what its hook system allows;
where a guarantee has no native hook, the run falls back to the SKILL.md prose contract AND emits a
loud **BLIND SPOT** in the morning report (via `harness/capabilities.py`). A missing guarantee is
never silent.

## Capability matrix (researched 2026-06 — see `../../references/cross-platform-enforcement-design.md`)

| Platform | deny-irreversible | never-stop | never-ASK |
|---|---|---|---|
| Claude Code | ✅ native | ✅ native | ✅ native |
| Gemini CLI | ✅ native | ✅ native | ⚠️ degraded (no pre-ask hook) |
| Codex CLI | ✅ native | ✅ native | ⚠️ degraded (no pre-ask hook) |
| Copilot CLI | ✅ native | ✅ native | ✅ native (`ask_user` tool) |
| Cursor | ✅ native | ⚠️ degraded (stop can't block) | ⚠️ degraded (no pre-ask hook) |
| Windsurf | ✅ native | ⚠️ degraded (no stop event) | ⚠️ degraded (no pre-ask hook) |

`deny-irreversible` works on every platform. The ⚠️ cells are reported as blind spots at run end.

## Install (per platform — all opt-in, all env-gated)

**One command** (`hooks/install.sh`) renders the snippet with `<SKILL_DIR>` resolved and writes it to
the platform's hooks location. Default is a DRY RUN — add `--apply` to write:

```bash
hooks/install.sh gemini             # dry-run: prints what it would write
hooks/install.sh gemini --apply     # writes ~/.gemini/settings.json (fragment if it already exists)
```

| Platform | command | default target |
|---|---|---|
| **Gemini CLI** | `hooks/install.sh gemini --apply` | `~/.gemini/settings.json` |
| **Codex CLI** | `hooks/install.sh codex --apply` | `~/.codex/hooks.json` (or `config.toml [hooks]`) |
| **Copilot CLI** | `hooks/install.sh copilot --apply --target <repo>/.github/hooks/agents-never-sleep.json` | — (`--target` required) |
| **Cursor** | `hooks/install.sh cursor --apply --target <project>/.cursor/hooks.json` | — (`--target` required) |
| **Windsurf** | `hooks/install.sh windsurf --apply` | `~/.codeium/windsurf/hooks.json` |

Safety: if the target already exists it is **never overwritten** — the rendered snippet is written to
`<target>.ans-fragment` for you to merge (these are merge targets like `settings.json`). The script
also `chmod +x`'s `enforce.sh`. (Manual alternative: copy the matching `platforms/<id>/*` file and
replace `<SKILL_DIR>` by hand — the script just does this deterministically.)

Then:
- The dispatcher is inert unless `UE_UNATTENDED=1` (or `CLAUDE_UNATTENDED=1`) is set — so once wired,
  it does nothing during your normal interactive sessions. Set it (and optionally `UE_PLATFORM=<id>`
  for accurate degradation reporting) only for real unattended runs.
- For `never-stop` to work, the platform must see the run-incomplete sentinel — export
  `UE_RUN_INCOMPLETE=<repo>/.unattended/run-incomplete` (the driver writes that path).

## Verification status

These adapters are built to each platform's **documented** hook contract and proven hermetically by
`acceptance/test_enforce_platforms.py` (correct stdin→deny/block shape per platform). A **live
smoke-test on each real tool** is the remaining manual step — run an unattended job on the platform,
confirm an irreversible command is blocked and (where native) a stop is blocked / an ask is denied.
