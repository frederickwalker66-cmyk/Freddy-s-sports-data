"""Evidence-based NBA five-leg preflight; no synthetic odds, probabilities or bets.

The preflight reads the actual NBA V8 slate output and reports which evidence
is missing for each candidate market. Archived source-labeled prices cannot
become active checkout quotes, "sharp" professional handle, realized CLV,
or certified positive EV merely because a workflow completed successfully.
"""
from __future__ import annotations

from collections import Counter


def audit_five_leg_preflight(slate, calibration, *, legs=5):
    """Fail closed: require 5 distinct, independently certified exact markets.

    This function intentionally has no automatic promotion based on self-
    declared receipts or archived prices. An external review workflow would
    be required to validate source custody and native probabilities.
    """
    if not isinstance(slate, dict) or not isinstance(calibration, dict):
        raise ValueError("NBA_slate_and_calibration_objects_required")
    if type(legs) is not int or legs != 5:
        raise ValueError("five_leg_preflight_requires_exactly_five")
    if (slate.get("champion_001_modified") is not False
            or slate.get("independently_certified_positive_ev_bets") != 0):
        raise ValueError("unsafe_NBA_bet_promotion")
    games = slate.get("games")
    markets = slate.get("all_paired_archived_markets")
    if not isinstance(games, list) or not isinstance(markets, list):
        raise ValueError("missing_NBA_schedule_or_archived_markets")
    if len({g.get("espn_event_id") for g in games}) != len(games):
        raise ValueError("duplicate_NBA_event_identity")
    ids = {g.get("espn_event_id") for g in games}
    by_kind = Counter()
    quarantined = Counter()
    for row in markets:
        if not isinstance(row, dict) or row.get("espn_event_id_research_match") not in ids:
            raise ValueError("unmatched_NBA_market_identity")
        if (row.get("source_quote_not_executable") is not True
                or row.get("certified_sharp_edge_pp") is not None
                or row.get("certified_expected_roi_percent") is not None
                or row.get("independently_calibrated_model_probability_percent") is not None):
            raise ValueError("archived_market_illegally_promoted_to_verified_bet")
        kind = row.get("market")
        if not isinstance(kind, str):
            raise ValueError("invalid_NBA_market_type")
        category = "player_prop" if kind.startswith("player_") else kind
        by_kind[category] += 1
        if category == "player_prop":
            if row.get("player_team_assignment_verified") is not False:
                raise ValueError("unverified_NBA_prop_roster_promotion")
            quarantined["unverified_player_to_team"] += 1
        elif category not in ("moneyline", "point_spread", "total_points"):
            raise ValueError("unknown_NBA_market_category")
    # These counters describe archive coverage, never a count of bettable legs.
    return {
        "report_type": "NBA_EXACT_FIVE_LEG_PREFLIGHT_V1",
        "requested_legs": legs,
        "date_et": slate.get("date_et"),
        "slate_games": len(games),
        "archived_paired_reference_markets": len(markets),
        "archived_reference_market_categories": dict(sorted(by_kind.items())),
        "unverified_prop_market_pairs_quarantined": quarantined["unverified_player_to_team"],
        "rest_and_last5_last10_features_present_in_research": sum(
            isinstance(g.get("nba_rest_back_to_back_last5_last10"), dict) for g in games),
        "rest_and_form_features_have_validated_fitted_coefficients": False,
        "bookmaker_checkout_quote_receipts_verified": 0,
        "exact_market_native_model_probabilities_independently_certified": 0,
        "verified_entry_to_closing_line_pairs_for_clv": 0,
        "realized_clv_percent": None,
        "independently_validated_sharp_wager_handle": None,
        "certified_positive_ev_legs": [],
        "approved_five_leg_parlay": None,
        "five_leg_joint_win_probability": None,
        "five_leg_expected_value_percent": None,
        "calibration_status": calibration.get(
            "persisted_nba_original_forward_calibration_status", "UNAVAILABLE"),
        "graded_forward_home_win_research_outcomes": calibration.get(
            "nba_original_graded_outcomes"),
        "decision": "HOLD_ZERO_QUALIFIED_LEGS_NOT_A_BET",
        "blockers": [
            "current independently authenticated executable price for every exact leg",
            "player identity, roster, availability and prop settlement verification",
            "native independently calibrated probability per exact bet market",
            "original entry and same-line genuine closing price receipts for CLV",
            "joint dependence model for five correlated selections",
            "external approval and authenticated Champion-001 reference predictions",
        ],
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
        "champion_001_modified": False,
    }
