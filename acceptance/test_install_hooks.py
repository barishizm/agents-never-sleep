#!/usr/bin/env python3
"""Install-automation test — hooks/install.sh wires a platform snippet in one command.

The per-platform enforcement snippets (hooks/platforms/*) used to require a manual copy + a hand
edit of the `<SKILL_DIR>` placeholder. install.sh does that deterministically. These tests prove,
hermetically (no real platform tool needed): the snippet is rendered with the placeholder replaced
by the chosen skill dir, the output is still valid JSON, dry-run writes nothing, --apply writes the
target, and an unknown platform fails cleanly.

Exit 0 = GREEN.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
INSTALL = os.path.join(SKILL_ROOT, "hooks", "install.sh")

# Platforms whose snippet is a single JSON file we can render + validate hermetically.
PLATFORMS = ["gemini", "codex", "copilot", "cursor", "windsurf"]
FAKE_SKILL = "/opt/FAKE-SKILL-DIR"


def _run(args):
    return subprocess.run([INSTALL, *args], capture_output=True, text=True)


def test_script_exists_executable(failures):
    if not os.path.exists(INSTALL):
        failures.append(f"[exists] {INSTALL} missing")
    elif not os.access(INSTALL, os.X_OK):
        failures.append("[exists] install.sh not executable")


def test_apply_renders_valid_json_without_placeholder(failures):
    for p in PLATFORMS:
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, f"{p}.json")
            r = _run([p, "--skill-dir", FAKE_SKILL, "--target", target, "--apply"])
            if r.returncode != 0:
                failures.append(f"[apply:{p}] non-zero exit: {r.stderr.strip()[:120]}")
                continue
            if not os.path.exists(target):
                failures.append(f"[apply:{p}] target not written")
                continue
            text = open(target, encoding="utf-8").read()
            if "<SKILL_DIR>" in text:
                failures.append(f"[apply:{p}] placeholder <SKILL_DIR> not substituted")
            if FAKE_SKILL not in text:
                failures.append(f"[apply:{p}] chosen skill dir not present in output")
            try:
                json.loads(text)
            except json.JSONDecodeError as e:
                failures.append(f"[apply:{p}] rendered output is not valid JSON: {e}")


def test_dry_run_writes_nothing_but_prints(failures):
    p = "gemini"
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "out.json")
        r = _run([p, "--skill-dir", FAKE_SKILL, "--target", target])  # no --apply
        if r.returncode != 0:
            failures.append(f"[dry] non-zero exit: {r.stderr.strip()[:120]}")
        if os.path.exists(target):
            failures.append("[dry] dry-run must NOT write the target")
        if FAKE_SKILL not in r.stdout:
            failures.append("[dry] dry-run should print the rendered snippet to stdout")
        if "<SKILL_DIR>" in r.stdout:
            failures.append("[dry] dry-run output still has the placeholder")


def test_unknown_platform_fails(failures):
    r = _run(["nosuchplatform", "--skill-dir", FAKE_SKILL])
    if r.returncode == 0:
        failures.append("[unknown] unknown platform should exit non-zero")


def test_default_skill_dir_is_real_skill_root(failures):
    # Without --skill-dir, the placeholder must resolve to the real installed skill root (so the
    # wired hook actually points at this skill's enforce.sh).
    r = _run(["gemini"])  # dry-run, default skill dir
    if r.returncode != 0:
        failures.append(f"[default] non-zero exit: {r.stderr.strip()[:120]}")
    if SKILL_ROOT not in r.stdout:
        failures.append("[default] default skill dir should be the real skill root")


def main() -> int:
    failures = []
    test_script_exists_executable(failures)
    if not os.path.exists(INSTALL):
        print("RESULT: ❌ RED — install.sh missing")
        return 1
    test_apply_renders_valid_json_without_placeholder(failures)
    test_dry_run_writes_nothing_but_prints(failures)
    test_unknown_platform_fails(failures)
    test_default_skill_dir_is_real_skill_root(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — install automation not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — one-command per-platform hook install renders valid, placeholder-free JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
