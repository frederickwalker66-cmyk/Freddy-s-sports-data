"""Score $0 untrained research-baseline forecasts against later published ESPN finals.

Descriptive research only; this does not verify independent official settlement,
calibration, expected value, true model accuracy, or betting readiness.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from challenger_prospective_outcome_validation import instant
from challenger_research_shadow_baseline import VERSION, BINARY_LEAGUES


def read_rows(paths):
    rows = []
    for path in paths:
        rows.extend(json.loads(s) for s in Path(path).read_text().splitlines() if s.strip())
    return rows


def valid_forecast(row, now):
    if not isinstance(row, dict) or row.get("record_type") != "prospective_untrained_research_baseline_forecast":
        return None
    if (row.get("baseline_version") != VERSION or row.get("league") not in BINARY_LEAGUES
            or not str(row.get("espn_event_id", "")).isdigit()
            or row.get("certified_prediction") is not False
            or row.get("calibrated_model_probability") is not False
            or row.get("trained_challenger_001_model") is not False
            or row.get("bet_ready") is not False or row.get("champion_001_modified") is not False
            or row.get("shadow_stake_usd") != 0):
        return None
    p = row.get("baseline_home_win_probability")
    if type(p) not in (float, int) or not math.isfinite(p) or not 0.2 <= p <= 0.8:
        return None
    try:
        captured = instant(row["snapshot_completed_at_utc"])
        forecast = instant(row["forecast_created_at_utc"])
        start = instant(row["event_start_utc"])
    except (ValueError, TypeError, KeyError):
        return None
    if not captured <= forecast < start or forecast > now:
        return None
    return (row["league"], str(row["espn_event_id"])), forecast


def evaluate(forecasts, linked_games, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("evaluation time requires timezone")
    now = now.astimezone(timezone.utc)
    sources = {}
    rejected = Counter()
    for row in forecasts:
        valid = valid_forecast(row, now)
        if valid is None:
            rejected["invalid_or_nonprospective_forecast"] += 1
            continue
        key, when = valid
        if key not in sources or when < sources[key][0]:
            sources[key] = (when, row)
    results = defaultdict(list)
    for record in linked_games:
        if isinstance(record, dict) and record.get("league") in BINARY_LEAGUES:
            results[(record["league"], str(record.get("espn_event_id", "")))].append(record)
    by_league = defaultdict(list)
    pending = Counter()
    for key, (_, forecast) in sorted(sources.items()):
        game_rows = results.get(key, [])
        if len(game_rows) != 1:
            pending["missing_or_duplicate_outcome_record"] += 1
            continue
        game = game_rows[0]
        if game.get("status") != "linked_to_espn_published_final_only":
            pending["not_linked_to_published_final"] += 1
            continue
        final = game.get("published_outcome")
        if not isinstance(final, dict) or final.get("result") not in ("home", "away"):
            pending["tie_or_invalid_published_result"] += 1
            continue
        if (game.get("champion_001_modified") is not False
                or game.get("independent_league_outcome_verified") is not False
                or game.get("qualified_for_challenger_backtest") is not False
                or game.get("bet_ready") is not False):
            pending["result_failed_quarantine_check"] += 1
            continue
        try:
            start_match = instant(game["event_start_utc"]) == instant(forecast["event_start_utc"])
            same_teams = (game["home_team"] == forecast["home_team"]
                          and game["away_team"] == forecast["away_team"])
            final_seen = instant(final["published_retrieved_at_utc"])
        except (TypeError, KeyError, ValueError):
            pending["result_missing_provenance"] += 1
            continue
        if (not start_match or not same_teams
                or final_seen <= instant(forecast["event_start_utc"])
                or final_seen > now
                or instant(forecast["event_start_utc"]) >= now):
            pending["result_identity_or_timing_mismatch"] += 1
            continue
        y = 1 if final["result"] == "home" else 0
        p = forecast["baseline_home_win_probability"]
        by_league[key[0]].append((p, y))
    metrics = {}
    for league, scored in sorted(by_league.items()):
        n = len(scored)
        # A 50% probability expresses no directional pick; counting it as a
        # home pick artificially inflates or deflates reported accuracy.
        directional = [(p, y) for p, y in scored if p != 0.5]
        metrics[league] = {
            "research_forecasts_with_espn_published_results": n,
            "exploratory_brier_score": round(sum((p - y) ** 2 for p, y in scored) / n, 6),
            "constant_50pct_brier_score": 0.25,
            "exploratory_log_loss": round(-sum(y * math.log(p) + (1-y) * math.log(1-p)
                                               for p, y in scored) / n, 6),
            "directional_forecasts": len(directional),
            "neutral_50pct_forecasts": n - len(directional),
            "exploratory_pick_accuracy": (
                round(sum((p > 0.5) == bool(y) for p, y in directional)
                      / len(directional), 6) if directional else None),
            "constant_50pct_log_loss": round(math.log(2), 6),
            "out_of_sample_calibration_validated": False,
            "minimum_50_games_for_initial_descriptive_review_met": n >= 50,
            "independently_verified_outcomes": 0,
        }
    report = {
        "stage": "untrained_challenger_shadow_baseline_descriptive_scorecard",
        "forecast_rows_seen": len(forecasts),
        "unique_valid_forecasts": len(sources),
        "scored_espn_published_games": sum(len(v) for v in by_league.values()),
        "pending_or_excluded": dict(sorted(pending.items())),
        "rejected_forecasts": dict(sorted(rejected.items())),
        "by_league": metrics,
        "independent_league_outcomes_verified": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "validated_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Research metrics describe only an UNTRAINED fixed rule linked to ESPN "
                    "published finals. Not independent outcome adjudication, not a "
                    "model-trained cross-validation result, not ROI, and not a betting edge."),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast-root", required=True)
    parser.add_argument("--linked-results", required=True)
    parser.add_argument("--output-dir", default="prospective_validation")
    args = parser.parse_args(argv)
    forecasts = read_rows(sorted(Path(args.forecast_root).rglob("research_shadow_forecasts.jsonl")))
    results = read_rows([args.linked_results])
    report = evaluate(forecasts, results)
    path = Path(args.output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "research_shadow_scorecard.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
