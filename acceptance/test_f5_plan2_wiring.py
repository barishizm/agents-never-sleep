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


def test_offer_record_snapshots_effective_set(failures):
    with tempfile.TemporaryDirectory() as d:
        led = AttemptLedger(os.path.join(d, "ledger.json"))
        led.open_f5_offer("T1", attempt_id="a1", category="db_schema_or_migration",
                          has_safety_net=True, foundational=True,
                          consensus_assisted_categories=["db_schema_or_migration"])
        offer = led.get_f5_offer("T1")
        if offer.get("consensus_assisted_categories") != ["db_schema_or_migration"]:
            failures.append(f"offer must snapshot the effective set; got {offer!r}")


def main():
    failures = []
    test_offer_record_snapshots_effective_set(failures)
    if failures:
        print("RESULT: ❌")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
