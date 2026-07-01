#!/usr/bin/env python3
"""Prove the cross-resume attempt-ledger + state-loop detection.

ticket-03 always breaks the gate. On the first pass it should be FAILED_RETRYABLE (retryable).
On a SECOND pass (a 'resume') the same failure signature recurs, loop detection trips, and the
ticket must become PARKED_DECISION ('unproductive looping') rather than retrying forever — the
exact gap a heartbeat watchdog is blind to.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from agents_never_sleep.gates import GateRunner  # noqa: E402
from agents_never_sleep.ledger import AttemptLedger  # noqa: E402
from agents_never_sleep.orchestrator import Orchestrator  # noqa: E402
from agents_never_sleep.state import OutcomeState, OutcomeStore  # noqa: E402
from agents_never_sleep.tickets import load_tickets  # noqa: E402
from agents_never_sleep.worker import DemoWorker  # noqa: E402


def build(repo, state_dir, artifacts_dir):
    gate = GateRunner(
        command=[sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"],
        cwd=repo, timeout=60,
    )
    ledger = AttemptLedger(os.path.join(state_dir, "ledger.json"))
    return Orchestrator(repo_dir=repo, store=OutcomeStore(state_dir), gate=gate,
                        worker=DemoWorker(), artifacts_dir=artifacts_dir, unattended=True,
                        ledger=ledger, loop_threshold=2)


def test_scratchpad_notes_and_digest(failures):
    """Ticket 04: append/read + redaction; the do-not-repeat digest; and the driver attaches
    notes+digest ONLY when autonomy.scratchpad.enabled is set (flag off = byte-identical payload)."""
    import types
    from agents_never_sleep import scratchpad
    from agents_never_sleep.driver import StepDriver
    from agents_never_sleep.state import ContaminationScope, TicketOutcome

    work = tempfile.mkdtemp(prefix="ue-scratch-")
    sd = os.path.join(work, "state")
    store = OutcomeStore(sd)

    # (1) append + read roundtrip; a pasted secret must be redacted, never persisted verbatim.
    scratchpad.append_note(sd, "t1", "designed the reconciler; key=sk-ant-api03-SECRETSECRET"
                                     "SECRETSECRETSECRETSECRETSECRETSECRETSECRETSECRETSECRET")
    notes = scratchpad.read_notes(sd, "t1")
    if "designed the reconciler" not in notes:
        failures.append("[scratch] note not persisted/readable")
    if "SECRETSECRETSECRET" in notes:
        failures.append("[scratch] redaction failed — a raw secret persisted in the notes")

    # (2) do-not-repeat digest from a set-aside ticket's outcome; current ticket excluded.
    store.write(TicketOutcome(ticket_id="t2", state=OutcomeState.FAILED_RETRYABLE,
                              attempted="tried approach A", exact_blocker="A breaks the gate",
                              contamination_scope=ContaminationScope.NONE))
    digest = scratchpad.do_not_repeat_digest(store, {"t1", "t2"}, current_ticket_id="t1")
    if not digest or digest[0]["ticket"] != "t2" or "A breaks" not in digest[0].get("blocker", ""):
        failures.append(f"[scratch] do_not_repeat digest wrong: {digest}")

    # (3) driver attaches ONLY with the flag on; off => the PROCEED payload is untouched.
    orch = types.SimpleNamespace(repo_dir=work)
    ticket = types.SimpleNamespace(id="t1")

    def payload_with(cfg):
        drv = StepDriver(orch=orch, tickets=[], store=store, state_dir=sd,
                         report_path=os.path.join(work, "r.md"), config=cfg)
        drv._add_skip("t2")
        p = {"status": "PROCEED"}
        drv._attach_scratchpad_hint(p, ticket)
        return p

    off = payload_with({})
    if any(k in off for k in ("notes", "do_not_repeat", "scratchpad_note")):
        failures.append(f"[scratch] flag off must not touch the payload: {off}")
    on = payload_with({"autonomy": {"scratchpad": {"enabled": True}}})
    if not all(k in on for k in ("notes", "do_not_repeat", "scratchpad_note")):
        failures.append(f"[scratch] flag on must inject notes+digest+guidance: {on}")


def test_notes_survive_git_revert(failures):
    """The scratchpad file lives under .unattended/ → gitignored + protected → it survives the
    revert that rolls the CODE back to green (the whole point: keep reasoning, discard bad edits)."""
    import subprocess
    from agents_never_sleep import scratchpad
    from agents_never_sleep.vcs import Git

    work = tempfile.mkdtemp(prefix="ue-scratch-git-")
    for a in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
              ["git", "config", "user.name", "t"]):
        subprocess.run(a, cwd=work, check=True)
    code = os.path.join(work, "code.py")
    with open(code, "w") as fh:
        fh.write("value = 1\n")
    git = Git(work)
    base = git.commit_all("baseline")            # ensures .unattended/ is gitignored

    sd = os.path.join(work, ".unattended", "state")
    scratchpad.append_note(sd, "t1", "the design decision that must outlive a revert")
    with open(code, "w") as fh:                  # a bad edit the gate would reject
        fh.write("value = BROKEN\n")
    git.revert_to(base)

    if "must outlive a revert" not in scratchpad.read_notes(sd, "t1"):
        failures.append("[scratch] notes did NOT survive the git revert")
    with open(code) as fh:
        if fh.read().strip() != "value = 1":
            failures.append("[scratch] code was not reverted to baseline by revert_to")


def test_cmd_note_redacts_patternless_env_secret(failures):
    """cmd_note must populate the redaction registry (as _Context does) so a PATTERN-LESS env/creds
    key never lands verbatim on disk — the whole no-leak guarantee. Exercises the real CLI path
    (finding 1 of the ticket-04 review), with a value that has NO sk-/tok_live_ shape."""
    import subprocess
    secret = "ZZ9pQ7wR3tN6vB1mKx4Ld"  # pattern-less, >= _MIN_SECRET_LEN; only the registry catches it
    work = tempfile.mkdtemp(prefix="ue-note-redact-")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    env = dict(os.environ, TOKONOMIX_API_KEY=secret, PYTHONPATH=SKILL_ROOT)
    subprocess.run([sys.executable, "-m", "agents_never_sleep.run", "note", "--repo", work,
                    "--ticket", "t1", "--text", f"my key is {secret} do not leak"],
                   cwd=work, env=env, check=True, capture_output=True)
    path = os.path.join(work, ".unattended", "state", "t1.notes.md")
    notes = open(path).read() if os.path.exists(path) else ""
    if secret in notes:
        failures.append("[note-redact] pattern-less env secret leaked verbatim into notes on disk")
    if "my key is" not in notes:
        failures.append("[note-redact] note body not written at all")


def main() -> int:
    failures: list = []
    work = tempfile.mkdtemp(prefix="ue-resume-")
    repo = os.path.join(work, "repo")
    shutil.copytree(os.path.join(HERE, "sandbox"), repo)
    state_dir, artifacts_dir = os.path.join(work, "state"), os.path.join(work, "art")
    tickets = [t for t in load_tickets(os.path.join(HERE, "tickets")) if t.id == "ticket-03-redgate"]

    r1 = build(repo, state_dir, artifacts_dir).run(tickets)
    s1 = r1.outcomes[0].state
    r2 = build(repo, state_dir, artifacts_dir).run(tickets)   # resume: same state dir + ledger
    s2 = r2.outcomes[0].state
    attempts = r2.outcomes[0].attempts

    print(f"pass 1: {s1.value}  ->  pass 2 (resume): {s2.value}  (attempts={attempts})")
    if not (s1 == OutcomeState.FAILED_RETRYABLE and s2 == OutcomeState.PARKED_DECISION):
        failures.append("[resume] loop-detection did not park the repeated failure")

    test_scratchpad_notes_and_digest(failures)
    test_notes_survive_git_revert(failures)
    test_cmd_note_redacts_patternless_env_secret(failures)

    if failures:
        print("RESULT: ❌ RED — resume/scratchpad guarantees not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — loop detected+parked on resume; scratchpad notes survive a revert, "
          "redact secrets, and inject (flag-on) / stay silent (flag-off)")
    print(f"workdir: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
