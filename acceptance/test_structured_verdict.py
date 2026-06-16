#!/usr/bin/env python3
"""Structured-verdict test (opt-in) — close the self-reported-verdict gap.

The trust decision normally reaches the harness via the AGENT (`complete --council-verdict ...`) —
the controlled party summarizing its own review. When `council.structured_verdict` is ON, the harness
instead PARSES a machine-readable verdict artifact the council produced and DERIVES the gate itself.

Proven here with NO live LLM call:
  * the pure derivation (`verdict_from_structured`) is FAIL-SAFE — malformed/empty/no-proposer → ERROR,
    a material open issue can only DOWNGRADE an explicit `overall`, never upgrade it;
  * `structured_verdict_enabled` is default-OFF and needs the council on;
  * end-to-end through the real StepDriver: flag OFF → identical behavior (artifact ignored, the
    agent's --council-verdict wins); flag ON → the harness derives the disposition from the artifact
    with NO agent --council-verdict value.

Exit 0 = GREEN.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from harness import council  # noqa: E402
from harness.council import CouncilTier, CouncilVerdict  # noqa: E402
from harness.driver import StepDriver  # noqa: E402
from harness.gates import GateRunner  # noqa: E402
from harness.ledger import AttemptLedger  # noqa: E402
from harness.orchestrator import Orchestrator  # noqa: E402
from harness.state import OutcomeState, OutcomeStore  # noqa: E402
from harness.tickets import load_tickets  # noqa: E402


def _council_cfg(structured=False, enabled=True, tokonomix=True):
    return {
        "gates": [{"name": "tests", "command": [sys.executable, "-m", "unittest", "discover",
                                                "-s", ".", "-p", "test_*.py"], "blocking": True}],
        "integrations": {"tokonomix": {"enabled": tokonomix}},
        "council": {
            "enabled": enabled,
            "structured_verdict": structured,
            "light": {"proposers": ["a", "b"], "judges": ["j1"], "mode": "consensus", "max_tokens": 800},
            "heavy": {"proposers": ["a", "b", "c"], "judges": ["j1", "j2"], "mode": "consensus",
                      "max_tokens": 1200},
            "prices_cents_per_mtok": {"a": [50, 250], "b": [25, 150], "c": [25, 38],
                                      "j1": [50, 250], "j2": [25, 150]},
        },
    }


# ---- pure derivation -----------------------------------------------------------------------------

def test_enabled_flag(failures):
    if council.structured_verdict_enabled(_council_cfg(structured=False)):
        failures.append("[flag] default (absent/false) must be OFF")
    if council.structured_verdict_enabled({"council": {"structured_verdict": True}}):
        failures.append("[flag] must be OFF when council is not enabled (needs council on)")
    if not council.structured_verdict_enabled(_council_cfg(structured=True)):
        failures.append("[flag] should be ON with council enabled + structured_verdict true")


def test_derive_clean(failures):
    v, cov = council.verdict_from_structured(
        {"overall": "pass", "issues": [], "proposers": ["m1", "m2"], "judge": "j"}, CouncilTier.HEAVY)
    if v != CouncilVerdict.PASS:
        failures.append(f"[derive] clean artifact should be PASS, got {v}")
    if "structured-verdict" not in cov or "proposers=m1,m2" not in cov:
        failures.append(f"[derive] coverage must record harness-derived provenance: {cov!r}")


def test_derive_material_open_concerns(failures):
    v, _ = council.verdict_from_structured(
        {"issues": [{"severity": "high", "status": "open", "title": "auth bypass"}],
         "proposers": ["m1"], "judge": "j"}, CouncilTier.HEAVY)
    if v != CouncilVerdict.CONCERNS:
        failures.append(f"[derive] open HIGH issue should be CONCERNS, got {v}")


def test_derive_downgrade_only(failures):
    # an explicit "pass" that still carries a material OPEN issue can only be DOWNGRADED to concerns.
    v, _ = council.verdict_from_structured(
        {"overall": "pass", "issues": [{"severity": "critical", "status": "open"}],
         "proposers": ["m1"]}, CouncilTier.HEAVY)
    if v != CouncilVerdict.CONCERNS:
        failures.append(f"[derive] overall=pass + open material issue must downgrade to CONCERNS, got {v}")


def test_derive_resolved_is_pass(failures):
    v, _ = council.verdict_from_structured(
        {"issues": [{"severity": "high", "status": "resolved"},
                    {"severity": "low", "status": "open"}],
         "proposers": ["m1"]}, CouncilTier.HEAVY)
    if v != CouncilVerdict.PASS:
        failures.append(f"[derive] only resolved/low issues should be PASS, got {v}")


def test_derive_failsafe(failures):
    if council.verdict_from_structured("not-a-dict", CouncilTier.HEAVY)[0] != CouncilVerdict.ERROR:
        failures.append("[derive] malformed artifact must be ERROR")
    if council.verdict_from_structured({"issues": [], "proposers": []},
                                       CouncilTier.HEAVY)[0] != CouncilVerdict.ERROR:
        failures.append("[derive] no proposers ran → ERROR (blind spot)")
    if council.verdict_from_structured({"overall": "weird", "proposers": ["m1"]},
                                       CouncilTier.HEAVY)[0] != CouncilVerdict.CONCERNS:
        failures.append("[derive] unrecognized overall must fail-safe to CONCERNS")


# ---- end-to-end through the real StepDriver -------------------------------------------------------

def _run_ticket01(cfg, *, artifact=None, council_verdict=None):
    """Drive the sandbox: implement a HEAVY auth diff for ticket-01 and complete it with the given
    artifact / agent verdict; benign-complete the rest. Return ticket-01's recorded outcome."""
    work = tempfile.mkdtemp(prefix="ue-sv-")
    repo = os.path.join(work, "repo")
    shutil.copytree(os.path.join(HERE, "sandbox"), repo)
    state_dir = os.path.join(work, "state")
    tickets = load_tickets(os.path.join(HERE, "tickets"))
    store = OutcomeStore(state_dir)
    gate = GateRunner(command=[sys.executable, "-m", "unittest", "discover", "-s", ".",
                               "-p", "test_*.py"], cwd=repo, timeout=60)
    ledger = AttemptLedger(os.path.join(state_dir, "ledger.json"))
    orch = Orchestrator(repo_dir=repo, store=store, gate=gate, worker=None,
                        artifacts_dir=os.path.join(work, "artifacts"), unattended=True, ledger=ledger)
    driver = StepDriver(orch=orch, tickets=tickets, store=store, state_dir=state_dir,
                        report_path=os.path.join(work, "report.md"), config=cfg)
    for _ in range(20):
        res = driver.next_ticket()
        if res["status"] != "PROCEED":
            break
        if res["ticket"]["id"] == "ticket-01-trivial":
            with open(os.path.join(repo, "auth.py"), "w", encoding="utf-8") as fh:
                fh.write("def authorize(jwt_token):\n    return bool(jwt_token)\n")
            driver.complete_ticket(attempted="auth", council_verdict=council_verdict,
                                   council_verdict_artifact=artifact, council_cost_eur=0.05)
        else:
            with open(os.path.join(repo, "note.py"), "a", encoding="utf-8") as fh:
                fh.write("\n# note\n")
            driver.complete_ticket(attempted="note", council_verdict="pass")
    return store.read("ticket-01-trivial")


