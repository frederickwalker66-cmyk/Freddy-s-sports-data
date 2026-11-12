"""V8 read-only betting-readiness evidence gate for PC and phone.

Reads real saved NBA pregame research calibration and existing archived
SharpAPI NBA/NFL markets. It never upgrades an aggregator quote, an analyst's
assertion or a GitHub green job into independent provenance, a model forecast,
a wager, or profitable expected value. The gate intentionally has no auto-
promotion path: independently signed model, quote and settlement evidence
requires a separate human release process.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from v8_forward_calibration_view import read_calibration
from v8_sharp_game_markets import summarize_full_game_markets
from v8_sharp_player_props import summarize_player_props

MARKETS = (
    "nba_moneyline", "nba_point_spread", "nba_total_points",
    "nba_player_props", "nfl_moneyline", "nfl_point_spread",
    "nfl_total_points", "nfl_player_props",
)
MIN_RESEARCH_GAMES = 50
MIN_EXPLORATORY_CALIBRATION_GAMES = 100


def _nonnegative_int(row, key):
    value = row.get(key)
    if type(value) is not int or value < 0:
        raise ValueError("untrusted_readiness_market_count_" + key)
    return value


def audit_betting_readiness(*, calibration_file=None, sharp_rows=None,
                            sharp_run_ids=(), now=None):
    """Create an inspectable blockers-by-market scorecard; NO bet certification."""
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("readiness_clock_must_be_timezone_aware")
    clock = clock.astimezone(timezone.utc)
    rows = [] if sharp_rows is None else sharp_rows
    if not isinstance(rows, list):
        raise ValueError("sharp_archives_must_be_list")
    if not isinstance(sharp_run_ids, (list, tuple)) or any(
            type(i) is not int or i <= 0 for i in sharp_run_ids):
        raise ValueError("invalid_saved_sharpapi_run_ids")
    calibration = read_calibration(calibration_file)
    game, _ = summarize_full_game_markets(
        rows, now=clock, archive_run_ids=sharp_run_ids)
    props, _ = summarize_player_props(
        rows, now=clock, archive_run_ids=sharp_run_ids)
    if (game["champion_001_modified"] is not False
            or props["champion_001_modified"] is not False
            or calibration["bet_ready"] is not False
            or calibration["certified_positive_ev_bets"] != 0
            or game["certified_positive_ev_bets"] != 0
            or props["certified_positive_ev_bets"] != 0):
        raise ValueError("upstream_model_or_price_report_claims_unsupported_certification")

    graded = calibration["graded_research_NBA_games"]
    originals = calibration["archived_original_forward_forecasts"]
    pending = calibration["pending_ungraded"]
    if graded is not None and (type(graded) is not int or graded < 0
                               or type(originals) is not int
                               or type(pending) is not int):
        raise ValueError("invalid_nba_forward_research_counts")

    game_count = _nonnegative_int(game, "today_recent_upcoming_full_games")
    prop_count = _nonnegative_int(props, "today_recent_two_sided_prop_markets")
    # This board deliberately contains at most 15 games and the prop report
    # at most 8 quotes per league. Counts in the market rows are only for
    # the VISIBLE reference board; they are never advertised as complete.
    game_board = game["today_game_market_board"]
    prop_board = props["today_player_prop_market_probability_board"]
    if not isinstance(game_board, list) or not isinstance(prop_board, dict):
        raise ValueError("invalid_archived_market_board")
    if any(not isinstance(item, dict) for item in game_board):
        raise ValueError("invalid_archived_game_snapshot")
    by_market = {}
    for market in MARKETS:
        league, kind = market.split("_", 1)
        if kind == "player_props":
            references = len(prop_board.get(league) or [])
        else:
            kind_lookup = {"moneyline": "moneyline", "point_spread": "point_spread",
                           "total_points": "total_points"}
            references = sum(
                item.get("league") == league
                and kind_lookup[kind] in item.get("paired_primary_markets", {})
                for item in game_board)
        # ONLY a distinct NBA home-win research model has saved, graded
        # probabilities; those are NOT frozen Champion forecasts or ATS,
        # totals, NFL or player-stat-specific calibration.
        research_graded = graded if market == "nba_moneyline" else None
        blockers = [
            "frozen_champion_executable_and_reference_predictions_not_externally_authenticated",
            "native_exact_market_pregame_probability_and_qualified_holdout_missing",
            "independent_sportsbook_event_line_price_and_checkout_receipt_missing",
            "exact_market_outcome_and_settlement_independently_unverified",
            "independent_release_review_not_approved",
        ]
        if kind == "player_props":
            blockers.append("player_identity_active_status_and_prop_stat_settlement_not_authenticated")
        if kind in ("point_spread", "total_points"):
            blockers.append("exact_handicap_or_total_line_and_push_semantics_not_model_verified")
        by_market[market] = {
            "status": "HOLD_NO_INDEPENDENTLY_VERIFIED_POSITIVE_EV",
            "research_forward_grades_nba_home_win_only": research_graded,
            "recent_aggregator_two_sided_examples_displayed": references,
            "aggregator_examples_are_executable_checkout_prices": False,
            "native_probability_validated_for_exact_market": False,
            "true_entry_to_closing_line_value_pairs_verified": 0,
            "market_specific_ev_certified": 0,
            "bet_ready": False,
            "blockers": blockers,
        }
    research = {
        "scope": "NBA_v8_Elo_home_win_research_not_Champion_001",
        "source": "durable_original_forward_calibration_if_present",
        "source_status": calibration["status"],
        "original_forecasts_saved": originals,
        "published_outcomes_graded": graded,
        "awaiting_grade": pending,
        "minimum_first_research_metrics": MIN_RESEARCH_GAMES,
        "minimum_exploratory_calibration": MIN_EXPLORATORY_CALIBRATION_GAMES,
        "additional_graded_needed_for_first_metrics": (
            max(0, MIN_RESEARCH_GAMES - graded) if graded is not None else None),
        "additional_graded_needed_for_exploratory_calibration": (
            max(0, MIN_EXPLORATORY_CALIBRATION_GAMES - graded)
            if graded is not None else None),
        "first_metrics_qualified": bool(graded is not None and graded >= MIN_RESEARCH_GAMES),
        "research_calibration_independently_certified": False,
    }
    return {
        "report_type": "v8_betting_readiness_exact_market_evidence_gate_v1",
        "checked_at_utc": clock.isoformat(),
        "decision": "PASS_HOLD_NO_CERTIFIED_BETS",
        "bet_ready": False,
        "certified_positive_ev_bets": 0,
        "independently_verified_checkout_prices": 0,
        "matched_original_entry_and_authenticated_closing_price_receipts": 0,
        "independently_approved_original_champion_001_model": False,
        "automatic_wagers": 0,
        "stake_usd": 0,
        "champion_001_modified": False,
        "research_forward": research,
        "archive_price_context": {
            "saved_sharpapi_runs": list(sorted(set(sharp_run_ids))),
            "archived_quote_rows_read": len(rows),
            "recent_upcoming_nba_nfl_full_game_reference_events": game_count,
            "recent_upcoming_two_sided_player_prop_reference_markets": prop_count,
            "bookmaker_reference": "SharpAPI_DraftKings_labeled_aggregator_not_checkout",
            "fresh_reference_examples_do_not_prove_execution_or_positive_EV": True,
        },
        "by_market": by_market,
        "critical_next_steps": [
            "Retrieve independently attested original Champion-001 executable, source, version and reproducible reference predictions.",
            "Keep capturing BEFORE-game native probability forecasts and later independently adjudicated outcomes for each exact market, including spreads and props.",
            "Finish 50 mature research grades for descriptive metrics, then 100+ with sufficiently populated calibration bins. These counts alone never certify profit.",
            "Independently verify sportsbook checkout timestamp, event identity, exact line, price, player identity and market settlement rules.",
            "Preserve authenticated original entry and same-outcome closing receipts to measure CLV; recorded repricing is not CLV.",
            "Independent release review must approve reproducible calibration, probability/price alignment and out-of-sample EV before any live pick can qualify.",
        ],
        "limitations": "Software readiness is not model skill, profitability, a verified bookmaker quote or a real-money approval. No bets were placed.",
    }


def save_readiness(report, path):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        raise ValueError("unsafe_readiness_report_destination")
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
