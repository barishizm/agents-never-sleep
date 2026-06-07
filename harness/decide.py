"""ASK / PARK / HALT — three distinct coded states (never collapsed).

The council's most important contradiction-fix: a junior reading "never stop" + "park ticket"
in prose will implement "park" as "stop the run" and invert the whole spine. So the three
states are explicit here:

  ASK  - ask the human. FORBIDDEN in unattended mode. The harness must never emit this unattended.
  PARK - defer THIS decision/ticket; the run keeps moving to the next independent ticket.
  HALT - stop the WHOLE run. Only on irreversible-damage-at-hook or no-safety-net (read-only fs).

Blast-radius tiering is made CONCRETE (enumerated hard-PARK categories) so the agent rarely
lands in "unsure" — the council's fix for both the safety risk and the park-starvation risk.
This MVP classifier is keyword/heuristic based; in production the agent supplies the
classification, but the contract (these three states, never-ask-unattended) is identical.
"""
from __future__ import annotations

import dataclasses
import enum
import re

from .state import ContaminationScope


class Action(str, enum.Enum):
    PROCEED = "PROCEED"   # assume + do (low blast-radius, reversible)
    PARK = "PARK"         # defer this ticket/decision
    HALT = "HALT"         # stop the whole run (irreversible / no safety net)
    ASK = "ASK"           # interactive only; never returned in unattended mode


@dataclasses.dataclass
class Decision:
    action: Action
    why: str
    category: str = ""
    foundational: bool = False
    contamination_scope: ContaminationScope = ContaminationScope.NONE


# Enumerated hard-PARK categories. Each maps to (regex, foundational?, scope).
HARD_PARK_CATEGORIES = {
    "db_schema_or_migration": (r"\b(schema|migrat|alter table|drop column|add column)\b", True, ContaminationScope.SERVICE),
    "api_contract": (r"\b(api contract|response shape|request shape|public api|endpoint contract)\b", True, ContaminationScope.SERVICE),
    "security_or_tenant": (r"\b(auth|authz|permission|tenant|isolation|rbac|access control|jwt|session)\b", True, ContaminationScope.SERVICE),
    "money_or_billing": (r"\b(discount|billing|price|pricing|invoice|payment|charge|refund|tax|vat)\b", False, ContaminationScope.MODULE),
    "cross_ticket_interface": (r"\b(shared interface|cross-ticket|other tickets depend|breaking change)\b", True, ContaminationScope.PACKAGE),
}

# Signals that a ticket's REQUIREMENT MEANING is ambiguous (we don't know WHAT to build).
AMBIGUITY_SIGNALS = (
    r"\b(which|what kind|unclear|ambiguous|tbd|decide|undecided|some sort of|or something)\b",
    r"\?\s*$",
)


def _matches(patterns, text) -> bool:
    return any(re.search(p, text, re.IGNORECASE | re.MULTILINE) for p in patterns)


def classify(ticket_text: str, *, unattended: bool, has_safety_net: bool) -> Decision:
    """Decide ASK/PARK/HALT for a ticket. `ticket_text` = title + body."""
    text = ticket_text.lower()

    # HALT: only when we cannot guarantee reversibility at all. Without a safety net even a
    # "reversible" assumption is not actually reversible -> do not risk destructive work.
    if not has_safety_net:
        return Decision(Action.HALT, "no VCS/backup safety net — cannot guarantee reversibility",
                        category="no_safety_net")

    # Hard-PARK categories: high blast-radius regardless of how 'reversible' it looks.
    for cat, (pattern, foundational, scope) in HARD_PARK_CATEGORIES.items():
        if re.search(pattern, text, re.IGNORECASE):
            return Decision(Action.PARK, f"touches hard-PARK category: {cat}",
                            category=cat, foundational=foundational, contamination_scope=scope)

    # Requirement-meaning ambiguity on something NOT in a hard category:
    # hybrid is the default (build reversibly behind a flag + park the decision) ONLY when
    # locally reversible and isolated. We approximate "isolated" as: no hard category matched.
    if _matches(AMBIGUITY_SIGNALS, text):
        return Decision(Action.PARK, "requirement-meaning ambiguous; defer the decision",
                        category="requirement_meaning", foundational=False,
                        contamination_scope=ContaminationScope.FILE)

    # Otherwise: low blast-radius + reversible -> assume and proceed.
    return Decision(Action.PROCEED, "low blast-radius, reversible — assume + do",
                    category="routine", contamination_scope=ContaminationScope.FILE)
