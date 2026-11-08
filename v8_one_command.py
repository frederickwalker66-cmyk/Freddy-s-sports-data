"""V8 all-in-one, safe phone research command: NBA or eight-sport historical scan.

Makes *bounded* public source calls (at most 35 days per league). No provider
secrets, paid APIs, trained-model fabrication, certified bets, or wagers.
Results are historical published scores, not authenticated pregame evidence.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger_historical_backfill import run as backfill, plan as backfill_plan, WINDOW_END
from v8_dual_milestone_runner import run as train_both
from v8_edge_value import rank_research_edges
from v8_sharp_archive import summarize_sharp_archive, read_archive

SPORTS = tuple(WINDOW_END)
COMMANDS = ("run_nba", "run_sports", "run_nfl", "run_nhl", "run_mlb",
            "run_ncaaf", "run_ncaab", "run_mls", "run_uefa", "run_edge", "run_sharp", "model_status")
COMMAND_LEAGUES = {
    "run_nba": ("nba",), "run_sports": SPORTS, "run_nfl": ("nfl",),
    "run_nhl": ("nhl",), "run_mlb": ("mlb",), "run_ncaaf": ("ncaaf",),
    "run_ncaab": ("ncaab",), "run_mls": ("mls",),
    "run_uefa": ("uefa_champions_league",),
}


def selected(command):
    if command not in COMMANDS:
        raise ValueError("unsupported_command")
    return COMMAND_LEAGUES.get(command, ())


def default_end_date(now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_clock_required")
    return now.astimezone(ZoneInfo("America/New_York")).date() - timedelta(days=1)


def execute(command, days=7, end_date=None, edge_rows=None, collector=None,
            now=None, output_dir="v8_results/one_command", sharp_rows=None,
            sharp_run_ids=()):
    leagues = selected(command)
    if type(days) is not int or not 1 <= days <= 35:
        raise ValueError("days_must_be_1_to_35")
    stop = end_date if end_date is not None else default_end_date(now)
    if not isinstance(stop, date) or isinstance(stop, datetime):
        raise ValueError("invalid_end_date")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "command": command, "requested_days_per_sport": days,
        "historical_end_et": stop.isoformat(),
        "requested_leagues": list(leagues),
        "sportsbook_api_requests": 0, "money_wagered_usd": 0,
        "champion_001_modified": False,
        "independently_verified_model_predictions": 0,
        "certified_positive_ev_bets": 0,
        "historical_data_only_not_trainable": True,
        "by_league": {},
        "research_edge_candidates": [],
        "sharp_archive": None,
    }
    if command == "run_edge":
        report["research_edge_candidates"] = rank_research_edges(edge_rows or [])
    elif command == "run_sharp":
        sharp_report, movements = summarize_sharp_archive(sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        report["sharp_archive"] = sharp_report
        (out / "sharp_line_movements.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\\n" for x in movements), encoding="utf-8")
    elif command == "model_status":
        dual, _, _ = train_both([], [])
        report["model_status"] = {
            "milestone_a": dual["milestone_a_nba"]["status"],
            "milestone_b_independently_complete": False,
            "research_models_fitted_this_run": [],
        }
    else:
        # Preflight every date range before any network calls; reject bad requests.
        for lg in leagues:
            backfill_plan(lg, days, stop, now=now)
        for lg in leagues:
            dest = out / lg
            try:
                kwargs = {"end_date": stop, "days": days, "output_dir": str(dest)}
                if collector is not None:
                    kwargs["collector"] = collector
                if now is not None:
                    kwargs["clock"] = now
                result = backfill(lg, **kwargs)
                report["by_league"][lg] = {
                    "status": "collected_research_only",
                    "completed_published_games": result["published_completed_game_results"],
                    "successful_source_days": result["scoreboard_days_successful"],
                    "failed_source_days": result["scoreboard_days_failed"],
                    "data_verified_for_model_training": False,
                }
            except (ValueError, ConnectionError, OSError, TimeoutError, RuntimeError) as exc:
                report["by_league"][lg] = {
                    "status": "collection_failed",
                    "error": type(exc).__name__,
                    "data_verified_for_model_training": False,
                }
    (out / "ONE_COMMAND_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--command", choices=COMMANDS, default="model_status")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--end-date", default="")
    p.add_argument("--edge-input", help="Optional JSONL of external research forecasts and quotes")
    p.add_argument("--sharp-archive-dir", help="Downloaded existing SharpAPI run artifacts; no API calls")
    p.add_argument("--output-dir", default="v8_results/one_command")
    args = p.parse_args(argv)
    rows = None
    if args.edge_input:
        path = Path(args.edge_input)
        if not path.is_file():
            raise FileNotFoundError(path)
        rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    sharp_rows, sharp_run_ids = [], []
    if args.command == "run_sharp" and args.sharp_archive_dir:
        sharp_rows, sharp_run_ids, _ = read_archive(args.sharp_archive_dir)
    stop = date.fromisoformat(args.end_date) if args.end_date else None
    report = execute(args.command, args.days, stop, rows, output_dir=args.output_dir,
                     sharp_rows=sharp_rows, sharp_run_ids=sharp_run_ids)
    print(json.dumps({"command": args.command, "leagues": report["requested_leagues"],
                      "research_edges": len(report["research_edge_candidates"]),
                      "certified_bets": 0, "output": args.output_dir},
                     sort_keys=True))


if __name__ == "__main__":
    main()
