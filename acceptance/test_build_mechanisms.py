"""Standalone (NOT pytest): python3 acceptance/test_build_mechanisms.py
Builds the site into a temp OUT and asserts the mechanisms page + llms.txt exist."""
import os, sys, tempfile

SITE_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site-src")
sys.path.insert(0, SITE_SRC)


def test_mechanisms_page_contains_f5():
    import build
    with tempfile.TemporaryDirectory() as tmp:
        build.OUT = tmp
        build.build()
        p = os.path.join(tmp, "en", "mechanisms", "index.html")
        assert os.path.isfile(p), "mechanisms page not built"
        html = open(p, encoding="utf-8").read()
        assert "consensus-assisted PARK" in html, "F5 body not rendered"


def test_llms_txt_is_generated_with_f5():
    import build
    with tempfile.TemporaryDirectory() as tmp:
        build.OUT = tmp
        build.build()
        p = os.path.join(tmp, "llms.txt")
        assert os.path.isfile(p), "llms.txt not emitted"
        txt = open(p, encoding="utf-8").read()
        assert "F5" in txt and "PARK" in txt, "llms.txt missing F5 summary"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"OK {name}")
    print("all passed")


if __name__ == "__main__":
    main()
