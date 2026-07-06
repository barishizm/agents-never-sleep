# GitHub metadata pack — ready to apply (maintainer action)

> **Why this file exists.** The public repo was deleted and recreated on 2026-07-05 (security
> purge of the history), which wiped its GitHub *settings-level* metadata: description, topics,
> social-preview image. This pack contains everything ready-to-paste. **Nothing in here is
> applied automatically** — applying requires repo-admin auth (`gh auth login` or the web UI) and
> is the maintainer's explicit step.

## 1. Repo description (≤ 350 chars, mechanism-honest)

```
Autonomous execution governance for coding agents: run a ticket backlog to completion unattended.
ASK/PARK/HALT autonomy contract, durable per-ticket state machine, deterministic test gates,
git-backed reversibility, heartbeat watchdog, morning report. Python stdlib only. Governs the
agent you already use — it is not one.
```

## 2. Topics (~20, kebab-case)

```
ai-agents · autonomous-agents · agent-workflow · execution-governance · unattended-runs ·
coding-agents · claude-code · agent-autonomy · backlog-automation · ai-governance ·
developer-tools · workflow-automation · state-machine · test-gates · reversibility ·
agent-safety · long-running-agents · autonomous-software-engineering · python-stdlib · agent-skill
```

## 3. Social-preview image (spec only — 1280×640)

- Background: deep ink-blue (`#12182A`); the amber heartbeat-line mark left-of-center.
- Line 1 (large, serif): `agents-never-sleep`
- Line 2 (mono, smaller): `Run the backlog. Park the questions. Review at daylight.`
- Footer (small): `ASK / PARK / HALT · deterministic gates · git-backed reversibility · MIT`
- No screenshots, no benchmark numbers (none exist — honesty bar).

## 4. Release notes draft — v1.0.0

Grounded in `CHANGELOG.public.md`; edit tone, not claims:

```markdown
## v1.0.0 — the reliability spine, complete

First stable release. SemVer applies from this tag onward (see SEMVER.md).

- ASK/PARK/HALT autonomy contract with structural enforcement (deny-ask, deny-irreversible,
  stop-guard hooks — live-verified on Claude Code; other platforms built to their documented
  hook contracts, not yet live-verified)
- Durable per-ticket state machine, attempt caps, loop detection, low-yield breaker
- Deterministic gates with failure taxonomy; snapshot-before-edit, revert-on-red
- `bin/ans-run` launcher: pre-token GO/NO-GO preflight, config TOFU trust, atomic flock
- Heartbeat watchdog (stale-run restart), process reaping, fresh-session context strategy
- Paperclip board integration (per-ticket status sync), Vault/env token-refs, secret redaction
- Python stdlib only; MIT

Install: `pip install git+https://github.com/TokonoMix/agents-never-sleep@v1.0.0`
Known limits: see README "Limitations" — the gate is the only hard gate; the council is advisory;
no benchmark numbers are published (methodology only, docs/benchmarks.md).
```

## 5. The exact commands (maintainer, after `gh auth login`)

```bash
gh repo edit TokonoMix/agents-never-sleep \
  --description "Autonomous execution governance for coding agents: run a ticket backlog to completion unattended. ASK/PARK/HALT autonomy contract, durable per-ticket state machine, deterministic test gates, git-backed reversibility, heartbeat watchdog, morning report. Python stdlib only. Governs the agent you already use — it is not one."

for t in ai-agents autonomous-agents agent-workflow execution-governance unattended-runs \
         coding-agents claude-code agent-autonomy backlog-automation ai-governance \
         developer-tools workflow-automation state-machine test-gates reversibility \
         agent-safety long-running-agents autonomous-software-engineering python-stdlib agent-skill; do
  gh repo edit TokonoMix/agents-never-sleep --add-topic "$t"
done

# social preview: Settings → General → Social preview (web UI only; gh has no flag for it)

gh release create v1.0.0 --repo TokonoMix/agents-never-sleep \
  --title "v1.0.0 — the reliability spine, complete" --notes-file <notes-from-§4>
```
