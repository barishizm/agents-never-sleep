"""Resolve the EFFECTIVE consensus-assisted category set for one ticket, from the project default
and the ticket's optional `consensus_assisted:` frontmatter override.

Kept as a pure, stdlib-only function so both the driver's offer-time check and (via the snapshotted
offer record) the orchestrator's resolve-time re-check use identical logic — and so the
supervised-only files only ever make a single call into here.

Resolution order (spec §2 — frontmatter is the strongest voice, applied symmetrically):
  ticket_declared is False -> F5 OFF for this ticket, regardless of category (INCLUDING
                              requirement_meaning). Returns None; caller skips the offer entirely.
  ticket_declared is True  -> F5 ON for this ticket even if its hard category is not in the project
                              default. Returns every hard category (a ticket lands in exactly one,
                              so a superset is equivalent to "this ticket's category is allowed").
  ticket_declared is None  -> project default (requirement_meaning is always eligible in eligible()
                              itself; this set only governs the hard categories).
"""
from .decide import HARD_PARK_CATEGORIES


def effective_categories(project_categories, ticket_declared):
    if ticket_declared is False:
        return None
    if ticket_declared is True:
        return list(HARD_PARK_CATEGORIES)
    return list(project_categories or [])
