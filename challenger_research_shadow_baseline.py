"""Untrained, fixed-rule $0 challenger research baseline; NEVER Champion-001.

Makes genuine prospective forecasts using only team win rates captured before
start. No market-derived model probabilities, calibration claims, or wagers.
A forecast is created only while the game is still in the future.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from challenger_prospective_outcome_validation import instant, validate_snapshot

VERSION = "research_fixed_form_v1_untrained"
BINARY_LEAGUES = {"nba", "mlb", "nfl", "nhl", "ncaaf", "ncaab"}


def _form(row, captured):
    if not isinstance(row, dict):
        return None
    count = row.get("last_games")
    rate = row.get("win_rate")
    ids = row.get("prior_espn_event_ids")
    if (type(count) is not int or not 3 <= count <= 5
            or type(rate) not in (int, float) or not math.isfinite(rate)
            or not 0 <= rate <= 1 or type(ids) is not list
            or len(ids) != count or len(set(ids)) != count
            or row.get("historical_original_publication_times_verified") is not False
            or type(row.get("result_start_embargo_hours")) is not int
            or row["result_start_embargo_hours"] < 48):
        return None
    try:
        asof = instant(row["retrieval_asof_utc"])
    except (KeyError, ValueError, TypeError):
        return None
    if asof > captured:
        return None
    return float(rate)


def build_forecasts(snapshots, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("clock requires timezone")
    now = now.astimezone(timezone.utc)
    if not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list")
    seen = set()
    produced = []
    skipped = Counter()
    for snap in snapshots:
        if not isinstance(snap, dict):
            skipped["invalid_snapshot"] += 1
            continue
        if snap.get("league") not in BINARY_LEAGUES:
            skipped["unsupported_market"] += 1
            continue
        try:
            key, captured = validate_snapshot(snap, now)
            start = instant(snap["event_start_utc"])
        except (ValueError, KeyError, TypeError, OverflowError):
            skipped["invalid_snapshot"] += 1
            continue
        if key in seen:
            raise ValueError("duplicate event in same pregame batch")
        seen.add(key)
        if not now < start:
            skipped["game_already_started"] += 1
            continue
        home_rate = _form(snap.get("home_team_form"), captured)
        away_rate = _form(snap.get("away_team_form"), captured)
        if home_rate is None or away_rate is None:
            skipped["incomplete_or_unverifiable_form"] += 1
            continue
        # A FIXED HEURISTIC, NOT A FITTED OR CALIBRATED MODEL.
        # No odds, sportsbook lines, or market-implied probabilities are read.
        p_home = round(0.5 + 0.3 * (home_rate - away_rate), 6)
        produced.append({
            "record_type": "prospective_untrained_research_baseline_forecast",
            "baseline_version": VERSION,
            "league": key[0],
            "espn_event_id": key[1],
            "snapshot_completed_at_utc": captured.isoformat(),
            "forecast_created_at_utc": now.isoformat(),
            "event_start_utc": start.isoformat(),
            "home_team": snap["home_team"],
            "away_team": snap["away_team"],
            "baseline_home_win_probability": p_home,
            "forecast_method": "fixed_0.5_plus_0.3_times_difference_in_previously_observed_5game_win_rate",
            "historical_source_publication_verified": False,
            "calibrated_model_probability": False,
            "trained_challenger_001_model": False,
            "certified_prediction": False,
            "training_eligible": False,
            "bet_ready": False,
            "shadow_stake_usd": 0,
            "champion_001_modified": False,
        })
    report = {
        "stage": "prospective_untrained_challenger_research_shadow_baseline",
        "generated_at_utc": now.isoformat(),
        "snapshots_seen": len(snapshots),
        "shadow_forecasts_created": len(produced),
        "by_league": dict(sorted(Counter(x["league"] for x in produced).items())),
        "skipped": dict(sorted(skipped.items())),
        "calibrated_predictions": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Untrained fixed heuristic; not Champion-001 or trained Challenger-001. "
                    "Research-only $0 forecasts are not bets or demonstrated edges. "
                    "No same-day or future result can be used at forecast time."),
    }
    return produced, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", required=True)
    p.add_argument("--output-dir", default="prospective_pregame")
    args = p.parse_args(argv)
    source = Path(args.snapshots)
    snapshots = [json.loads(x) for x in source.read_text().splitlines() if x.strip()]
    predictions, report = build_forecasts(snapshots)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "research_shadow_forecasts.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in predictions), encoding="utf8")
    (folder / "research_baseline_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
