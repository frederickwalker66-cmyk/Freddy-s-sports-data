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
from v8_source_cadence_watchdog import evaluate as source_health
from v8_certification_audit import inspect_archives as certification_audit
from v8_nba_training_intake import audit as nba_training_intake, load_review_packets
from v8_nba_oos_research import benchmark as nba_oos_benchmark, save as save_nba_oos
from v8_nba_forward_research import capture as capture_nba_forward
from v8_nfl_nhl_forward import capture as capture_new_sport_forward
from v8_nfl_nhl_board_view import read_boards as read_sport_research_boards
from v8_nba_forward_grade import load_archived_forecasts, grade as grade_nba_forward, save as save_nba_forward_grading
from v8_forward_leaderboard_view import read_leaderboard
from v8_forward_calibration_view import read_calibration

SPORTS = tuple(WINDOW_END)
COMMANDS = ("run_nba", "run_sports", "run_nfl", "run_nhl", "run_mlb",
            "run_ncaaf", "run_ncaab", "run_mls", "run_uefa", "run_edge", "run_sharp", "run_health", "run_certify", "run_nba_train", "run_nba_oos", "run_nba_forward", "run_nba_grade", "run_leaderboard", "run_calibration", "run_nfl_forward", "run_nhl_forward", "run_sport_board", "model_status")
