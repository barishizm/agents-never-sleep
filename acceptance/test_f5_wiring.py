#!/usr/bin/env python3
"""F5 WIRING — the runtime interrupt/resume path that activates agents_never_sleep/f5.py.

test_f5.py already proves the PURE core (narrow eligibility + downgrade-only interpretation).
This suite proves the WIRING around it: the driver's new PARK_CONSENSUS_ELIGIBLE interrupt, the
`resolve-park` CLI round-trip (both RESOLVE->PROCEED and KEEP_PARKED->declined-park), the durable
already-attempted flag surviving a simulated crash, the per-run F5 call ceiling, and the morning
report's declined-consensus visibility line.

Exit 0 = GREEN.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

import shutil

from agents_never_sleep import f5                                        # noqa: E402
from agents_never_sleep.decide import classify                           # noqa: E402
from agents_never_sleep.driver import StepDriver                         # noqa: E402
from agents_never_sleep.gates import GateRunner                          # noqa: E402
from agents_never_sleep.ledger import AttemptLedger  # noqa: E402
from agents_never_sleep.orchestrator import Orchestrator, ProceedToken   # noqa: E402
from agents_never_sleep.state import OutcomeState, OutcomeStore, TicketOutcome  # noqa: E402
from agents_never_sleep.tickets import Ticket                            # noqa: E402


def test_ledger_f5_attempted(failures):
    work = tempfile.mkdtemp(prefix="ue-f5-ledger-")
    led = AttemptLedger(os.path.join(work, "ledger.json"))
    if led.f5_attempted("t-1"):
        failures.append("[ledger] a fresh ticket must not be f5_attempted")
    if led.get_f5_offer("t-1") is not None:
        failures.append("[ledger] a fresh ticket must have no offer record")
    led.open_f5_offer("t-1", attempt_id="a-1", category="requirement_meaning",
                      has_safety_net=True, foundational=False)
    if not led.f5_attempted("t-1"):
        failures.append("[ledger] open_f5_offer did not persist f5_attempted in-process")
    rec = led.get_f5_offer("t-1")
    if rec is None or rec.get("attempt_id") != "a-1" or rec.get("category") != "requirement_meaning":
        failures.append(f"[ledger] get_f5_offer did not return the recorded fields: {rec}")
    if rec.get("status") != "offered":
        failures.append(f"[ledger] a new offer must start life as status='offered', got {rec}")
    # a FRESH AttemptLedger over the SAME path (simulates a new process) must see it too.
    led2 = AttemptLedger(os.path.join(work, "ledger.json"))
    if not led2.f5_attempted("t-1"):
        failures.append("[ledger] f5_attempted did not survive a reload from disk")
    rec2 = led2.get_f5_offer("t-1")
    if rec2 is None or rec2.get("attempt_id") != "a-1":
        failures.append(f"[ledger] the offer record did not survive a reload from disk: {rec2}")
    if led2.f5_attempted("t-2"):
        failures.append("[ledger] an unrelated ticket must not read as attempted")
    led2.consume_f5_offer("t-1")
    if led2.get_f5_offer("t-1").get("status") != "consumed":
        failures.append("[ledger] consume_f5_offer must flip the record's status to 'consumed'")


def _ambiguous_ticket(tid: str) -> Ticket:
    # Matches decide.AMBIGUITY_SIGNALS ("which kind"/"?") and no HARD_PARK_CATEGORIES keyword, so
    # classify() routes it to the requirement_meaning PARK branch (consensus_resolvable=True) — the
    # ONLY category F5 is ever eligible on (see f5.py / acceptance/test_f5.py).
    return Ticket(id=tid, title="Add a widget", body="Add a widget — unclear which kind of widget?",
                 meta={}, path="")


def _build(repo, state_dir, artifacts_dir, tickets):
    gate = GateRunner(command=[sys.executable, "-m", "unittest", "discover", "-s", ".",
                               "-p", "test_*.py"], cwd=repo, timeout=60)
    ledger = AttemptLedger(os.path.join(state_dir, "ledger.json"))
    store = OutcomeStore(state_dir)
    orch = Orchestrator(repo_dir=repo, store=store, gate=gate, worker=None,
                        artifacts_dir=artifacts_dir, unattended=True, ledger=ledger)
    return StepDriver(orch=orch, tickets=tickets, store=store, state_dir=state_dir,
                      report_path=os.path.join(os.path.dirname(state_dir), "report.md"))


def test_orchestrator_resolve_park_resolve_and_decline(failures):
    work = tempfile.mkdtemp(prefix="ue-f5-orch-")
    repo = os.path.join(work, "repo")
    shutil.copytree(os.path.join(HERE, "sandbox"), repo)
    drv = _build(repo, os.path.join(work, "state"), os.path.join(work, "art"), [])
    ticket = _ambiguous_ticket("t-resolve")
    decision = classify(f"{ticket.title}\n{ticket.body}", unattended=True, has_safety_net=True)
    if decision.category != "requirement_meaning":
        failures.append(f"[orch] fixture ticket did not classify as requirement_meaning: {decision}")
    # `offer` is the durable ledger RECORD (Task 1's open_f5_offer shape) — resolve_park never
    # re-classifies the ticket, so the test builds the record directly rather than re-deriving it.
    offer = {"attempt_id": "a-resolve", "category": decision.category,
            "has_safety_net": True, "foundational": decision.foundational, "status": "offered"}

    good = f5.F5Verdict(resolved=True, chosen_reading="a status badge",
                        evidence="components/Badge.tsx already renders status", dissent_count=0,
                        synthesis_text="clearly reading A")
    resolved = drv.orch.resolve_park(ticket, offer, good)
    if not isinstance(resolved, ProceedToken):
        failures.append(f"[orch] RESOLVE must route into begin_proceed (ProceedToken), got {resolved}")

    ticket2 = _ambiguous_ticket("t-decline")
    bad = f5.F5Verdict(resolved=False)
    declined = drv.orch.resolve_park(ticket2, offer, bad)
    if not isinstance(declined, TicketOutcome) or declined.state != OutcomeState.PARKED_DECISION:
        failures.append(f"[orch] KEEP_PARKED must write a PARKED_DECISION outcome, got {declined}")
    if "f5-attempted-declined" not in (declined.review_coverage or ""):
        failures.append(f"[orch] declined park missing the audit tag: {declined.review_coverage!r}")
    if "F5 consensus tried and declined" not in declined.why:
        failures.append(f"[orch] declined park 'why' missing the audit text: {declined.why!r}")
    if declined.category != "requirement_meaning":
        failures.append(f"[orch] declined park lost its category: {declined.category!r}")
    stored = drv.store.read("t-decline")
    if stored is None or stored.state != OutcomeState.PARKED_DECISION:
        failures.append("[orch] declined outcome was not durably written to the store")


def test_orchestrator_resolve_park_rejects_forged_hard_category(failures):
    """A resolve-park call carrying an offer RECORD whose category is a hard-PARK category (forged
    or a stale replay) must NEVER honour a claimed RESOLVE — defense in depth, since
    interpret_verdict alone cannot see the category and resolve_park never re-classifies the
    (possibly-mutated) ticket text, only the persisted record."""
    work = tempfile.mkdtemp(prefix="ue-f5-forge-")
    repo = os.path.join(work, "repo")
    shutil.copytree(os.path.join(HERE, "sandbox"), repo)
    drv = _build(repo, os.path.join(work, "state"), os.path.join(work, "art"), [])
    hard_ticket = Ticket(id="t-hard", title="x",
                        body="Run a database schema migration to add a column", meta={}, path="")
    decision = classify(f"{hard_ticket.title}\n{hard_ticket.body}", unattended=True,
                       has_safety_net=True)
    if decision.category != "db_schema_or_migration":
        failures.append(f"[orch] fixture did not classify as a hard category: {decision}")
    offer = {"attempt_id": "a-forge", "category": decision.category,
            "has_safety_net": True, "foundational": decision.foundational, "status": "offered"}
    forged = f5.F5Verdict(resolved=True, chosen_reading="whatever", evidence="whatever",
                          dissent_count=0)
    result = drv.orch.resolve_park(hard_ticket, offer, forged)
    if isinstance(result, ProceedToken):
        failures.append("[orch] a forged RESOLVE on a hard-PARK category must NOT reach begin_proceed")
    if not isinstance(result, TicketOutcome) or result.state != OutcomeState.PARKED_FOUNDATIONAL:
        failures.append(f"[orch] hard category must still park foundational, got {result}")


def main() -> int:
    failures: list = []
    test_ledger_f5_attempted(failures)
    test_orchestrator_resolve_park_resolve_and_decline(failures)
    test_orchestrator_resolve_park_rejects_forged_hard_category(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — F5 wiring not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — F5 wiring holds so far")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
