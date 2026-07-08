#!/usr/bin/env python3
"""G1' — recoverable WIP backups must be DISCOVERABLE.

`revert_to()` anchors pre-revert working-tree state (tracked + untracked) into a durable
`refs/ans-backup/<ts>` commit before `reset --hard` + `clean -fd`, so nothing is irrecoverable.
But the peer incident showed the refs are recoverable *in principle* yet invisible *in practice* —
the operator had to dig a backup commit out by hand. This surfaces them in the morning report with
a non-destructive restore hint, so "recoverable" means "findable". Read-only; no hot-path change.

Exit 0 = GREEN.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep.report import build_report  # noqa: E402
from agents_never_sleep.vcs import Git  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _repo_with_commit():
    repo = tempfile.mkdtemp(prefix="ue-backup-")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    with open(os.path.join(repo, "app.py"), "w") as fh:
        fh.write("print('hi')\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-qm", "init")
    return repo


def test_report_surfaces_backup_refs(failures):
    """The report names each backup ref and gives a restore hint — only when there are any."""
    empty = build_report([], backup_refs=[])
    if "ans-backup" in empty:
        failures.append("[g1'] report mentions backups when there are none (noise)")

    r = build_report([], backup_refs=[("refs/ans-backup/20260708T0900-123", "deadbee")])
    if "refs/ans-backup/20260708T0900-123" not in r:
        failures.append("[g1'] report does not name the recoverable backup ref")
    if "deadbee" not in r:
        failures.append("[g1'] report does not include the backup commit sha")
    if "git worktree add" not in r and "git restore" not in r and "git checkout" not in r:
        failures.append("[g1'] report gives no restore/inspect command for the backup")


def test_list_backup_refs_finds_a_real_revert_backup(failures):
    """After a revert_to over a DIRTY tree, list_backup_refs() enumerates the anchored ref."""
    repo = _repo_with_commit()
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    git = Git(cwd=repo)
    # Dirty the tree (tracked edit + an untracked file) so _backup_wip anchors a ref.
    with open(os.path.join(repo, "app.py"), "a") as fh:
        fh.write("# edit\n")
    with open(os.path.join(repo, "scratch.txt"), "w") as fh:
        fh.write("untracked wip\n")
    backup = git.revert_to(base)
    if not backup:
        failures.append("[g1'] revert_to over a dirty tree returned no backup sha")
    refs = git.list_backup_refs()
    if not any(ref.startswith("refs/ans-backup/") for ref, _sha in refs):
        failures.append(f"[g1'] list_backup_refs did not enumerate the anchored backup (got {refs!r})")


def main() -> int:
    failures = []
    test_report_surfaces_backup_refs(failures)
    test_list_backup_refs_finds_a_real_revert_backup(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — recoverable backups are not discoverable")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — backup refs enumerated + surfaced in the report with a restore hint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
