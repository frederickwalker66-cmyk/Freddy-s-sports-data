"""#80-82: deterministic final release gate for all-eight-sport research pipeline.

This gate never trains, replaces, signs, deploys, or bets a model. It produces
an evidence inventory with explicit external blockers, refusing false zero-to-
ready promotions. SHA files attest local bytes only, not publisher authorship.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from champion_001_authentication import inspect as inspect_champion
from independent_schedule_review import SOURCES

LEAGUES = tuple(SOURCES)
REQUIRED_ZERO_MARKET = (
    "direct_draftkings_checkout_quotes_verified",
    "exact_direct_bookmaker_market_ids_verified",
    "independently_verified_native_probabilities",
    "qualified_chronological_training_games",
    "certified_champion_001_predictions",
    "certified_challenger_001_predictions",
    "certified_positive_ev_bets",
    "bet_ready_selections",
    "automated_wagers",
)
REQUIRED_ZERO_INDEPENDENT = (
    "direct_draftkings_checkout_markets_verified",
    "verified_native_model_probabilities",
    "qualified_chronological_training_games",
    "certified_champion_001_predictions",
    "certified_challenger_001_predictions",
    "certified_positive_ev_bets",
    "bet_ready_selections",
    "automated_bets_placed",
)


def evaluate(schedule, identity, markets, champion=None):
    if not all(isinstance(x, dict) for x in (schedule, identity, markets)):
        raise ValueError("invalid_completion_gate_inputs")
    if (schedule.get("stage") !=
            "challenger_eight_sport_seven_day_schedule_coverage_research_only"
            or identity.get("stage") !=
            "challenger_78_independent_league_identity_research_only"
            or markets.get("stage") !=
            "challenger_79_exact_aggregator_market_research_quarantine"):
        raise ValueError("incompatible_stage_or_wrong_run")
    if (set(schedule.get("by_league", {})) != set(LEAGUES)
            or set(markets.get("by_league", {})) != set(LEAGUES)):
        raise ValueError("missing_eight_sport_coverage")
    count = schedule.get("totals", {}).get("pregame_events_archived")
    if (type(count) is not int or count < 0
            or identity.get("archived_espn_events_reviewed") != count
            or markets.get("archived_pregame_events") != count):
        raise ValueError("source_game_counts_differ_between_gates")
    if (schedule.get("archived_games_matching_exact_original_event_fields") != count
            or schedule.get("original_source_hashes_independently_publisher_signed") is not False
            or schedule.get("independent_league_schedule_verified") is not False
            or schedule.get("historical_feature_publication_authenticated") is not False):
        raise ValueError("source_integrity_or_publisher_attestation_invalid")
    if (identity.get("champion_001_modified") is not False
            or markets.get("champion_001_modified") is not False
            or schedule.get("champion_001_modified") is not False):
        raise ValueError("frozen_champion_changed")
    for key in REQUIRED_ZERO_INDEPENDENT:
        if identity.get(key) != 0:
            raise ValueError("independent_identity_promoted_to_prediction")
    for key in REQUIRED_ZERO_MARKET:
        if markets.get(key) != 0:
            raise ValueError("research_market_promoted_to_prediction")
    for key in (
        "qualified_chronological_training_games", "certified_champion_001_predictions",
        "certified_challenger_001_predictions", "certified_positive_ev_bets",
        "bet_ready_selections", "automated_bets_placed",
    ):
        if schedule.get(key) != 0:
            raise ValueError("schedule_source_promoted_to_training_or_bet")
    games = sum(x.get("archived_pregame_games", -1)
                for x in schedule["by_league"].values())
    if games != count:
        raise ValueError("league_archive_counts_do_not_sum")
    matched_by_league = {
        lg: markets["by_league"][lg].get(
            "league_identity_matched_research_only", 0)
        for lg in LEAGUES
    }
    if any(type(v) is not int or v < 0 or
           v > schedule["by_league"][lg]["archived_pregame_games"]
           for lg, v in matched_by_league.items()):
        raise ValueError("per_league_identity_count_invalid")
    if (matched_by_league["nba"] != identity.get(
            "independently_observed_nba_pregame_identity_matches_research_only")
            or matched_by_league["mlb"] != identity.get(
                "independently_observed_mlb_pregame_identity_matches_research_only")
            or matched_by_league["nhl"] != identity.get(
                "independently_observed_nhl_pregame_identity_matches_research_only")):
        raise ValueError("independent_and_market_identity_counts_disagree")
    quote_count = markets.get("provider_quote_rows_reviewed")
    if (type(quote_count) is not int or quote_count < 0
            or quote_count != sum(
                r.get("research_aggregator_quote_rows_reviewed", 0)
                for r in markets["by_league"].values())):
        raise ValueError("market_quote_count_mismatch")
    champion = inspect_champion() if champion is None else champion
    if (not isinstance(champion, dict)
            or champion.get("champion_001_modified") is not False
            or champion.get("certified_champion_001_predictions") != 0
            or champion.get("original_executable_verified") is not False
            or champion.get("immutable_model_version_authenticated") is not False
            or champion.get("reproducible_reference_outputs_verified") is not False):
        raise ValueError("unsafe_or_unattested_champion_001")
    blockers = [
        "original_champion_001_binary_independent_custody_and_reproducible_output_missing",
        "point_in_time_training_features_not_independently_authenticated",
        "per_league_chronological_200_training_50_holdout_evidence_unverified",
        "native_pregame_model_probabilities_and_calibration_not_independently_verified",
        "direct_draftkings_event_market_selection_line_price_receipt_missing",
        "player_props_require_separate_roster_injury_active_and_player_model",
        "soccer_requires_independent_90_minute_three_way_settlement_review",
        "closing_line_value_requires_verified_entry_and_closing_quotes",
        "production_promotion_requires_reproducible_signed_artifacts_and_repository_protection",
    ]
    return {
        "stage": "challenger_82_full_sequence_release_readiness",
        "research_source_and_identity_audit_complete": True,
        "software_reconciliation_status": "passed_same_run_research_reconciliation",
        "model_update_status": "BLOCKED_MISSING_INDEPENDENT_EXTERNAL_EVIDENCE",
        "release_decision": "HOLD_NO_DEPLOYMENT_NO_CERTIFIED_PICKS",
        "league_count": len(LEAGUES),
        "archived_pregame_games": count,
        "third_party_schedule_original_responses_verified_in_same_run":
            schedule.get("original_espn_source_responses_verified", 0),
        "league_operated_identity_matches_research_only": matched_by_league,
        "research_aggregator_quote_rows_reviewed": quote_count,
        "research_exact_market_fields_reconciled":
            markets.get("research_market_fields_reconciled", 0),
        "model_training_completed": False,
        "native_models_certified": 0,
        "newly_authenticated_champion_artifacts": 0,
        "independently_verified_bookmaker_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "qualified_chronological_training_games": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "blockers": blockers,
        "next_external_requirements": [
            "Recover owner-held frozen Champion-001 executable plus independent signature and reference outputs.",
            "Provide genuine as-of historical features and independently adjudicated outcomes per league.",
            "Train and evaluate native per-league models on disjoint chronological holdouts.",
            "Capture direct sportsbook market/price evidence and check player status where relevant.",
            "Review OOS calibration, bankroll controls, release sign-off and durable signed archives.",
        ],
        "warning": "Engineering tests, ESPN/league corroboration, SHA receipts and aggregator quote metadata do not establish independently verified forecast probabilities or executable betting value.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schedule-report", required=True)
    p.add_argument("--independent-report", required=True)
    p.add_argument("--market-report", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    items = [json.loads(Path(f).read_text()) for f in (
        args.schedule_report, args.independent_report, args.market_report)]
    result = evaluate(*items)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": result["model_update_status"],
                      "archived_pregame_games": result["archived_pregame_games"],
                      "bookmaker_prices_verified": result["independently_verified_bookmaker_prices"],
                      "champion_001_modified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