def test_e2e_flag_off_ignores_artifact(failures):
    # Flag OFF: a CONCERNS artifact must be ignored; the agent's "pass" self-report wins → DONE.
    artifact = {"issues": [{"severity": "high", "status": "open"}], "proposers": ["m1"]}
    o = _run_ticket01(_council_cfg(structured=False), artifact=artifact, council_verdict="pass")
    if o is None or o.state != OutcomeState.DONE:
        failures.append(f"[e2e off] flag OFF must keep agent-verdict behavior (DONE), got "
                        f"{getattr(o, 'state', None)}")
    elif "structured-verdict" in (o.review_coverage or ""):
        failures.append("[e2e off] artifact must NOT be consulted when the flag is off")


def test_e2e_flag_on_derives_from_artifact(failures):
    # Flag ON: NO agent --council-verdict; the harness derives CONCERNS from the artifact on a HEAVY
    # diff → DONE_LOW_CONFIDENCE + needs-daylight, coverage shows it was harness-parsed.
    artifact = {"issues": [{"severity": "high", "status": "open", "title": "auth bypass"}],
                "proposers": ["gpt-5.4", "gemini-2.5-pro"], "judge": "claude-opus-4-8"}
    o = _run_ticket01(_council_cfg(structured=True), artifact=artifact, council_verdict=None)
    if o is None or o.state != OutcomeState.DONE_LOW_CONFIDENCE:
        failures.append(f"[e2e on] harness-derived CONCERNS on HEAVY diff should be "
                        f"DONE_LOW_CONFIDENCE, got {getattr(o, 'state', None)}")
        return
    cov = o.review_coverage or ""
    if "structured-verdict" not in cov or "NEEDS-DAYLIGHT-REVIEW" not in cov:
        failures.append(f"[e2e on] coverage must show harness-parsed verdict + daylight: {cov!r}")


def test_e2e_flag_on_clean_artifact_trusts(failures):
    # Flag ON + a clean artifact (no material issue) on a HEAVY diff → derived PASS → DONE.
    artifact = {"overall": "pass", "issues": [{"severity": "low", "status": "open"}],
                "proposers": ["gpt-5.4", "gemini-2.5-pro"], "judge": "claude-opus-4-8"}
    o = _run_ticket01(_council_cfg(structured=True), artifact=artifact, council_verdict=None)
    if o is None or o.state != OutcomeState.DONE:
        failures.append(f"[e2e on clean] clean artifact should auto-trust (DONE), got "
                        f"{getattr(o, 'state', None)}")


def main() -> int:
    failures = []
    for t in (test_enabled_flag, test_derive_clean, test_derive_material_open_concerns,
              test_derive_downgrade_only, test_derive_resolved_is_pass, test_derive_failsafe,
              test_e2e_flag_off_ignores_artifact, test_e2e_flag_on_derives_from_artifact,
              test_e2e_flag_on_clean_artifact_trusts):
        t(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — structured-verdict path not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — derivation fail-safe, flag default-OFF, and end-to-end OFF/ON wiring hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
