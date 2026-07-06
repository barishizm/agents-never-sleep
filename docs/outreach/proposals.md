# External-content proposals (maintainer-gated — nothing here is published)

Technical deep dives, never ads. Each proposal lists what may **not** be claimed, because the
honesty bar travels with the content: mechanism, not outcome; no benchmark numbers (none exist);
"live-verified on Claude Code only" wherever enforcement comes up.

---

## P1 — "Your agent's only answer to uncertainty is STOP — that's a governance bug, not an AI bug"

- **Thesis.** Coding agents stall on the first unanswerable question because *deciding how to
  behave under uncertainty during long autonomous work* is above the agent's responsibility — a
  separation-of-concerns argument, not a model-quality one. ASK/PARK/HALT as the concrete contract.
- **Outline.** The 22:00→08:00 stall anecdote (labelled as illustration) → why the model can't fix
  it → the three responses and blast-radius tiering → what enforcement (not discipline) looks like
  → limitations.
- **Venue.** Dev.to / personal engineering blog; HN submission of the blog post.
- **May NOT claim:** throughput/success numbers; that other platforms are live-verified; that PARK
  never defers important work (it does, by design).
- **Effort.** ~1 day writing + review.

## P2 — "Deterministic gates + git-backed reversibility: trusting agent work you didn't watch"

- **Thesis.** The only hard arbiter of unattended agent work is a deterministic gate; everything
  else (council, specialists) is advisory. Snapshot-before-edit / revert-on-red / per-ticket
  `pre:`/`done:` commits make wrong-but-confident work cheap to undo.
- **Outline.** Failure taxonomy (introduced vs pre-existing vs env) → why "delete the failing test"
  must be a blocking blind-spot → the run-branch review workflow.
- **Venue.** Dev.to or an engineering blog; good conference-lightning-talk candidate.
- **May NOT claim:** that gates catch what tests don't cover; recovery statistics.
- **Effort.** ~1 day.

## P3 — "Agreement is not correctness: what a multi-model council is actually for"

- **Thesis.** A council is a *recall amplifier feeding judgment, not a truth oracle* — frontier
  models share training data and can be uniformly wrong; the design levers are blind parallel
  proposers, an independent cross-family judge, decorrelation over raw score, and grounding.
- **Outline.** The epistemics → why ANS treats verdicts as advisory (trust-or-flag, never revert)
  → DONE_LOW_CONFIDENCE / daylight review as the honest disposition.
- **Venue.** Longer-form: personal blog / Medium engineering pub.
- **May NOT claim:** measured error-reduction percentages.
- **Effort.** 1–2 days.

## P4 — "The fresh-session context strategy: why long agent sessions degrade and %-triggered compaction makes it worse"

- **Thesis.** Harness state must be durable so *agent context* can be disposable: fresh session
  every N tickets beats mid-task summarization (lossy, cache-busting, constraint-dropping).
- **Outline.** The degradation observation (labelled anecdotal) → auto-compact vs %-trigger vs
  fresh-session → the `fresh_session_every` mechanism and its never-stop interaction.
- **Venue.** Dev.to; HN.
- **May NOT claim:** a measured degradation curve (observation is anecdotal until benchmarked).
- **Effort.** ~half a day.

## P5 — "The Autonomous Execution Governance manifesto" (derivative)

- **Thesis.** Condensed serialization of `docs/manifesto.md` for a general engineering audience.
- **Venue.** Where P1 lands well, as the follow-up.
- **May NOT claim:** "industry standard" / category-leadership language ("defines/pioneers" only
  if the maintainer elects it).
- **Effort.** ~half a day (source exists).

---

**Suggested order:** P1 → P2 → P4 (short, concrete, code-anchored), then P3/P5. Every draft goes
through maintainer review before any submission; venue accounts and posting are maintainer-owned.
