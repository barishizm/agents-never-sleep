#!/usr/bin/env python3
"""Effective consensus-assisted category resolution: project default ± per-ticket override."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agents_never_sleep import consensus_scope  # noqa: E402
from agents_never_sleep.decide import HARD_PARK_CATEGORIES  # noqa: E402


def test_unset_uses_project_default(failures):
    got = consensus_scope.effective_categories(["db_schema_or_migration"], None)
    if got != ["db_schema_or_migration"]:
        failures.append(f"unset should return project default; got {got!r}")


def test_true_enables_all_hard_categories(failures):
    got = consensus_scope.effective_categories([], True)
    if got is None or set(got) != set(HARD_PARK_CATEGORIES):
        failures.append(f"true should enable every hard category; got {got!r}")


def test_false_is_fully_off(failures):
    got = consensus_scope.effective_categories(["db_schema_or_migration"], False)
    if got is not None:
        failures.append(f"false should return None (F5 fully off, even requirement_meaning); got {got!r}")


def main():
    failures = []
    for fn in (test_unset_uses_project_default, test_true_enables_all_hard_categories,
               test_false_is_fully_off):
        fn(failures)
    if failures:
        print("RESULT: ❌")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
