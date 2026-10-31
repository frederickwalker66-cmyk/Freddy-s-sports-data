"""Challenger-only research preflight for slips and multi-leg risk.

This module does not infer true probabilities, certify external forecasts, fetch
injuries/odds, place wagers, or modify Champion-001. Missing evidence fails closed.
"""
from collections import Counter
from math import isfinite


VALID_RESULTS = {"win", "loss", "push", "void", "pending"}


def break_even_probability(american_odds):
    """Price-implied break-even probability, not a model forecast."""
    if type(american_odds) is not int or -100 < american_odds < 100:
        raise ValueError("valid nonzero American odds of +/-100 or greater required")
    if american_odds > 0:
        return 100.0 / (american_odds + 100)
    return -american_odds / (100.0 - american_odds)


def net_win_per_unit(american_odds):
    break_even_probability(american_odds)
    return american_odds / 100.0 if american_odds > 0 else 100.0 / -american_odds


def audit_slip(legs, quoted_parlay_odds=None, joint_probability=None,
               joint_probability_verified=False, parlay_quote_verified=False):
    """Analyze a research slip; never label it as a certified prediction.

    Each leg needs a stable event_id, market_type, selection, American odds,
    and explicit evidence booleans:
      - dk_quote_verified: exact sportsbook checkout/quote independently checked
      - availability_verified: current injury/active check (player props only)
      - model_probability_verified: independent pregame model output verified
      - model_probability: optional scalar from that verified output
    None of these flags is inferred by the function.
    A quoted parlay price is required; multiplying leg odds is invalid for SGPs.
    A separately validated joint probability is required for combined EV.
    """
    if not isinstance(legs, list) or not legs:
        raise ValueError("legs must be a nonempty list")
    if joint_probability is not None:
        if (isinstance(joint_probability, bool) or
                not isinstance(joint_probability, (int, float)) or
                not isfinite(joint_probability) or
                not 0 <= joint_probability <= 1):
            raise ValueError("joint probability must be finite and in [0,1]")
    rows = []
    event_counts = Counter()
    for i, leg in enumerate(legs):
        if not isinstance(leg, dict):
            raise ValueError("every leg must be a mapping")
        odds = leg.get("odds_american")
        implied = break_even_probability(odds)
        event = leg.get("event_id")
        reasons = []
        if not isinstance(event, str) or not event.strip():
            reasons.append("event_identity_missing")
        else:
            event_counts[event] += 1
        if not isinstance(leg.get("market_type"), str) or not leg["market_type"].strip():
            reasons.append("market_identity_missing")
        if not isinstance(leg.get("selection"), str) or not leg["selection"].strip():
            reasons.append("selection_missing")
        if leg.get("dk_quote_verified") is not True:
            reasons.append("direct_draftkings_quote_unverified")
        is_prop = bool(leg.get("is_player_prop"))
        if is_prop and leg.get("availability_verified") is not True:
            reasons.append("player_availability_or_role_unverified")
        p = leg.get("model_probability")
        ev = None
        if p is None:
            reasons.append("independent_model_probability_missing")
        elif (isinstance(p, bool) or not isinstance(p, (int, float))
              or not isfinite(p) or not 0 <= p <= 1):
            raise ValueError("individual model probability invalid")
        elif leg.get("model_probability_verified") is not True:
            reasons.append("independent_model_probability_unverified")
        else:
            ev = round(float(p) * net_win_per_unit(odds) - (1-float(p)), 6)
        rows.append({
            "leg_number": i+1, "event_id": event,
            "selection": leg.get("selection"),
            "break_even_probability": round(implied, 6),
            "model_ev_per_unit_if_verified": ev,
            "reasons": reasons,
        })
    shared_events = sorted(k for k, v in event_counts.items() if v > 1)
    blockers = []
    if shared_events:
        blockers.append("shared_event_exposure_requires_joint_model")
    if quoted_parlay_odds is None:
        blockers.append("exact_parlay_price_missing")
        combined_break_even = None
    else:
        combined_break_even = round(break_even_probability(quoted_parlay_odds), 6)
        if parlay_quote_verified is not True:
            blockers.append("parlay_checkout_quote_unverified")
    if joint_probability is None or joint_probability_verified is not True:
        blockers.append("validated_joint_probability_missing")
        combined_ev = None
    elif quoted_parlay_odds is None or parlay_quote_verified is not True:
        combined_ev = None
    else:
        combined_ev = round(float(joint_probability) *
                            net_win_per_unit(quoted_parlay_odds) -
                            (1 - float(joint_probability)), 6)
    blockers.extend(reason for row in rows for reason in row["reasons"])
    blockers = sorted(set(blockers))
    return {
        "stage": "challenger_research_only_preflight",
        "champion_001_modified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "wagers_placed": 0,
        "bet_ready": False,
        "decision": "PASS" if blockers or combined_ev is None or combined_ev <= 0 else "RESEARCH_REVIEW_ONLY",
        "legs": rows,
        "same_event_ids": shared_events,
        "combined_quote_break_even_probability": combined_break_even,
        "combined_model_ev_per_unit_if_verified": combined_ev,
        "blockers": blockers,
        "note": "No independence assumption, automatic SGP payout calculation, or wager authorization.",
    }


def grade_slip_results(results):
    """Outcome audit only; sportsbook void/push and final payout need separate verification."""
    if not isinstance(results, list) or not results:
        raise ValueError("results must be a nonempty list")
    if any(x not in VALID_RESULTS for x in results):
        raise ValueError("unsupported or missing leg settlement")
    counts = Counter(results)
    if counts["loss"]:
        state = "loss"
    elif counts["pending"]:
        state = "pending"
    else:
        state = "requires_bookmaker_payout_confirmation"
    settled = counts["win"] + counts["loss"]
    return {
        "leg_counts": {k: counts[k] for k in sorted(VALID_RESULTS)},
        "settled_leg_hit_rate": counts["win"] / settled if settled else None,
        "preliminary_ticket_state": state,
        "final_payout_verified": False,
        "champion_001_modified": False,
        "note": "A void is not a loss; this descriptive hit rate is not model accuracy.",
    }
