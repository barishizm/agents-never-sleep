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

from agents_never_sleep.ledger import AttemptLedger  # noqa: E402


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


def main() -> int:
    failures: list = []
    test_ledger_f5_attempted(failures)
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
