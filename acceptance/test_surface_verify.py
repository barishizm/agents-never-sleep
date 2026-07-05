"""Standalone (NOT pytest): python3 acceptance/test_surface_verify.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site-src"))
from tools import surface_verify


def test_all_present_ok():
    r = surface_verify.check_text("...F5 — consensus-assisted PARK...", ["F5"])
    assert r["ok"] is True and r["missing"] == [], r


def test_missing_reported_not_raised():
    r = surface_verify.check_text("nothing here", ["F5", "council"])
    assert r["ok"] is False, r
    assert set(r["missing"]) == {"F5", "council"}, r


def test_report_is_string():
    s = surface_verify.report({"ok": False, "missing": ["F5"]})
    assert isinstance(s, str) and "F5" in s, s


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"OK {name}")
    print("all passed")


if __name__ == "__main__":
    main()
