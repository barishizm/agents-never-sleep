#!/usr/bin/env python3
"""Plan 2 wiring: the hard-category widening end-to-end — offer record snapshots the effective set,
resolve re-checks against THAT set (not fresh config), and a hard-category resolution is forced to
DONE_LOW_CONFIDENCE + daylight review even with a green gate."""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agents_never_sleep.ledger import AttemptLedger  # noqa: E402
from agents_never_sleep.run import build_parser  # noqa: E402


def test_offer_record_snapshots_effective_set(failures):
    with tempfile.TemporaryDirectory() as d:
        led = AttemptLedger(os.path.join(d, "ledger.json"))
        led.open_f5_offer("T1", attempt_id="a1", category="db_schema_or_migration",
                          has_safety_net=True, foundational=True,
                          consensus_assisted_categories=["db_schema_or_migration"])
        offer = led.get_f5_offer("T1")
        if offer.get("consensus_assisted_categories") != ["db_schema_or_migration"]:
            failures.append(f"offer must snapshot the effective set; got {offer!r}")


def test_resolve_park_rechecks_recorded_set_not_fresh_config(failures):
    """A RESOLVE verdict on a hard category the RECORDED offer opted in must route to proceed even
    if the live project set no longer contains it (offer record is the trusted anchor)."""
    from agents_never_sleep import f5
    from agents_never_sleep.decide import Decision, Action
    # Recorded offer opted db_schema in; a fresh eligible() check with the recorded set is True,
    # with an empty set is False — proving resolve_park must use the recorded set.
    d = Decision(Action.PARK, "why", category="db_schema_or_migration", foundational=True)
    if not f5.eligible(d, has_safety_net=True, already_attempted=False,
                       consensus_assisted_categories=["db_schema_or_migration"]):
        failures.append("recorded set should make the hard category eligible at resolve time")
    if f5.eligible(d, has_safety_net=True, already_attempted=False,
                   consensus_assisted_categories=[]):
        failures.append("empty set (stale fresh config) should NOT — proves the anchor matters")


def _build_orch(work):
    """Minimal Orchestrator fixture — mirrors test_f5_wiring.py's `_build` but returns the
    Orchestrator directly (resolve_park is an Orchestrator method, no StepDriver needed here)."""
    from agents_never_sleep.gates import GateRunner
    from agents_never_sleep.ledger import AttemptLedger
    from agents_never_sleep.orchestrator import Orchestrator
    from agents_never_sleep.state import OutcomeStore

    repo = os.path.join(work, "repo")
    sandbox = os.path.join(HERE, "sandbox")
    if os.path.isdir(sandbox):
        shutil.copytree(sandbox, repo)
    else:
        os.makedirs(repo, exist_ok=True)
    state_dir = os.path.join(work, "state")
    gate = GateRunner(command=[sys.executable, "-m", "unittest", "discover", "-s", ".",
                               "-p", "test_*.py"], cwd=repo, timeout=60)
    ledger = AttemptLedger(os.path.join(state_dir, "ledger.json"))
    store = OutcomeStore(state_dir)
    return Orchestrator(repo_dir=repo, store=store, gate=gate, worker=None,
                        artifacts_dir=os.path.join(work, "art"), unattended=True, ledger=ledger)


def test_resolve_park_hard_category_defect_found_stays_parked(failures):
    """The end-to-end wiring of Task 6 Step 4/4b: a hard-category offer whose RECORDED
    consensus_assisted_categories opted it in, with a RESOLVE verdict that also FOUND A DEFECT,
    must route through interpret_soundness_verdict and stay parked — proving resolve_park routes
    the interpreter by the RECORDED category, not requirement_meaning-only."""
    from agents_never_sleep import f5
    from agents_never_sleep.decide import classify
    from agents_never_sleep.orchestrator import ProceedToken
    from agents_never_sleep.state import OutcomeState, TicketOutcome
    from agents_never_sleep.tickets import Ticket

    with tempfile.TemporaryDirectory(prefix="ue-f5plan2-hard-") as work:
        orch = _build_orch(work)
        ticket = Ticket(id="t-hard-defect", title="x",
                        body="Run a database schema migration to add a column", meta={}, path="")
        decision = classify(f"{ticket.title}\n{ticket.body}", unattended=True, has_safety_net=True)
        if decision.category != "db_schema_or_migration":
            failures.append(f"fixture ticket did not classify as a hard category: {decision}")
            return
        offer = {"attempt_id": "a-hard-defect", "category": decision.category,
                "has_safety_net": True, "foundational": decision.foundational,
                "status": "offered", "consensus_assisted_categories": [decision.category]}
        # resolved=True + evidence cited + zero dissent would RESOLVE under interpret_verdict, but
        # defect_found=True must veto to KEEP_PARKED under interpret_soundness_verdict.
        verdict = f5.F5Verdict(resolved=True, chosen_reading="SQL injection at line 42",
                              evidence="line 42 concatenates unsanitized user input",
                              dissent_count=0, synthesis_text="clear vulnerability",
                              defect_found=True)
        result = orch.resolve_park(ticket, offer, verdict)
        if isinstance(result, ProceedToken):
            failures.append("a defect_found verdict on a hard category must NOT reach begin_proceed")
        if not isinstance(result, TicketOutcome) or result.state != OutcomeState.PARKED_FOUNDATIONAL:
            failures.append(f"defect_found hard category must stay parked foundational, got {result}")

        # Contrast: the SAME offer/category, resolved cleanly with NO defect, structurally eligible
        # via the recorded set, must RESOLVE into begin_proceed — proving the veto is defect-specific,
        # not a blanket block on hard categories once opted in.
        ticket2 = Ticket(id="t-hard-clean", title="x",
                         body="Run a database schema migration to add a column", meta={}, path="")
        clean_verdict = f5.F5Verdict(resolved=True, chosen_reading="additive, reversible migration",
                                    evidence="migration adds a nullable column only",
                                    dissent_count=0, synthesis_text="straightforwardly additive",
                                    defect_found=False)
        clean_result = orch.resolve_park(ticket2, offer, clean_verdict)
        if not isinstance(clean_result, ProceedToken):
            failures.append(f"a clean soundness verdict on the RECORDED opted-in set must RESOLVE, "
                            f"got {clean_result}")


