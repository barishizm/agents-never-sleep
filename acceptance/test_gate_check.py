"""Standalone (NOT pytest): python3 acceptance/test_gate_check.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site-src"))
from tools import gate_check


def test_added_line_without_ssot_fails():
    ok, why = gate_check.decide(
        changelog_diff="+### Added — new watchdog knob\n", label_names=[],
        changed_paths=["agents_never_sleep/watchdog.py"], waiver=None)
    assert ok is False, why


def test_added_line_with_ssot_entry_passes():
    ok, why = gate_check.decide(
        changelog_diff="+### Added — new watchdog knob\n", label_names=[],
        changed_paths=["site-src/content/mechanisms/watchdog.json"], waiver=None)
    assert ok is True, why


def test_label_without_ssot_fails():
    ok, why = gate_check.decide(
        changelog_diff="", label_names=["knowledge-affecting"],
        changed_paths=["agents_never_sleep/reap.py"], waiver=None)
    assert ok is False, why


def test_waiver_passes_with_reason():
    ok, why = gate_check.decide(
        changelog_diff="+### Added — internal-only refactor\n", label_names=[],
        changed_paths=["agents_never_sleep/reap.py"], waiver="internal refactor, no public surface")
    assert ok is True, why


def test_no_knowledge_signal_passes():
    ok, why = gate_check.decide(
        changelog_diff="+### Fixed — typo\n", label_names=[],
        changed_paths=["README.md"], waiver=None)
    assert ok is True, why


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"OK {name}")
    print("all passed")


if __name__ == "__main__":
    main()
