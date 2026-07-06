# Terminology memo — "Execution Governance" vs "Operational Governance"

> **Status: decision memo, decision NOT taken.** The program spec flags the category name as a
> maintainer decision (it shapes naming and discoverability everywhere); this memo only organizes
> the trade-off. Based on general domain knowledge as of this writing — a web-search validation
> pass (current collisions, volume) is a recommended follow-up before deciding; no sources are
> fabricated here.

## The candidates

**A. Execution Governance** (current de-facto usage in README/manifesto: "Autonomous Execution
Governance").

- **For:** names the thing ANS actually owns — *how work executes* (scheduling, autonomy,
  reversibility, recoverability, continuity). Precise scope boundary: it audibly excludes code
  generation, reasoning quality, and verification. Novel enough as a phrase that ANS can define it.
- **Against:** "execution" is overloaded (process execution, trade execution in finance, project
  delivery in management-speak). Some ESL readers first parse "execution" as the death-penalty
  sense before the computing sense — a real but minor readability cost.

**B. Operational Governance**

- **For:** reads naturally to the ops/DevOps audience; "operational" is friendly across
  International English.
- **Against:** heavily colonized term — corporate/IT-governance frameworks (COBIT-adjacent
  material, ops-management consultancies) already use it for something else entirely. ANS would
  inherit collisions instead of defining a term. It also names the wrong layer: ANS governs
  *execution of autonomous work*, not *operations of a system in production*.

## Assessment

The discipline-defining move (README v3 / manifesto framing: "Version Control → CI/CD → DevOps →
Observability → **Autonomous Execution Governance**") only works with a term ANS can own.
"Operational Governance" is already someone else's term; "Execution Governance" is close to
whitespace and matches the load-bearing scope boundary (execution ONLY).

**Recommendation:** keep **Autonomous Execution Governance** as the primary category name; use
"operational safety" freely as a *property* inside descriptions (as the README already does), and
consider "autonomous-agent operations" as a secondary discoverability tag rather than a category
name. Validate with a web-search collision pass before public anchoring (P1/P5 in
[proposals.md](proposals.md)).

**Decision:** maintainer's. Nothing in the repo changes on the strength of this memo alone.
