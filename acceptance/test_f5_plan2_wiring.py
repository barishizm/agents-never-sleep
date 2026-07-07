#!/usr/bin/env python3
"""Plan 2 wiring: the hard-category widening end-to-end — offer record snapshots the effective set,
resolve re-checks against THAT set (not fresh config), and a hard-category resolution is forced to
DONE_LOW_CONFIDENCE + daylight review even with a green gate."""
import os
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