COMMAND_LEAGUES = {
    "run_nba": ("nba",), "run_nba_forward": ("nba",), "run_nba_grade": ("nba",),
    "run_nfl_forward": ("nfl",), "run_nhl_forward": ("nhl",), "run_sports": SPORTS, "run_nfl": ("nfl",),
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
            sharp_run_ids=(), source_run_metadata=None,
            certification_source_dir=None, certification_sharp_dir=None,
            certification_source_run_id=None, certification_sharp_run_id=None,
            nba_review_packets=None, nba_qualified_history=None,
            nba_forward_runner=None, nba_grading_archive_dir=None,
            nba_grading_outcome_collector=None, leaderboard_file=None,
            calibration_file=None, new_sport_forward_runner=None,
            nfl_nhl_board_files=None):
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
        "source_collection_health": None,
        "certification_review": None,
        "nba_training_intake": None,
        "nba_oos_research": None,
        "nba_forward_research": None,
        "nba_forward_grading": None,
        "forward_leaderboard": None,
        "forward_calibration": None,
        "next_sport_forward_research": None,
        "nfl_nhl_forward_board": None,
    }
    if command == "run_edge":
        report["research_edge_candidates"] = rank_research_edges(edge_rows or [])
    elif command == "run_sharp":
        sharp_report, movements = summarize_sharp_archive(sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        report["sharp_archive"] = sharp_report
        (out / "sharp_line_movements.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in movements), encoding="utf-8")
    elif command == "run_sport_board":
        report["nfl_nhl_forward_board"] = read_sport_research_boards(nfl_nhl_board_files)
    elif command == "run_calibration":
        report["forward_calibration"] = read_calibration(calibration_file)
    elif command == "run_leaderboard":
        report["forward_leaderboard"] = read_leaderboard(leaderboard_file)
    elif command == "run_nba_grade":
        if end_date is not None:
            raise ValueError("prospective_grading_cannot_override_actual_clock")
        if nba_grading_archive_dir is None:
            raise ValueError("original_GitHub_forward_archives_required")
        originals, receipt = load_archived_forecasts(nba_grading_archive_dir)
        grading, grading_ledger = grade_nba_forward(
            originals, as_of=now, collector=nba_grading_outcome_collector, receipt=receipt)
        save_nba_forward_grading(grading, grading_ledger, out)
        report["nba_forward_grading"] = grading
        report["historical_data_only_not_trainable"] = False
        report["by_league"]["nba"] = {
            "status": grading["status"],
            "completed_published_games": grading["real_forward_research_forecasts_graded"],
            "successful_source_days": None,
            "failed_source_days": None,
            "research_forecasts_graded": grading["real_forward_research_forecasts_graded"],
            "data_verified_for_model_training": False,
        }
    elif command in ("run_nfl_forward", "run_nhl_forward"):
        if end_date is not None:
            raise ValueError("forward_prediction_cannot_use_historical_end_date")
        league = selected(command)[0]
        runner = new_sport_forward_runner or capture_new_sport_forward
        original, status = runner(league, out / (league + "_forward"), history_days=days)
        report["historical_data_only_not_trainable"] = False
        report["model_training_data_independently_qualified"] = False
        report["next_sport_forward_research"] = status
        report["by_league"][league] = {
            "status": "clocktime_forward_probability_research_only",
            "completed_published_games": status["published_history_retrieved"],
            "successful_source_days": status["source_days_ok"],
            "failed_source_days": status["source_days_failed"],
            "research_forecast_count": len(original),
            "data_verified_for_model_training": False,
        }
    elif command == "run_nba_forward":
        if end_date is not None:
            raise ValueError("forward_prediction_cannot_use_historical_end_date")
        runner = nba_forward_runner if nba_forward_runner is not None else capture_nba_forward
        forward, forward_report = runner(out / "nba_forward", history_days=days)
        report["historical_data_only_not_trainable"] = False
        report["model_training_data_independently_qualified"] = False
        report["nba_forward_research"] = forward_report
        report["by_league"]["nba"] = {
            "status": "genuine_pregame_forecast_research_only",
            "completed_published_games": forward_report["history_games_retrieved"],
            "successful_source_days": forward_report["source_days_succeeded"],
            "failed_source_days": forward_report["source_days_failed"],
            "research_forecast_count": len(forward),
            "data_verified_for_model_training": False,
        }
    elif command == "run_nba_oos":
        backfill_plan("nba", days, stop, now=now)
        nba_source_dir = out / "nba"
        kwargs = {"end_date": stop, "days": days, "output_dir": str(nba_source_dir)}
        if collector is not None:
            kwargs["collector"] = collector
        if now is not None:
            kwargs["clock"] = now
        receipt = backfill("nba", **kwargs)
        source_file = nba_source_dir / "published_results.jsonl"
        published = [json.loads(x) for x in source_file.read_text(encoding="utf-8").splitlines()
                     if x.strip()]
        nba_diag, nba_ledger = nba_oos_benchmark(published, receipt, now=now)
        report["nba_oos_research"] = nba_diag
        report["by_league"]["nba"] = {
            "status": nba_diag["status"],
            "completed_published_games": nba_diag["published_completed_games"],
            "successful_source_days": nba_diag["source_days_successfully_returned"],
            "failed_source_days": nba_diag["source_days_failed"],
            "data_verified_for_model_training": False,
        }
        save_nba_oos(nba_diag, nba_ledger, out)
    elif command == "run_nba_train":
        rows, trained_report, trained_model = nba_training_intake(
            nba_review_packets or [], now=now, qualified_history=nba_qualified_history)
        report["nba_training_intake"] = trained_report
        (out / "NBA_ORIGINAL_REVIEW_WORKLIST.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        (out / "NBA_RESEARCH_INTAKE.json").write_text(
            json.dumps(trained_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if trained_model is not None:
            artifact = out / "NBA_UNVERIFIED_RESEARCH_MODEL.json"
            if artifact.exists():
                raise FileExistsError("refusing_to_overwrite_existing_native_research_artifact")
            artifact.write_text(json.dumps(trained_model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif command == "run_certify":
        report["certification_review"] = certification_audit(
            source_dir=certification_source_dir, sharp_dir=certification_sharp_dir,
            source_run_id=certification_source_run_id,
            sharp_run_id=certification_sharp_run_id)
    elif command == "run_health":
        report["source_collection_health"] = source_health(
            source_run_metadata if source_run_metadata is not None else {"fetch_error": True}, now=now)
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
    if command == "run_certify":
        (out / "CERTIFICATION_AUDIT.json").write_text(
            json.dumps(report["certification_review"], indent=2, sort_keys=True)
            + "\n", encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--command", choices=COMMANDS, default="model_status")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--end-date", default="")
    p.add_argument("--edge-input", help="Optional JSONL of external research forecasts and quotes")
    p.add_argument("--sharp-archive-dir", help="Downloaded existing SharpAPI run artifacts; no API calls")
    p.add_argument("--source-runs-json", help="Actual GitHub source workflow metadata for read-only health view")
    p.add_argument("--certification-source-dir", help="Downloaded matching source pipeline artifact directory")
    p.add_argument("--nba-review-dir", help="Previously captured original NBA source review packets (research only)")
    p.add_argument("--nba-grade-archives-dir", help="Saved completed Github forward runs including original schedule bytes and run metadata")
    p.add_argument("--leaderboard-file", help="Read-only persisted V8 forward-research scorecard")
    p.add_argument("--calibration-file", help="Read-only persisted V8 forward calibration report")
    p.add_argument("--nfl-board-file", help="Read-only persistent NFL forward research scorecard")
    p.add_argument("--nhl-board-file", help="Read-only persistent NHL forward research scorecard")
    p.add_argument("--nba-qualified-history", help="Distinct independently reviewed NBA history file; only for unverified native research training")
    p.add_argument("--certification-sharp-dir", help="Downloaded SharpAPI market baseline artifact directory")
    p.add_argument("--certification-source-run-id", type=int, help="Source workflow ID for evidence tracking")
    p.add_argument("--certification-sharp-run-id", type=int, help="Sharp workflow ID for research price reference")
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
    source_metadata = None
    if args.command == "run_health" and args.source_runs_json:
        source_metadata = json.loads(Path(args.source_runs_json).read_text(encoding="utf-8"))
    nba_review_packets = []
    nba_qualified_history = None
    if args.command == "run_nba_train":
        if args.nba_review_dir:
            nba_review_packets, _ = load_review_packets(args.nba_review_dir)
        if args.nba_qualified_history:
            native_path = Path(args.nba_qualified_history)
            if not native_path.is_file() or native_path.is_symlink() or native_path.name in (
                    "original_bytes_lineage_review.jsonl", "all_sports_evidence_review_queue.jsonl",
                    "historical_published_results.jsonl"):
                raise ValueError("unreviewed_or_missing_nba_native_training_file")
            nba_qualified_history = [json.loads(x) for x in native_path.read_text(encoding="utf-8").splitlines()
                                     if x.strip()]
    stop = date.fromisoformat(args.end_date) if args.end_date else None
    report = execute(args.command, args.days, stop, rows, output_dir=args.output_dir,
                     sharp_rows=sharp_rows, sharp_run_ids=sharp_run_ids,
                     source_run_metadata=source_metadata,
                     certification_source_dir=args.certification_source_dir,
                     certification_sharp_dir=args.certification_sharp_dir,
                     certification_source_run_id=args.certification_source_run_id,
                     certification_sharp_run_id=args.certification_sharp_run_id,
                     nba_review_packets=nba_review_packets, nba_qualified_history=nba_qualified_history,
                     nba_grading_archive_dir=args.nba_grade_archives_dir,
                     leaderboard_file=args.leaderboard_file,
                     calibration_file=args.calibration_file,
                     nfl_nhl_board_files={"nfl":args.nfl_board_file, "nhl":args.nhl_board_file})
    print(json.dumps({"command": args.command, "leagues": report["requested_leagues"],
                      "research_edges": len(report["research_edge_candidates"]),
                      "certified_bets": 0, "output": args.output_dir},
                     sort_keys=True))


if __name__ == "__main__":
    main()
