"""Eight-league bounded historical game-result backfill for research only.

Reads ESPN-published final scores for one <=35-day historical window per league.
Soccer goals/draws require independently established 90-minute vs extra-time
rules; binary moneyline research MUST NOT absorb MLS or UCL three-way results.
No SportsGameOdds, no sportsbook API, no training or wagering. Never claim
an older season is covered until source requests and game identity pass.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import LEAGUES, collect
from challenger_research_features import build_candidates
from challenger_elo_walkforward import evaluate

# Representative historical in-season windows. Not complete seasons.
# 35-day requests deliberately avoid unlimited backfills and rate-limit storms.
# Use --end-date (or GitHub Actions input) to choose earlier windows, including
# older seasons, only where published source coverage can be verified.
WINDOW_END = {
    "nba": date(2026, 2, 15),
    "nhl": date(2026, 2, 15),
    "mlb": date(2026, 8, 15),
    "nfl": date(2025, 11, 10),
    "ncaaf": date(2025, 11, 10),
    "ncaab": date(2026, 2, 15),
    "mls": date(2026, 8, 15),
    "uefa_champions_league": date(2026, 3, 18),
}
MAX_DAYS = 35


def plan(league, days=MAX_DAYS, end_date=None, now=None):
    league = league.lower()
    if league not in WINDOW_END or league not in LEAGUES:
        raise ValueError("only the eight configured competition feeds are supported")
    if type(days) is not int or not 1 <= days <= MAX_DAYS:
        raise ValueError("request budget: 1-35 days per league")
    end = end_date or WINDOW_END[league]
    if not isinstance(end, date) or isinstance(end, datetime):
        raise ValueError("end date must be a calendar date")
    today = (now or datetime.now(timezone.utc)).astimezone(
        ZoneInfo("America/New_York")).date()
    if end >= today:
        raise ValueError("backfill ends only on dates before today")
    if end - timedelta(days=days - 1) < date(1950, 1, 1):
        raise ValueError("historical collection windows may not begin before 1950")
    return {"league": league, "start_et": (end - timedelta(days=days - 1)).isoformat(),
            "end_et": end.isoformat(), "days": days,
            "maximum_public_scoreboard_requests": days,
            "sportsbook_api_requests": 0,
            "results_only": True,
            "soccer_three_way_regulation_verified": False,
            "sportsgameodds_requests": 0}


def build_report(league, days, end_date, rows, collection, candidates, research):
    if league != collection["leagues"][0] or len(collection["leagues"]) != 1:
        raise ValueError("one-league collection expected")
    if collection["total_completed_results"] != len(rows):
        raise ValueError("collected results count mismatch")
    if research["research_candidates"] != len(candidates):
        raise ValueError("candidate count mismatch")
    details = collection["by_league"][league]
    if details["days_attempted"] != days or details["days_ok"] + details["days_failed"] != days:
        raise ValueError("unaccounted scoreboard days")
    if details["completed_games"] != len(rows):
        raise ValueError("inconsistent game count")
    if any(x["qualified_for_challenger_backtest"] is not False
           or x["bet_ready"] is not False for x in candidates):
        raise ValueError("unverified feature was incorrectly promoted")
    # Soccer published score results do not independently establish the 90-min
    # three-way settlement result, particularly for UCL knockout extra time.
    if league in ("mls", "uefa_champions_league") and candidates:
        raise ValueError("soccer published results cannot become binary moneyline candidates")
    draws = sum(x["result"] == "draw" for x in rows)
    if league in ("mls", "uefa_champions_league"):
        outcome_class = "published_soccer_score_three_way_unverified_90min"
    else:
        outcome_class = "published_score_binary_moneyline_unverified_settlement"
    return {
        "stage": "challenger_historical_backfill_research_only",
        "league": league, "days_requested": days,
        "window_start_et": (end_date - timedelta(days=days - 1)).isoformat(),
        "window_end_et": end_date.isoformat(),
        "public_scoreboard_requests_maximum": days,
        "sportsbook_api_requests": 0,
        "scoreboard_days_successful": details["days_ok"],
        "scoreboard_days_failed": details["days_failed"],
        "coverage_complete": details["days_failed"] == 0,
        "published_completed_game_results": len(rows),
        "published_score_home_results": sum(x["result"] == "home" for x in rows),
        "published_score_away_results": sum(x["result"] == "away" for x in rows),
        "published_score_draw_results": draws,
        "result_scope": outcome_class,
        "soccer_90_minute_result_verified": False,
        "bookmaker_market_settlement_verified": False,
        "independently_confirmed_historical_period_coverage": False,
        "quarantined_research_candidates": len(candidates),
        "qualified_training_examples": 0,
        "officially_adjudicated_results": 0,
        "sportsgameodds_requests": 0,
        "independent_result_adjudication_verified": False,
        "historical_pregame_feature_timestamps_verified": False,
        "historical_odds_snapshots_verified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "These are ESPN-published historical score observations, not official adjudication, historical pregame features, player props, NBA/NHL overtime settlement, or soccer 90-minute markets. Missing source days and older seasons remain incomplete. Nothing is training-ready or bet-ready.",
    }


def run(league, days=MAX_DAYS, end_date=None, output_dir="challenger_backfill",
        collector=collect, clock=None):
    p = plan(league, days, end_date, now=clock)
    league = p["league"]
    end = date.fromisoformat(p["end_et"])
    rows, coverage = collector((league,), days, end)
    candidates, research = build_candidates(rows)
    report = build_report(league, days, end, rows, coverage, candidates, research)
    diagnostic = evaluate(rows)
    if (diagnostic["bet_ready_selections"] != 0
            or diagnostic["certified_champion_001_predictions"] != 0
            or diagnostic["champion_001_modified"] is not False):
        raise ValueError("unsafe diagnostic state")

    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("published_results.jsonl", rows),
        ("research_candidates.jsonl", candidates),
    ):
        (dest / name).write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in payload),
            encoding="utf-8")
    for name, payload in (
        ("backfill_coverage.json", report),
        ("scoreboard_collection.json", coverage),
        ("candidate_coverage.json", research),
        ("walkforward_diagnostic.json", diagnostic),
    ):
        (dest / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True, choices=sorted(WINDOW_END))
    parser.add_argument("--days", type=int, default=MAX_DAYS)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default="challenger_backfill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    end = date.fromisoformat(args.end_date) if args.end_date else None
    if args.dry_run:
        report = plan(args.league, args.days, end)
    else:
        report = run(args.league, args.days, end, args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
