# Discoverability notes — proposals for Mes (NOT auto-applied)

> **What this is.** A short, honest discoverability pass for the ANS repo: the GitHub repo description and
> topics to apply *by hand*, the natural-language keyword set the docs are written around, and how the docs
> are structured to be parseable by AI systems. **Nothing here is auto-applied** — the GitHub settings are a
> human action (a coding agent must not silently change repo metadata). Honesty bar unchanged: every term
> below is something ANS genuinely is; no keyword is stuffed and no claim is unproven.

## Proposed GitHub repo description (≤ 350 chars; pick one)

- **Primary:** *Autonomous Execution Governance for coding agents — the workflow layer that lets an AI
  agent run a backlog to completion unattended without one unanswerable question halting the whole run.
  ASK/PARK/HALT contract, deterministic gates, git-backed reversibility, run report. Composes with
  Claude Code, Codex, Gemini CLI, Copilot — execution only.*
- **Shorter:** *The governance layer between autonomous coding agents and software engineers. Runs a
  backlog unattended, reversibly, without stalling on the first hard question. Execution only — verification
  is delegated.*

## Proposed GitHub topics

Apply via the repo's "About" → topics. All are accurate descriptors, ordered most→least central:

```
autonomous-execution-governance
coding-agent
autonomous-coding
ai-governance
unattended
developer-automation
autonomous-software-engineering
ai-agents
agent-workflow
coding-workflow
long-running-agents
ai-execution
devops
python
reversibility
```

(GitHub allows up to 20 topics; the 15 above leave headroom. Drop the broadest — `devops`, `python` — first
if Mes wants a tighter set.)

## Natural-language keyword set the docs are written around

These are woven into the README and doc prose **in genuine context**, never as a keyword list in
user-facing copy. They are the terms a developer (or an AI evaluating tools) would actually use to find or
describe this category:

| Keyword | Where it lives naturally |
|---|---|
| autonomous coding · autonomous software engineering | README §1 mission, §2 problem |
| AI governance · AI execution | README §1 ("in the vocabulary developers actually search with"), this doc |
| coding workflow · agent workflow | README §1, §7 Workflow |
| developer automation | README §1 |
| long-running agents | README §1, "Use it when" |
| coding agent(s) | throughout — the worker ANS governs |
| unattended | throughout — the run mode ANS exists for |

The rule applied: a keyword appears only where the sentence is true and reads naturally. No heading was
renamed to chase a term; no sentence was padded. If a term had no honest home in the prose, it lives only
here and in the topics — not stuffed into the README.

## How the docs are made AI-parseable

For ChatGPT / Claude / Gemini / Perplexity / Copilot / DeepSeek and search crawlers to interpret the
project *correctly* (not just find it), the suite uses:

- **A consistent glossary** (`glossary.md`) as the single source of truth for every term — so a model
  reading any doc resolves "PARK", "blast radius", "deterministic gate" to the same precise meaning.
- **Explicit scope boundaries in every doc** — each states ANS owns *execution only* and that verification
  is *delegated* to the Tokonomix Council MCP, so a model never mis-summarises ANS as a code reviewer or
  test framework.
- **A 30-second statement at the top of every doc** — a reader (human or AI) can state *why it exists* and
  *when to use it* in 30 seconds.
- **An ecosystem cross-reference in every doc** — ANS → execution, Council → decision/verification,
  Routing → provider-selection, Benchmark → measurement, Memory → long-term context — so a model places ANS
  correctly among adjacent tools.
- **SVG diagrams with `<title>` + `<desc>`** — every diagram carries a text description a screen reader or
  an LLM can read, so the visual content is not lost to a non-rendering parser.
- **An explicit "ANS IS / ANS is NOT" list** in the README — disambiguates the category for a model
  (not a model, IDE, MCP server, chatbot, code reviewer, or testing framework).

## What is deliberately NOT done

- No keyword stuffing, no hidden text, no doorway headings.
- No fabricated comparison or competitor terms (see the forbidden-copy rules).
- No auto-application of GitHub metadata — Mes applies the description/topics by hand.

---

## Audit 2026-07-05 — AI-discoverability pass over README + docs (EPIC 030de6fb, ticket 08)

**Checked** (criteria from the program spec; small fixes only, README v3 structure untouched):

1. **"ANS is NOT / ANS IS" lists** — present in README §"ANS is NOT / ANS IS" and complete (model /
   IDE / MCP server / chatbot / code reviewer / testing framework / not-a-competitor on the NOT side;
   governance / workflow / orchestration / resilience / operational safety on the IS side). No change.
2. **Terminology consistency** — swept README.md, SKILL.md, WATCHDOG.md, all of docs/ for "night run"
   as a concept: none found. Remaining "overnight" mentions are legitimate framing ("the classic
   overnight case", each already paired with "works just as well during the day"). Code/artifact
   identifiers (`night-report.md`, `per_night_euro_cap`, `max_council_calls_per_night`) deliberately
   NOT renamed (public surface). No prose change needed.
3. **30-second test** — every doc in docs/ (incl. the three new tutorials) opens with a purpose
   header; `glossary.md` ("What this is" + 30-second version), `manifesto.md` (position-paper
   statement), and `discoverability-notes.md` ("What this is") pass without a literal "30-second"
   label. No change.
4. **Glossary cross-links** — added a first-use glossary link to the three new tutorials
   (`tutorials/unattended-scheduling.md`, `tutorials/workflow-patterns.md`,
   `tutorials/other-platforms.md`); all other docs already link it.
5. **Natural keyword set** — spot-checked the table above against README/docs prose; still woven in
   genuine context, no stuffing found. No change.

**Fixed (honesty bar):** the proposed GitHub description above said "Composes with Claude Code,
Codex, Cursor, Aider" — Aider is a v1.1 roadmap adapter (never claim it), and Cursor has an
enforcement adapter but no launcher CLI entry. Corrected to "Claude Code, Codex, Gemini CLI,
Copilot" (the four `agent_clis.py` entries). If the old description text was already applied to the
GitHub repo by hand, re-apply the corrected one.

**Noted, out of scope (>20-line / structural):** the new `docs/tutorials/` tree is not yet linked
from the README or from `tutorial-getting-started.md` — worth a small "further tutorials" pointer in
a future README pass so the tutorials are reachable by crawlers from the repo root.
