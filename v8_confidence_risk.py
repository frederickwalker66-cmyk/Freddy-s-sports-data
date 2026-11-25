"""Read-only probability-first research filter; never grants certification."""
import math

def screen(probability, decimal_odds, legs=1):
    if type(legs) is not int or not 1 <= legs <= 8:
        return {"decision": "HOLD", "reason": "invalid_leg_count"}
    if any(type(v) not in (int, float) or not math.isfinite(v)
           for v in (probability, decimal_odds)):
        return {"decision": "HOLD", "reason": "missing_or_invalid_probability_or_price"}
    if not 0 <= probability <= 1 or decimal_odds <= 1:
        return {"decision": "HOLD", "reason": "invalid_probability_or_price"}
    threshold = {1: .75, 2: .60, 3: .55}.get(legs, .50)
    ev = probability * decimal_odds - 1
    return {"decision": "HOLD" if probability >= threshold and ev >= .03 else "PASS",
            "research_threshold_met": probability >= threshold and ev >= .03,
            "probability": probability, "ev": ev, "minimum_probability": threshold,
            "reason": "research_only_requires_independent_certification"}

def confidence_report():
    return {"status": "HOLD", "certified_bets": 0,
            "champion_modified": False,
            "straight_first": True, "minimum_ev": .03,
            "minimum_probability_by_legs": {"1": .75, "2": .60, "3": .55,
                                             "4_to_8": .50},
            "parlay_probability_requires_joint_model": True,
            "native_probability_verified": False,
            "historical_backtest_verified": False,
            "version_comparison_verified": False,
            "reason": "no independently authenticated market-level evidence supplied"}
