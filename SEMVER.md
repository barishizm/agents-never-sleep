# SemVer policy & v1.0 roadmap — agents-never-sleep

> **STATUS: DRAFT for review (Mes).** This document proposes the versioning commitment. It does
> **not** declare 1.0 and does **not** finalize the guarantee — tagging 1.0 is an explicit human
> decision (see §4). Until 1.0 is tagged, the package stays `0.x` and the API is **not** yet
> stability-guaranteed (a `0.x` minor bump may break things, per SemVer §4).

This file complements two existing documents — read them together:

- **`ARCHITECTURE.md`** — enumerates the public API surface (CLI flags, ticket format, gate
  interface, outcome states, config schema). That doc is the *contract*; this doc is the *policy*
  for how the contract may change.
- **`CHANGELOG.md`** — the per-version record of what changed; it already carries a "Roadmap to
  v1.0" list, which §4 here makes concrete and checkable.

The current published version is **`0.3.1`** (source of truth: `harness/__init__.py` `__version__`).

---

## 1. What SemVer means for this package

We follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). For a version
`MAJOR.MINOR.PATCH`, **once 1.0 is tagged**:

- **MAJOR** — a breaking change to anything classified **Stable** in §2 (a removed CLI flag, a
  changed JSON output key, a removed/renamed config key, a changed/removed outcome-state value, a
  renamed importable symbol). Breaking changes are announced in the CHANGELOG with a migration note.
- **MINOR** — backward-compatible additions: a new optional CLI flag, a new optional config key, a
  new JSON output field, a new outcome state, a new (additive) integration. Existing callers keep
  working unchanged.
- **PATCH** — bug fixes and internal changes that do not alter any Stable surface (e.g. the redact
  hardening in 0.3.1).

**Before 1.0 (now):** SemVer §4 applies — `0.x` makes **no** stability promise. We nonetheless aim
to treat `0.MINOR` bumps as the signal for surface changes and keep PATCH for fixes, so the habit is
already in place when 1.0 lands.

## 2. Public API surface — Stable vs Experimental

"Stable" = covered by the §1 guarantee at 1.0. "Experimental" = may change in a MINOR before
1.0-equivalent stabilization; do not build load-bearing automation on it without pinning.

### 2.1 CLI — the loop (`python3 -m harness.run` / `ans`)

| Surface | Class | Notes |
|---|---|---|
| `next` subcommand + `--repo`, `--tickets` flags | **Stable** | Primary agent-driven entry. |
| `complete` subcommand + `--attempted`, `--cannot-implement` | **Stable** | Core loop. |
| `complete` council/specialist flags (`--council-verdict`, `--council-cost`, `--review-coverage`, `--specialist-concerns`, `--specialist-cost`, `--council-http-status`) | **Experimental** | Tied to the review-council feature, which is still evolving. |
| `report` subcommand | **Stable** | Re-emits the morning report. |
| `reset-attempts`, `reset-spend` | **Stable** | Operator escapes. |
| `parked protect|restore` | **Experimental** | WIP-protection surface (INT-1735). |
| JSON output shapes in ARCHITECTURE.md §1 | **Stable** | Documented keys only; undocumented keys may appear/disappear. |

### 2.2 CLI — the launcher (`bin/ans-run` / `ans-run`)

| Surface | Class | Notes |
|---|---|---|
| `ans-run [--repo] [--agent] [--fg] [--check] [--trust] PROMPT...` | **Stable** | Flags + exit codes (0 / 64 NO-GO / 65 busy). |
| `.claude/agents-never-sleep.json` `launcher` section (presets, `target_user`, `checks`, `credentials_paths`, `min_disk_mb`, `fresh_session_every`) | **Stable** | Additive keys = MINOR. |
| `ANS_RUN_NO_LOCK`, `ANS_TRUST_STORE` env vars | **Experimental** | Escape hatches / test hooks. |

### 2.3 Ticket format (ARCHITECTURE.md §2)

| Surface | Class |
|---|---|
| `.md` + YAML front-matter (`id`, `title`, `blast_radius`, `expected_outcome`); harness never mutates ticket files | **Stable** |

### 2.4 Gate interface & config (ARCHITECTURE.md §3, §5)

