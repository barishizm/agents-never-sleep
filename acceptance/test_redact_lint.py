"""Standalone (NOT pytest): python3 acceptance/test_redact_lint.py"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site-src"))
from tools import redact_lint, ssot


def test_clean_entry_no_violations():
    entries = [{"id": "ok", "title": "T", "summary": "A safe mechanism description.",
                "body_html": "<p>Runs a deterministic gate.</p>"}]
    assert redact_lint.scan(entries) == [], redact_lint.scan(entries)


def test_defaults_catch_generic_leaks():
    entries = [{"id": "bad", "title": "T", "summary": "reaches 10.0.0.5 and costs €0.07",
                "body_html": "<p>it never fails</p>"}]
    v = redact_lint.scan(entries)
    assert len(v) >= 3, v  # private IP + euro + absolute-claim


def test_local_vocab_merges():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.local.json")
        json.dump([{"label": "org host", "pattern": r"\bwoozle01\b"}], open(p, "w"))
        deny = redact_lint.load_deny(p)
        entries = [{"id": "h", "title": "T", "summary": "runs on woozle01", "body_html": "<p>ok</p>"}]
        v = redact_lint.scan(entries, deny=deny)
        assert any("org host" in x for x in v), v


def test_real_f5_entry_is_public_safe():
    assert redact_lint.scan(ssot.load()) == [], "SSOT entries must be public-safe"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"OK {name}")
    print("all passed")


if __name__ == "__main__":
    main()
