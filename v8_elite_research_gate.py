"""Freddy's Picks AI V8: research-only price mathematics and release gates.

This module does NOT train a model, authenticate a provider, output certified
picks, touch frozen Champion-001, or place bets. All inputs are hypothetical
or unauthenticated unless an independent process proves otherwise.
"""
from __future__ import annotations

import math
from typing import Any

VERSION = "v8-elite-research-gate-v0"
SUPPORTED = frozenset({"nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league"})
MIN_TRAIN = 200
MIN_HOLDOUT = 50


def decimal_odds(american: int) -> float:
    """Convert strict integer American odds to gross decimal payout."""
    if type(american) is not int or -100 < american < 100:
        raise ValueError("American odds must be an integer <= -100 or >= +100")
    return 1 + (american / 100 if american > 0 else 100 / abs(american))


def breakeven_probability(american: int) -> float:
    return 1 / decimal_odds(american)


def expected_roi(probability: float, american: int) -> float:
    """Net expected return per unit stake, NOT a betting recommendation."""
    if type(probability) not in (int, float) or not math.isfinite(probability):
        raise ValueError("probability must be finite")
    if not 0 <= probability <= 1:
        raise ValueError("probability outside [0,1]")
    return float(probability) * decimal_odds(american) - 1


def release_gate(evidence: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: review supplied evidence without trusting its self-attestation.

    Even if flags pass, records are not automatically independently authenticated
    and this module never turns them into certified picks.
    """
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dictionary")
    league = evidence.get("league")
    blockers = []
    if league not in SUPPORTED:
        blockers.append("unsupported_league")
    if evidence.get("champion_001_modified") is not False:
        blockers.append("champion_must_remain_frozen")
    if evidence.get("independent_source_authentication") is not True:
        blockers.append("independent_source_authentication_missing")
    if evidence.get("original_pregame_asof_authenticated") is not True:
        blockers.append("pregame_asof_proof_missing")
    if evidence.get("independent_result_adjudication") is not True:
        blockers.append("independent_result_adjudication_missing")
    if evidence.get("verified_market_settlement_rules") is not True:
        blockers.append("market_settlement_rules_unverified")
    if evidence.get("untouched_chronological_holdout") is not True:
        blockers.append("chronological_holdout_missing")
    for key, threshold in (("qualified_training_games", MIN_TRAIN),
                           ("qualified_holdout_games", MIN_HOLDOUT)):
        number = evidence.get(key)
        if type(number) is not int or number < threshold:
            blockers.append(key + "_insufficient")
    if evidence.get("calibrated_out_of_sample") is not True:
        blockers.append("out_of_sample_calibration_missing")
    if evidence.get("independently_verified_executable_odds") is not True:
        blockers.append("executable_odds_unverified")
    if evidence.get("reproduced_model_artifact") is not True:
        blockers.append("model_artifact_unverified")
    return {
        "version": VERSION,
        "league": league,
        "release_review_complete": not blockers,
        "certified_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
        "reason": "independent_external_signoff_required_even_if_flags_pass",
        "blockers": blockers,
    }


def research_price_comparison(probability: float, american: int) -> dict[str, float]:
    """Pure math; explicitly unqualified as a model-based pick."""
    return {
        "market_breakeven_probability": breakeven_probability(american),
        "hypothetical_probability": float(probability),
        "hypothetical_expected_roi": expected_roi(probability, american),
        "certified_prediction": False,
    }
