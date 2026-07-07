#!/usr/bin/env python3
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agents_never_sleep import config  # noqa: E402


class _Profile:
    has_tokonomix = False
    # default_config() reads profile.gates directly (no getattr fallback) to build the
    # "gates" section; every other attr it reads defensively via getattr(..., False).
    gates = []


def test_default_has_empty_consensus_list(failures):
    c = config.default_config(_Profile())
    val = (c.get("classify") or {}).get("consensus_assisted_categories")
    if val != []:
        failures.append(f"default consensus_assisted_categories must be []; got {val!r}")


def test_validate_accepts_known_categories(failures):
    try:
        config.validate_consensus_config(
            {"classify": {"consensus_assisted_categories": ["db_schema_or_migration"]}})
    except Exception as e:  # noqa: BLE001
        failures.append(f"known category must validate; raised {e!r}")


def test_validate_rejects_typo(failures):
    try:
        config.validate_consensus_config(
            {"classify": {"consensus_assisted_categories": ["db_schema"]}})
        failures.append("a misspelled category must be a hard error, not silently ignored")
    except ValueError:
        pass


def test_validate_rejects_requirement_meaning(failures):
    try:
        config.validate_consensus_config(
            {"classify": {"consensus_assisted_categories": ["requirement_meaning"]}})
        failures.append("requirement_meaning must be rejected (always eligible by definition)")
    except ValueError:
        pass


def main():
    failures = []
    for fn in (test_default_has_empty_consensus_list, test_validate_accepts_known_categories,
               test_validate_rejects_typo, test_validate_rejects_requirement_meaning):
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