| Surface | Class | Notes |
|---|---|---|
| `gate.command` / `gate.timeout_s` / `gate.cwd`; green=exit 0 contract | **Stable** | |
| Top-level config keys `gate`, `budget`, `integrations`, `launcher` | **Stable** | |
| `council`, `specialists` config sections | **Experimental** | Feature still maturing. |
| `integrations.paperclip`, `integrations.tokonomix` | **Experimental** | External-service shaped. |

### 2.5 Outcome states (ARCHITECTURE.md §4)

All seven values (`DONE`, `DONE_LOW_CONFIDENCE`, `PARKED_DECISION`, `PARKED_FOUNDATIONAL`,
`BLOCKED_ENV`, `FAILED_RETRYABLE`, `FAILED_BUG_IN_AGENT`) are **Stable** — they are how a consumer
interprets a run. New states may be ADDED (MINOR); existing ones are not renamed/removed without a
MAJOR bump.

### 2.6 Python import surface (`import harness`)

| Surface | Class | Notes |
|---|---|---|
| `harness.__version__` | **Stable** | |
| `harness.launcher:main`, `harness.run:main` (the console entry points) | **Stable** | Their *callability* is the contract, not their internal signature. |
| Everything else under `harness.*` (e.g. `harness.driver`, `harness.orchestrator`, `harness.council`) | **Experimental / internal** | Importable but NOT a supported API. Use the CLI. |

> ⚠️ **v1.0 blocker (see §4): top-level package name `harness`.** Pip-installing makes
> `import harness` the public import path — a generic, collision-prone name for a published package.
> Renaming the package to `agents_never_sleep` is a one-time breaking change that should land
> **before** 1.0 (after 1.0 it would be a MAJOR bump). Deferred now because it breaks the symlinked
> dev install, `python -m harness.run` in every doc/recipe, and `test_*` imports — it needs its own
> ticket. **Decision for Mes.**

## 3. Deprecation policy (applies from 1.0)

- A Stable surface marked **deprecated** keeps working for at least one MINOR release, emits a
  warning where practical, and is documented in the CHANGELOG under a "Deprecated" heading.
- Removal of a deprecated surface happens only in a MAJOR release.
- Experimental surfaces may change or be removed in a MINOR with a CHANGELOG note, no deprecation
  window.

## 4. Roadmap to v1.0 — what must be true to tag it

This refines the existing "Roadmap to v1.0" in `CHANGELOG.md` into a checkable list. **Tagging 1.0,
publishing to PyPI, and cutting the GitHub release are explicit Mes decisions — never autonomous.**

| # | Criterion | Status |
|---|---|---|
| 1 | **Stable surface frozen & reviewed** — §2 classifications signed off; "Experimental" items either stabilized or explicitly kept experimental past 1.0. | ☐ pending Mes review of this doc |
| 2 | **`pip install agents-never-sleep` works** in a fresh venv, both console scripts on PATH. | ✅ built + verified locally (wheel installs offline, `ans-run`/`ans` run from a venv); **PyPI publish is a Mes action** |
| 3 | **Real-agent E2E proof** — `acceptance/test_real_claude.py` drives real `claude -p` to DRAINED, asserts done≥2 **and** committed work on the run branch. | ✅ test present + collects clean; live run is Mes/credential-gated |
| 4 | **Package rename** `harness` → `agents_never_sleep` (§2.6 blocker) decided + executed, or explicitly waived. | ☐ Mes decision (needs own ticket) |
| 5 | **Cross-platform enforcement adapters** — at least Codex + Gemini CLI hooks implemented & tested (Claude Code shipped). | ☐ partial (adapters scaffolded under `hooks/platforms/`) |
| 6 | **Public docs** — tokonomix.ai/agents-never-sleep (or equivalent) published. | ☐ |
| 7 | **CHANGELOG complete** with a `1.0.0` entry + the SemVer commitment statement made final (remove the DRAFT banner from this file). | ☐ |
| 8 | **Mes sign-off** — PyPI publish + GitHub release + git tag `v1.0.0`. | ☐ human-gated |

When 1.0 is tagged, delete the DRAFT banner at the top of this file and the §1 "Before 1.0" caveat;
the guarantee becomes binding from that commit.
