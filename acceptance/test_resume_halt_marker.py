#!/usr/bin/env python3
"""Item 2 — a resume-safety HALT must STOP the fresh-session launcher, not respawn into it.

The launcher's `run_fresh_session_loop` detects "done" by the run-incomplete sentinel going ABSENT.
A RunResumeUnsafe HALT raises BEFORE the driver's terminal handler, so it never clears the sentinel
(correct — state must stay intact for inspection). Without an extra signal the launcher would then
respawn a fresh agent that HALTs again, up to its respawn cap. Fix: run.py writes a durable
`resume-halt` marker in the state dir when it maps RunResumeUnsafe to HALT_RESUME_UNSAFE; the loop
checks it and stops immediately; the driver clears it once a fresh/safe run branch is (re)entered.

This tests the load-bearing cross-process contract (write-on-HALT + clear-on-healthy-entry).

Exit 0 = GREEN.
"""
import io
import contextlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep import run as run_mod  # noqa: E402
from agents_never_sleep.driver import RunResumeUnsafe, StepDriver  # noqa: E402
from agents_never_sleep.gates import GateRunner  # noqa: E402
from agents_never_sleep.ledger import AttemptLedger  # noqa: E402
from agents_never_sleep.orchestrator import Orchestrator  # noqa: E402
from agents_never_sleep.state import OutcomeStore  # noqa: E402
from agents_never_sleep.tickets import Ticket  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _repo():
    repo = tempfile.mkdtemp(prefix="ue-haltmark-")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    with open(os.path.join(repo, "app.py"), "w") as fh:
        fh.write("print('hi')\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-qm", "init")
    return repo


def _driver(repo):
    state_dir = os.path.join(repo, ".unattended", "state")
    orch = Orchestrator(
        repo_dir=repo, store=OutcomeStore(state_dir),
        gate=GateRunner(command=["true"], cwd=repo, timeout=30),
        worker=None, artifacts_dir=os.path.join(repo, ".unattended", "art"), unattended=True,
        ledger=AttemptLedger(os.path.join(state_dir, "ledger.json")),
        protect_paths=[".unattended"],
    )
    return StepDriver(orch=orch, tickets=[Ticket(id="t1", title="x", body="y", meta={}, path="")],
                      store=OutcomeStore(state_dir), state_dir=state_dir,
                      report_path=os.path.join(repo, "r.md"), config={})


def test_halt_writes_marker(failures):
    repo = _repo()
    tix = os.path.join(repo, "tix")
    os.makedirs(tix, exist_ok=True)
    marker = os.path.join(repo, ".unattended", "state", "resume-halt")

    orig = run_mod.cmd_next

    def boom(args):
        raise RunResumeUnsafe("stale run branch 'ans/run-old' cannot be resumed")
    run_mod.cmd_next = boom
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run_mod.main(["next", "--repo", repo, "--tickets", tix])
    finally:
        run_mod.cmd_next = orig

    if rc != 3:
        failures.append(f"[item2] HALT must exit 3, got {rc}")
    if not os.path.exists(marker):
        failures.append("[item2] HALT did not write the resume-halt marker the launcher watches")


def test_healthy_entry_clears_marker(failures):
    repo = _repo()
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(repo, ".unattended", "state", "run-incomplete")
    state_dir = os.path.join(repo, ".unattended", "state")
    os.makedirs(state_dir, exist_ok=True)
    marker = os.path.join(state_dir, "resume-halt")
    with open(marker, "w") as fh:
        fh.write("stale halt from a prior run\n")

    # A healthy fresh run enters/creates a run branch without HALT -> the marker must be cleared.
    r = _driver(repo).next_ticket()
    if r.get("status") != "PROCEED":
        failures.append(f"[item2] setup: expected PROCEED, got {r.get('status')!r}")
    if os.path.exists(marker):
        failures.append("[item2] a healthy run did not clear a stale resume-halt marker "
                        "(launcher would wrongly stop)")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def main() -> int:
    failures = []
    test_halt_writes_marker(failures)
    test_healthy_entry_clears_marker(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — resume-HALT does not signal the launcher to stop")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — HALT writes the stop-marker; a healthy run clears it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
