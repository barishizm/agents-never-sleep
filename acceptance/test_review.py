#!/usr/bin/env python3
"""Rotated review-loop test (INT-1729) — panel rotation, zero-overlap policy, convergence, degrade ladder.

The rotated loop is OPT-IN (council.enabled + council.review.rotate). Its premise, proven empirically
2026-06-07: a panel that confirms its OWN prior review shares blind spots — only an INDEPENDENT
(zero-model-overlap) panel that confirms with no new material issue counts as convergence. The harness
owns the deterministic scaffolding (panel build + disjointness validation, alternation, convergence
evaluation, the budget degrade ladder, and the cap disposition); the AGENT runs the actual review
rounds via the tokonomix MCP. These tests prove the scaffolding with NO live LLM call.

Exit 0 = GREEN.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, SKILL_ROOT)

from harness import config as cfgmod  # noqa: E402
from harness import council  # noqa: E402
from harness.council import CouncilVerdict, Panel, ReviewMode, ReviewOutcome  # noqa: E402
from harness.state import OutcomeState  # noqa: E402

# Two zero-model-overlap panels (the empirically-proven shape: propose-panel + an independent
# verify-panel with no shared model slug and a different judge family).
PROPOSE = {"proposers": ["claude-opus-4-8", "gemini-2.5-pro", "deepseek/deepseek-v3.2"],
           "judges": ["claude-sonnet-4-6"]}
VERIFY = {"proposers": ["gpt-5.4", "gemini-3.1-pro", "deepseek/deepseek-v4"],
          "judges": ["gpt-5.4-mini"]}


def _cfg(rotate=True, enabled=True, tokonomix=True, max_rounds=3, budget=None, panels="default"):
    if panels == "default":
        panels = {"propose": dict(PROPOSE), "verify": dict(VERIFY)}
    return {
        "integrations": {"tokonomix": {"enabled": tokonomix}},
        "budget": budget or {"per_night_euro_cap": 100.0, "max_council_calls_per_night": 50,
                             "balance_threshold_euro": 1.0, "on_credits_exhausted": "stop"},
        "council": {
            "enabled": enabled,
            "light": {"proposers": ["a", "b"], "judges": ["j"], "mode": "consensus", "max_tokens": 900},
            "heavy": {"proposers": ["a", "b", "c"], "judges": ["j"], "mode": "consensus",
                      "max_tokens": 1400},
            "prices_cents_per_mtok": {},
            "review": {"rotate": rotate, "max_rounds": max_rounds, "panels": panels},
        },
    }


def test_review_enabled(failures):
    if not council.review_enabled(_cfg(rotate=True)):
        failures.append("[enabled] rotate=true + council on -> review enabled")
    if council.review_enabled(_cfg(rotate=False)):
        failures.append("[enabled] rotate=false -> review NOT enabled")
    if council.review_enabled(_cfg(rotate=True, enabled=False)):
        failures.append("[enabled] council disabled -> review NOT enabled")
    if council.review_enabled(_cfg(rotate=True, tokonomix=False)):
        failures.append("[enabled] tokonomix off -> review NOT enabled")
    if council.review_max_rounds(_cfg(max_rounds=5)) != 5:
        failures.append("[enabled] max_rounds should read from config")
    if council.review_max_rounds({"council": {"review": {}}}) != 3:
        failures.append("[enabled] max_rounds default should be 3")


def test_build_and_validate_panels(failures):
    p, v = council.build_panels(_cfg())
    if not isinstance(p, Panel) or not isinstance(v, Panel):
        failures.append("[panels] build_panels should return two Panel objects")
    if p.id == v.id:
        failures.append("[panels] the two panels must have distinct ids")
    ok, overlap = council.validate_rotation(p, v)
    if not ok or overlap:
        failures.append(f"[panels] proven panels are slug-disjoint -> ok, got ok={ok} overlap={overlap}")
    # an overlapping pair must be rejected by the hard zero-overlap policy
    bad_a = Panel(id="A", proposers=["gpt-5.4", "gemini-2.5-pro"], judges=["j1"])
    bad_b = Panel(id="B", proposers=["gpt-5.4", "deepseek/deepseek-v4"], judges=["j2"])  # gpt-5.4 shared
    ok2, overlap2 = council.validate_rotation(bad_a, bad_b)
    if ok2 or "gpt-5.4" not in overlap2:
        failures.append(f"[panels] shared model slug must fail validation, got ok={ok2} overlap={overlap2}")
    # a shared JUDGE is also an overlap (judges count toward the panel membership)
    jb_a = Panel(id="A", proposers=["x1"], judges=["shared-judge"])
    jb_b = Panel(id="B", proposers=["y1"], judges=["shared-judge"])
    ok3, overlap3 = council.validate_rotation(jb_a, jb_b)
    if ok3 or "shared-judge" not in overlap3:
        failures.append("[panels] shared judge must fail validation")
    # a provider-prefixed ALIAS of the same model is NOT an independent panel
    alias_a = Panel(id="A", proposers=["gemini-2.5-pro"], judges=["j1"])
    alias_b = Panel(id="B", proposers=["google/gemini-2.5-pro"], judges=["j2"])
    ok4, _ = council.validate_rotation(alias_a, alias_b)
    if ok4:
        failures.append("[panels] provider-prefixed alias of the same model must count as overlap")


def test_rotation_ready_degrades_on_bad_config(failures):
    # rotation_ready is the non-raising guard the driver uses to decide degrade-to-single
    ready, _ = council.rotation_ready(_cfg())
    if not ready:
        failures.append("[ready] valid disjoint panels -> ready")
    # missing panels
    ready2, _ = council.rotation_ready(_cfg(panels={}))
    if ready2:
        failures.append("[ready] missing panels -> NOT ready")
    # overlapping panels
    bad = {"propose": {"proposers": ["gpt-5.4"], "judges": ["j"]},
           "verify": {"proposers": ["gpt-5.4"], "judges": ["k"]}}
    ready3, reason3 = council.rotation_ready(_cfg(panels=bad))
    if ready3 or not reason3:
        failures.append("[ready] overlapping panels -> NOT ready, with a reason")


def test_select_panel_alternation(failures):
    p, v = council.build_panels(_cfg())
    seq = [council.select_panel(p, v, i).id for i in range(4)]
    if seq != [p.id, v.id, p.id, v.id]:
        failures.append(f"[select] rounds must alternate propose/verify, got {seq}")


def test_evaluate_convergence(failures):
    PASS, CONC, ERR = CouncilVerdict.PASS, CouncilVerdict.CONCERNS, CouncilVerdict.ERROR
    cases = [
        # (rounds as (panel,verdict), max_rounds, expected outcome)
        ([], 3, ReviewOutcome.CONTINUE),                                  # nothing yet -> run round 1
        ([("A", PASS)], 3, ReviewOutcome.CONTINUE),                       # 1 panel pass != convergence
        ([("A", PASS), ("B", PASS)], 3, ReviewOutcome.CONVERGED),         # rotated panel confirms
        ([("A", CONC), ("B", PASS)], 3, ReviewOutcome.CONVERGED),         # fixed, rotated panel confirms
        ([("A", PASS), ("B", CONC)], 3, ReviewOutcome.CONTINUE),          # rotated panel found new issue
        ([("A", PASS), ("B", CONC), ("A", PASS)], 3, ReviewOutcome.CONVERGED),  # next rotation confirms
        ([("A", PASS), ("A", PASS)], 3, ReviewOutcome.CONTINUE),          # SAME panel twice != convergence
        ([("A", PASS), ("B", CONC)], 2, ReviewOutcome.CAP_EXHAUSTED),     # cap hit unconfirmed
        ([("A", PASS), ("B", ERR)], 2, ReviewOutcome.CAP_EXHAUSTED),      # blind-spot error at cap
        ([("A", PASS), ("B", ERR)], 3, ReviewOutcome.CONTINUE),           # error -> not a confirmation
        # a PASS confirming a prior round that did NOT deliver a real review (ERROR/SKIPPED) is only a
        # SINGLE effective review — must NOT converge (the core blind-spot guarantee).
        ([("A", ERR), ("B", PASS)], 3, ReviewOutcome.CONTINUE),           # prev errored -> no real pair
        ([("A", council.CouncilVerdict.SKIPPED), ("B", PASS)], 3, ReviewOutcome.CONTINUE),  # prev skipped
        ([("A", ERR), ("B", PASS)], 2, ReviewOutcome.CAP_EXHAUSTED),      # error-prev unconfirmed at cap
    ]
    for rounds, mx, want in cases:
        got = council.evaluate_review(rounds, mx)
        if got != want:
            failures.append(f"[converge] rounds={[(p, v.value) for p, v in rounds]} max={mx}: "
                            f"{got} != {want}")


def test_review_mode_ladder(failures):
    HIGH = 1000.0
    # council off -> deterministic
    if council.review_mode(_cfg(enabled=False), {}, balance_eur=HIGH) != ReviewMode.DETERMINISTIC:
        failures.append("[mode] council off -> DETERMINISTIC")
    # council on, rotate off -> single advisory
    if council.review_mode(_cfg(rotate=False), {}, balance_eur=HIGH) != ReviewMode.SINGLE:
        failures.append("[mode] rotate off -> SINGLE")
    # rotate on, budget healthy -> rotate
    if council.review_mode(_cfg(), {}, balance_eur=HIGH) != ReviewMode.ROTATE:
        failures.append("[mode] rotate on + budget ok -> ROTATE")
    # balance below threshold -> no council at all -> deterministic
    if council.review_mode(_cfg(), {}, balance_eur=0.10) != ReviewMode.DETERMINISTIC:
        failures.append("[mode] balance below threshold -> DETERMINISTIC")
    # http 402 -> deterministic
    if council.review_mode(_cfg(), {}, balance_eur=HIGH, http_402=True) != ReviewMode.DETERMINISTIC:
        failures.append("[mode] http 402 -> DETERMINISTIC")
    # only room for one more call -> can't rotate -> single
    one_call = {"max_council_calls_per_night": 1, "balance_threshold_euro": 1.0}
    if council.review_mode(_cfg(budget=one_call), {"council_calls": 0}, balance_eur=HIGH) != \
            ReviewMode.SINGLE:
        failures.append("[mode] <2 calls remaining -> degrade to SINGLE")
    # euro-cap-only config (no call cap): the ladder must forward-check EUROS, not just call count.
    # One rotated round on the default test panels estimates ≈€0.20.
    euro_cap = {"per_night_euro_cap": 1.0, "balance_threshold_euro": 1.0}
    if council.review_mode(_cfg(budget=euro_cap), {"council_cost_eur": 0.95}, balance_eur=HIGH) != \
            ReviewMode.DETERMINISTIC:
        failures.append("[mode] euro-cap: <1 round of headroom -> DETERMINISTIC")
    if council.review_mode(_cfg(budget=euro_cap), {"council_cost_eur": 0.70}, balance_eur=HIGH) != \
            ReviewMode.SINGLE:
        failures.append("[mode] euro-cap: room for 1 round but not 2 -> SINGLE")
    if council.review_mode(_cfg(budget=euro_cap), {"council_cost_eur": 0.0}, balance_eur=HIGH) != \
            ReviewMode.ROTATE:
        failures.append("[mode] euro-cap: ample headroom -> ROTATE")


def test_review_disposition(failures):
    conv = council.review_disposition(ReviewOutcome.CONVERGED, ticket_title="t")
    if conv.state != OutcomeState.DONE or conv.needs_daylight_review:
        failures.append("[disp] CONVERGED -> DONE, no daylight")
    cap = council.review_disposition(ReviewOutcome.CAP_EXHAUSTED, ticket_title="t")
    if cap.state != OutcomeState.DONE_LOW_CONFIDENCE or not cap.needs_daylight_review:
        failures.append("[disp] CAP_EXHAUSTED -> DONE_LOW_CONFIDENCE + daylight")
    if "NEEDS-DAYLIGHT-REVIEW" not in (cap.review_coverage or ""):
        failures.append("[disp] CAP_EXHAUSTED coverage must carry the daylight tag")


def test_round_cost_estimate(failures):
    p, v = council.build_panels(_cfg())
    c = council.estimate_review_round_eur(_cfg(), p)
    if c <= 0:
        failures.append(f"[cost] per-round estimate should be > 0, got {c}")


def test_default_config_has_disjoint_review_block(failures):
    class _Prof:
        platform = "x"; exec_mode = "y"; expected_yield = "z"; warnings = []
        gates = []; has_vault = False; has_paperclip = False; has_tokonomix = True
    cfg = cfgmod.default_config(_Prof())
    review = (cfg.get("council", {}) or {}).get("review")
    if not review:
        failures.append("[default] default_config must carry a council.review block")
        return
    if review.get("rotate") is not False:
        failures.append("[default] review.rotate must DEFAULT to False (opt-in)")
    if review.get("max_rounds") != 3:
        failures.append("[default] review.max_rounds default should be 3")
    p, vv = council.build_panels(cfg)
    ok, overlap = council.validate_rotation(p, vv)
    if not ok:
        failures.append(f"[default] shipped default panels must be slug-disjoint, overlap={overlap}")


def main() -> int:
    failures = []
    test_review_enabled(failures)
    test_build_and_validate_panels(failures)
    test_rotation_ready_degrades_on_bad_config(failures)
    test_select_panel_alternation(failures)
    test_evaluate_convergence(failures)
    test_review_mode_ladder(failures)
    test_review_disposition(failures)
    test_round_cost_estimate(failures)
    test_default_config_has_disjoint_review_block(failures)
    print("=" * 60)
    if failures:
        print("RESULT: ❌ RED — rotated review-loop not proven")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ✅ GREEN — panel rotation, zero-overlap, convergence, degrade ladder, cap hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
