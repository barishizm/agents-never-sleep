#!/usr/bin/env python3
"""G4a — detect running unisolated in a live/shared working tree, and gate on it.

ANS runs IN-PLACE in the primary working tree. When that tree is shared and DIRTY, the harness's
own destructive git ops act on live work (the einstein-saas incident class). This measures the risk
ONCE at run start — `primary_worktree AND not clean` — and applies a tri-state policy
`autonomy.live_tree`: warn (default, non-breaking) | ack (silent) | require_isolation (HALT before
any run branch). A clean tree or a linked `git worktree` is never flagged.

Exit 0 = GREEN.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep.driver import StepDriver, live_tree_decision  # noqa: E402
from agents_never_sleep.gates import GateRunner  # noqa: E402
from agents_never_sleep.ledger import AttemptLedger  # noqa: E402
from agents_never_sleep.orchestrator import Orchestrator  # noqa: E402
from agents_never_sleep.state import OutcomeStore  # noqa: E402
from agents_never_sleep.tickets import Ticket  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _new_repo():
    repo = tempfile.mkdtemp(prefix="ue-livetree-")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    with open(os.path.join(repo, "app.py"), "w") as fh:
        fh.write("print('hi')\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-qm", "init")
    return repo


def _driver(repo, work, config=None):
    state_dir = os.path.join(work, "state")
    orch = Orchestrator(
        repo_dir=repo, store=OutcomeStore(state_dir),
        gate=GateRunner(command=["true"], cwd=repo, timeout=30),
        worker=None, artifacts_dir=os.path.join(work, "art"), unattended=True,
        ledger=AttemptLedger(os.path.join(state_dir, "ledger.json")),
        protect_paths=[".unattended"],
    )
    return StepDriver(orch=orch, tickets=[Ticket(id="t1", title="x", body="y", meta={}, path="")],
                      store=OutcomeStore(state_dir), state_dir=state_dir,
                      report_path=os.path.join(repo, "night-report.md"), config=config or {})


def _dirty(repo):
    with open(os.path.join(repo, "untracked-wip.txt"), "w") as fh:
        fh.write("live work a human might lose\n")


def _branches(repo):
    return _git(repo, "branch").stdout


def test_decision_table(failures):
    T = live_tree_decision
    cases = [
        # (is_linked, is_clean, policy) -> expected
        ((False, False, "warn"), "warn"),
        ((False, False, "ack"), "ok"),
        ((False, False, "require_isolation"), "halt"),
        ((False, False, None), "warn"),          # missing policy defaults to warn
        ((True,  False, "require_isolation"), "ok"),   # linked worktree = isolated
        ((False, True,  "require_isolation"), "ok"),   # clean tree = nothing clobberable
        ((True,  True,  "warn"), "ok"),
    ]
    for args, want in cases:
        got = T(*args)
        if got != want:
            failures.append(f"[g4a] live_tree_decision{args} = {got!r}, expected {want!r}")


def test_warn_default_surfaces_but_proceeds(failures):
    repo = _new_repo()
    work = tempfile.mkdtemp(prefix="ue-livetree-wk-")
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(work, "state", "run-incomplete")
    _dirty(repo)  # primary + dirty, default policy (warn)
    note = os.path.join(work, "state", "live-tree-note")

    r1 = _driver(repo, work).next_ticket()
    if r1.get("status") != "PROCEED":
        failures.append(f"[g4a] warn must not block; got {r1.get('status')!r}")
    if not os.path.exists(note):
        failures.append("[g4a] warn did not persist a live-tree note for the report")
    # Run to terminal; the morning report must name the risk.
    with open(os.path.join(repo, "app.py"), "a") as fh:
        fh.write("# work\n")
    _driver(repo, work).complete_ticket(attempted="did it")
    _driver(repo, work).next_ticket()  # drain -> terminal -> writes report
    report = open(os.path.join(repo, "night-report.md"), encoding="utf-8").read()
    if "live" not in report.lower() or "tree" not in report.lower():
        failures.append("[g4a] morning report does not surface the live-tree risk under warn")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def test_ack_silences(failures):
    repo = _new_repo()
    work = tempfile.mkdtemp(prefix="ue-livetree-wk-")
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(work, "state", "run-incomplete")
    _dirty(repo)
    note = os.path.join(work, "state", "live-tree-note")
    r1 = _driver(repo, work, {"autonomy": {"live_tree": "ack"}}).next_ticket()
    if r1.get("status") != "PROCEED":
        failures.append(f"[g4a] ack must proceed; got {r1.get('status')!r}")
    if os.path.exists(note):
        failures.append("[g4a] ack must NOT emit a live-tree warning")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def test_require_isolation_halts_before_branch(failures):
    repo = _new_repo()
    work = tempfile.mkdtemp(prefix="ue-livetree-wk-")
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(work, "state", "run-incomplete")
    _dirty(repo)
    r1 = _driver(repo, work, {"autonomy": {"live_tree": "require_isolation"}}).next_ticket()
    if r1.get("status") != "HALTED":
        failures.append(f"[g4a] require_isolation on a dirty primary tree must HALT; got {r1.get('status')!r}")
    if "ans/run-" in _branches(repo):
        failures.append("[g4a] HALT must fire BEFORE any run branch is created")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def test_clean_primary_no_warning(failures):
    repo = _new_repo()  # clean tree
    work = tempfile.mkdtemp(prefix="ue-livetree-wk-")
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(work, "state", "run-incomplete")
    note = os.path.join(work, "state", "live-tree-note")
    _driver(repo, work).next_ticket()
    if os.path.exists(note):
        failures.append("[g4a] a clean primary tree must not be flagged")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def test_linked_worktree_no_warning(failures):
    repo = _new_repo()
    wt = tempfile.mkdtemp(prefix="ue-livetree-linked-")
    os.rmdir(wt)  # git worktree add wants a non-existing path
    r = _git(repo, "worktree", "add", "-q", "-b", "wt-branch", wt)  # own branch (main is checked out)
    if r.returncode != 0:
        failures.append(f"[g4a] setup: git worktree add failed: {r.stderr.strip()}")
        return
    work = tempfile.mkdtemp(prefix="ue-livetree-wk-")
    os.environ["UE_RUN_INCOMPLETE"] = os.path.join(work, "state", "run-incomplete")
    with open(os.path.join(wt, "untracked-wip.txt"), "w") as fh:
        fh.write("dirty but isolated\n")
    note = os.path.join(work, "state", "live-tree-note")
    # Drive the harness against the LINKED worktree (isolated) — must never warn.
    _driver(wt, work).next_ticket()
    if os.path.exists(note):
        failures.append("[g4a] a linked git worktree is isolated and must not be flagged")
    os.environ.pop("UE_RUN_INCOMPLETE", None)


def main() -> int:
    failures = []
    test_decision_table(failures)
    test_warn_default_surfaces_but_proceeds(failures)
    test_ack_silences(failures)
    test_require_isolation_halts_before_branch(failures)
    test_clean_primary_no_warning(failures)
    test_linked_worktree_no_warning(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — live-tree isolation gate not implemented")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — live-tree risk detected once at start; warn/ack/require_isolation honored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
