"""Archived NBA Elo retrospective benchmark from genuine ESPN-published results.

Replays completed regular-season games in event-time order with the existing
48-hour assumed outcome embargo. This is a *retrospective simulation*, NOT
predictions actually recorded before tipoff, independently published original
pregame evidence, calibrated model, sportsbook EV or a certified prediction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import json
import math

from challenger_multiseason_history import _check_record
from challenger_elo_walkforward import (
    validate_game, embargoed_forecasts, evaluate as elo_evaluate,
    SETTLEMENT_LAG_HOURS, MIN_GAMES, MIN_EVAL, K, HOME_ADV,
)
from historical_outcomes import parse_time
from v8_nba_paired_baseline import compare as compare_to_rolling_home_prior


def benchmark(rows, coverage, now=None):
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if not isinstance(rows, list) or not isinstance(coverage, dict):
        raise ValueError("results_and_coverage_required")
    if (coverage.get("stage") != "challenger_historical_backfill_research_only"
            or coverage.get("league") != "nba"
            or coverage.get("champion_001_modified") is not False
            or coverage.get("independent_result_adjudication_verified") is not False
            or coverage.get("historical_pregame_feature_timestamps_verified") is not False
            or coverage.get("bookmaker_market_settlement_verified") is not False
            or coverage.get("qualified_training_examples") != 0
            or coverage.get("officially_adjudicated_results") != 0
            or coverage.get("published_completed_game_results") != len(rows)):
        raise ValueError("unsupported_or_promoted_historical_NBA_coverage")
    days, okay, failed = (
        coverage.get("days_requested"), coverage.get("scoreboard_days_successful"),
        coverage.get("scoreboard_days_failed"))
    if (type(days) is not int or not 1 <= days <= 35
            or any(type(x) is not int or x < 0 for x in (okay, failed))
            or okay + failed != days):
        raise ValueError("unreconciled_NBA_source_day_counts")
    games = []
    ids = set()
    for row in rows:
        if row.get("league") != "nba":
            raise ValueError("non_NBA_result_contamination")
        # The original archived window must identify the exact ESPN URL and
        # game day, not merely a plausible home/away final score.
        _check_record(row, "nba", coverage)
        lg, start, eid, home, away, result = validate_game(row)
        retrieved = parse_time(row.get("retrieved_at_utc"))
        if not (start < retrieved <= clock) or result is None:
            raise ValueError("unobservable_or_unsettled_original_NBA_score")
        if eid in ids:
            raise ValueError("duplicate_NBA_event_id_quarantined")
        ids.add(eid)
        games.append((start, eid, home, away, result))
    games.sort(key=lambda x: (x[0], x[1]))
    replay, ties = embargoed_forecasts(games, lag_hours=SETTLEMENT_LAG_HOURS)
    if ties or len(replay) != len(games):
        raise ValueError("inconsistent_NBA_replay")
    baseline_comparison, paired_rows = compare_to_rolling_home_prior(
        games, replay, warmup=MIN_GAMES, minimum=MIN_EVAL)
    ledger = []
    for (start, eid, home, away, y), (p, y2, simulated), paired in zip(games, replay, paired_rows):
        if y != y2 or simulated != start.isoformat() or not 0 < p < 1:
            raise ValueError("Elo_replay_event_alignment_failure")
        ledger.append({
            "record_type": "v8_retrospective_NBA_Elo_event_replay_only",
            "league": "nba", "espn_event_id": eid,
            "event_start_utc": start.isoformat(),
            "home_team_espn_id": home, "away_team_espn_id": away,
            "retrospective_simulated_home_win_probability": round(p, 9),
            "retrospective_rolling_home_baseline_probability": paired["home_win_prior_reconstructed_after_game"],
            "elo_vs_rolling_baseline_brier_improvement_retro_only": round(paired["paired_brier_improvement"], 9),
            "published_score_home_won_research_label": y,
            "historical_forecast_actually_recorded_before_tipoff": False,
            "probability_source": "fixed_Elo_K20_HA60_embargo48h_reconstructed_after_game",
            "result_publication_timestamp_independently_verified": False,
            "qualified_as_true_pregame_shadow": False,
            "qualified_for_model_training": False,
            "certified_prediction": False, "bet_ready": False,
            "champion_001_modified": False,
        })
    baseline = elo_evaluate(rows, min_games=MIN_GAMES, min_eval=MIN_EVAL)
    result = baseline["by_league"]["nba"]
    enough = result["status"] == "provisional_walkforward_diagnostic"
    if result["historical_games"] != len(games):
        raise ValueError("Elo_diagnostic_history_disagrees_with_replay")
    early_games = min(MIN_GAMES, len(games))
    later_games = max(0, len(games) - early_games)
    data = {
        "report_version": "v8-nba-retrospective-elo-benchmark-v1",
        "status": ("RETROSPECTIVE_DIAGNOSTIC_AVAILABLE_UNVERIFIED"
                   if enough else "HOLD_INSUFFICIENT_RESEARCH_HISTORY"),
        "source": "ESPN_original_published_completed_regular_season_scoreboard",
        "source_window_start_et": coverage.get("window_start_et"),
        "source_window_end_et": coverage.get("window_end_et"),
        "source_days_requested": days,
        "source_days_successfully_returned": okay,
        "source_days_failed": failed,
        "whole_requested_window_fetched": failed == 0,
        "published_completed_games": len(games),
        "warmup_games": early_games,
        "retrospective_evaluation_games": later_games,
        "minimum_required_evaluation_games": MIN_EVAL,
        "brier_score_retrospective_research_only": (
            result["diagnostic_brier"] if enough else None),
        "log_loss_retrospective_research_only": (
            result["diagnostic_logloss"] if enough else None),
        "neutral_50_50_brier_comparison_not_bookmaker": (
            result["neutral_50_50_brier"] if enough else None),
        "calibration_bins_exploratory_only": result["calibration_bins"] if enough else [],
        "paired_rolling_home_baseline_comparison": baseline_comparison,
        "model_parameters_fixed_before_retrospective_replay": {
            "K": K, "home_advantage_elo_points": HOME_ADV,
            "assumed_previous_result_embargo_hours": SETTLEMENT_LAG_HOURS},
        "original_actual_pregame_model_forecast_receipts": 0,
        "independently_authenticated_original_training_examples": 0,
        "original_result_publication_times_independently_authenticated": False,
        "independently_calibrated_probability_model": False,
        "verified_executable_draftkings_price_quotes": 0,
        "champion_001_production_model_modified": False,
        "certified_champion_001_predictions": 0,
        "certified_v8_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "bet_ready": False,
        "warning": (
            "The source is historical ESPN-published scores captured AFTER games. "
            "The Elo replay reconstructs what a fixed rule could have forecast "
            "with a presumed 48h result embargo; forecasts were NOT actually "
            "recorded pregame. Brier/log loss are exploratory, not independently "
            "certified out-of-sample skill; the 50/50 comparison is not a market "
            "baseline. Rolling home-win-rate comparison and paired day bootstrap "
            "are retrospective only, not independently validated skill. "
            "No historical betting ROI, qualified shadows, bets or "
            "actionable positive EV can be inferred."),
    }
    return data, ledger


def read_jsonl(path):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.stat().st_size > 20_000_000:
        raise ValueError("oversized_NBA_history")
    return [json.loads(s) for s in source.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def save(report, ledger, output_dir):
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "NBA_ELO_RETROSPECTIVE_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (path / "NBA_ELO_RETROSPECTIVE_LEDGER.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in ledger),
        encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--published-games", required=True)
    p.add_argument("--coverage", required=True)
    p.add_argument("--output-dir", default="v8_results/nba_elo_research")
    args = p.parse_args(argv)
    cov = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    result, ledger = benchmark(read_jsonl(args.published_games), cov)
    save(result, ledger, args.output_dir)
    print(json.dumps({
        "status": result["status"], "games": result["published_completed_games"],
        "retrospective_evaluation_games": result["retrospective_evaluation_games"],
        "research_brier": result["brier_score_retrospective_research_only"],
        "certified_predictions": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