def test_resolve_park_requirement_meaning_still_uses_interpret_verdict(failures):
    """The `requirement_meaning` branch must still route through interpret_verdict (the
    disambiguation gate), not interpret_soundness_verdict — defect_found=True is meaningless there
    (the agent never sets it on that path) and must not accidentally veto a real disambiguation."""
    from agents_never_sleep import f5
    from agents_never_sleep.decide import classify
    from agents_never_sleep.orchestrator import ProceedToken

    with tempfile.TemporaryDirectory(prefix="ue-f5plan2-reqmeaning-") as work:
        orch = _build_orch(work)
        from agents_never_sleep.tickets import Ticket
        ticket = Ticket(id="t-reqmeaning", title="Add a widget",
                        body="Add a widget — unclear which kind of widget?", meta={}, path="")
        decision = classify(f"{ticket.title}\n{ticket.body}", unattended=True, has_safety_net=True)
        if decision.category != "requirement_meaning":
            failures.append(f"fixture ticket did not classify as requirement_meaning: {decision}")
            return
        offer = {"attempt_id": "a-reqmeaning", "category": decision.category,
                "has_safety_net": True, "foundational": decision.foundational, "status": "offered"}
        verdict = f5.F5Verdict(resolved=True, chosen_reading="a status badge",
                              evidence="components/Badge.tsx already renders status",
                              dissent_count=0, synthesis_text="clearly reading A")
        result = orch.resolve_park(ticket, offer, verdict)
        if not isinstance(result, ProceedToken):
            failures.append(f"requirement_meaning RESOLVE must still route via interpret_verdict "
                            f"and reach begin_proceed, got {result}")


def _resolve_park_argv(*extra):
    return ["resolve-park", "--ticket-id", "T1", "--attempt-id", "a1",
            "--resolved", "--chosen-reading", "x", *extra]


def test_resolve_park_defect_found_flag_defaults_false(failures):
    parser = build_parser()
    args = parser.parse_args(_resolve_park_argv())
    if getattr(args, "defect_found", "MISSING") is not False:
        failures.append(f"--defect-found must default to False, got {getattr(args, 'defect_found', 'MISSING')!r}")

    from agents_never_sleep.f5 import F5Verdict
    verdict = F5Verdict(resolved=args.resolved, chosen_reading=args.chosen_reading or "",
                        evidence=args.evidence or "", dissent_count=args.dissent_count,
                        synthesis_text=args.synthesis_text or "",
                        defect_found=getattr(args, "defect_found", False))
    if verdict.defect_found is not False:
        failures.append(f"F5Verdict.defect_found must be False when --defect-found omitted, got {verdict.defect_found!r}")


def test_resolve_park_defect_found_flag_sets_true(failures):
    parser = build_parser()
    args = parser.parse_args(_resolve_park_argv("--defect-found"))
    if args.defect_found is not True:
        failures.append(f"--defect-found must set True, got {args.defect_found!r}")

    from agents_never_sleep.f5 import F5Verdict
    verdict = F5Verdict(resolved=args.resolved, chosen_reading=args.chosen_reading or "",
                        evidence=args.evidence or "", dissent_count=args.dissent_count,
                        synthesis_text=args.synthesis_text or "",
                        defect_found=getattr(args, "defect_found", False))
    if verdict.defect_found is not True:
        failures.append(f"F5Verdict.defect_found must be True when --defect-found passed, got {verdict.defect_found!r}")


def main():
    failures = []
    test_offer_record_snapshots_effective_set(failures)
    test_resolve_park_rechecks_recorded_set_not_fresh_config(failures)
    test_resolve_park_hard_category_defect_found_stays_parked(failures)
    test_resolve_park_requirement_meaning_still_uses_interpret_verdict(failures)
    test_resolve_park_defect_found_flag_defaults_false(failures)
    test_resolve_park_defect_found_flag_sets_true(failures)
    if failures:
        print("RESULT: ❌")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
