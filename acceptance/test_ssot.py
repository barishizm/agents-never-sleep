"""Standalone (NOT pytest): python3 acceptance/test_ssot.py"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site-src"))
from tools import ssot


def _write(d, name, obj):
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        json.dump(obj, f)


def test_loads_and_sorts():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "b.json", {"id": "b", "title": "B", "summary": "s", "body_html": "<p>b</p>", "order": 2})
        _write(d, "a.json", {"id": "a", "title": "A", "summary": "s", "body_html": "<p>a</p>", "order": 1})
        rows = ssot.load(root=d)
        assert [r["id"] for r in rows] == ["a", "b"], rows


def test_missing_required_raises():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "x.json", {"id": "x", "title": "X", "summary": "s"})  # no body_html
        try:
            ssot.load(root=d)
        except ssot.SsotError:
            return
        raise AssertionError("expected SsotError for missing body_html")


def test_duplicate_id_raises():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "one.json", {"id": "dup", "title": "1", "summary": "s", "body_html": "<p>1</p>"})
        _write(d, "two.json", {"id": "dup", "title": "2", "summary": "s", "body_html": "<p>2</p>"})
        try:
            ssot.load(root=d)
        except ssot.SsotError:
            return
        raise AssertionError("expected SsotError for duplicate id")


def test_real_f5_entry_present():
    rows = ssot.load()  # the real content/mechanisms dir
    ids = [r["id"] for r in rows]
    assert "f5" in ids, ids


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"OK {name}")
    print("all passed")


if __name__ == "__main__":
    main()
