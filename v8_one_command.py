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
from v8_probability_edge_dashboard import build_dashboard, render_dashboard
from v8_sharp_archive import summarize_sharp_archive, read_archive
from v8_sharp_player_props import summarize_player_props
from v8_sharp_game_markets import summarize_full_game_markets
from v8_mixed_market_board import mixed_market_board
from v8_sgo_research import audit_source_archive
from v8_source_cadence_watchdog import evaluate as source_health
from v8_certification_audit import inspect_archives as certification_audit
from v8_audit_reconciliation import inspect_full as full_audit
from v8_nba_training_intake import audit as nba_training_intake, load_review_packets
from v8_nba_oos_research import benchmark as nba_oos_benchmark, save as save_nba_oos
from v8_nba_forward_research import capture as capture_nba_forward
from v8_nfl_nhl_forward import capture as capture_new_sport_forward
from v8_nfl_nhl_board_view import read_boards as read_sport_research_boards
from v8_nba_forward_grade import load_archived_forecasts, grade as grade_nba_forward, save as save_nba_forward_grading
from v8_forward_leaderboard_view import read_leaderboard
from v8_forward_calibration_view import read_calibration
from v8_sharp_calibration_dashboard import dashboard as sharp_calibration_dashboard
from v8_arbitrage_research import scan_arbitrage
from v8_betting_readiness import audit_betting_readiness, save_readiness
from v8_nba_slate_best_bets import run as run_nba_slate_best_bets
from v8_nba_five_leg_preflight import audit_five_leg_preflight
from v8_clv_reconciliation import reconcile as reconcile_local_clv
from v8_season_artifact_view import review as review_season_artifacts
from v8_nba_always_sharp_edge import build_nba_sharp_edge, save as save_nba_sharp_edge

SPORTS = tuple(WINDOW_END)
COMMANDS = ("run_nba", "run_nba_best_bets", "run_sports", "run_season_form", "run_nfl", "run_nhl", "run_mlb",
            "run_ncaaf", "run_ncaab", "run_mls", "run_uefa", "run_edge", "run_sharp", "run_nfl_props_edge", "run_mixed_market", "run_arbitrage", "run_health", "run_readiness", "run_certify", "run_audit", "run_nba_train", "run_nba_oos", "run_nba_forward", "run_nba_grade", "run_leaderboard", "run_calibration", "run_nfl_forward", "run_nhl_forward", "run_sport_board", "model_status")
COMMAND_LEAGUES = {
    "run_nba": ("nba",), "run_nba_best_bets": ("nba",), "run_season_form": SPORTS, "run_nba_forward": ("nba",), "run_nba_grade": ("nba",),
    "run_nfl_forward": ("nfl",), "run_nhl_forward": ("nhl",), "run_sports": SPORTS, "run_nfl": ("nfl",),
    "run_nhl": ("nhl",), "run_mlb": ("mlb",), "run_ncaaf": ("ncaaf",),
    "run_ncaab": ("ncaab",), "run_mls": ("mls",),
    "run_uefa": ("uefa_champions_league",),
    "run_nfl_props_edge": ("nba", "nfl"),
    "run_mixed_market": ("nba", "nfl"),
    "run_arbitrage": SPORTS,
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
            arbitrage_rows=None, sgo_archive_dir=None,
            sharp_run_ids=(), source_run_metadata=None,
            certification_source_dir=None, certification_sharp_dir=None,
            certification_source_run_id=None, certification_sharp_run_id=None,
            nba_review_packets=None, nba_qualified_history=None,
            nba_forward_runner=None, nba_grading_archive_dir=None,
            nba_grading_outcome_collector=None, leaderboard_file=None,
            calibration_file=None, new_sport_forward_runner=None,
            nfl_nhl_board_files=None, audit_outcome_dir=None,
            audit_calibration_dir=None, audit_outcome_run_id=None,
            audit_calibration_run_id=None, nba_best_bets_runner=None,
            season_archive_dir=None):
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
        "research_forward_probability_rows": [],
        "probability_sharp_edge_dashboard": None,
        "sharp_archive": None,
        "sharp_player_props": None,
        "sharp_full_game_markets": None,
        "nba_always_sharp_edge": None,
        "mixed_market_research": None,
        "sportsgameodds_archive_research": None,
        "sharp_edge_calibration": None,
        "sharp_edge_clv": None,
        "arbitrage_research": None,
        "nfl_and_player_props_edge_research": None,
        "source_collection_health": None,
        "betting_readiness": None,
        "certification_review": None,
        "comprehensive_audit": None,
        "nba_training_intake": None,
        "nba_oos_research": None,
        "nba_forward_research": None,
        "nba_slate_best_bets": None,
        "season_to_date_all_leagues": None,
        "nba_five_leg_preflight": None,
        "nba_local_clv_receipt_status": None,
        "nba_forward_grading": None,
        "forward_leaderboard": None,
        "forward_calibration": None,
        "next_sport_forward_research": None,
        "nfl_nhl_forward_board": None,
    }
    if command == "run_nba_best_bets":
        if end_date is not None:
            raise ValueError("tonight_NBA_slate_cannot_use_historical_end_date")
        # One command includes the original current-date ESPN schedule, a fresh
        # independent Elo research capture, ALL archived NBA SGO lines/player
        # props, existing SharpAPI movement and persisted calibration evidence.
        # No paid collection, cross-provider odds promotion, or wagers.
        calibration = sharp_calibration_dashboard(calibration_file)
        report["sharp_edge_calibration"] = calibration
        runner = nba_best_bets_runner or run_nba_slate_best_bets
        extras = ({"season_history_dir": Path(season_archive_dir) / "nba"}
                  if season_archive_dir is not None and
                  nba_best_bets_runner is None else {})
        slate, forecasts = runner(out / "nba_best_bets", days=days, now=now,
                                   sgo_archive_dir=sgo_archive_dir,
                                   calibration=calibration, **extras)
        report["season_to_date_all_leagues"] = review_season_artifacts(
            season_archive_dir or out / "missing_season_archive")
        if (slate.get("champion_001_modified") is not False
                or slate.get("independently_certified_positive_ev_bets") != 0):
            raise ValueError("unsafe_NBA_slate_betting_certification")
        report["nba_slate_best_bets"] = slate
        five_leg = audit_five_leg_preflight(slate, calibration)
        report["nba_five_leg_preflight"] = five_leg
        (out / "NBA_FIVE_LEG_PREFLIGHT.json").write_text(
            json.dumps(five_leg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # Cloud runs intentionally receive NO private user betting receipts.
        # This documents the exact-market entry/close CLV evidence gap.
        clv_status = reconcile_local_clv([], [])
        report["nba_local_clv_receipt_status"] = clv_status
        (out / "NBA_CLV_RECEIPT_READINESS.json").write_text(
            json.dumps(clv_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tonight_ids = {g["espn_event_id"] for g in slate["games"]}
        report["research_forward_probability_rows"] = [
            row for row in forecasts if row.get("espn_event_id") in tonight_ids]
        report["nba_forward_research"] = slate.get("nba_forward_research_status")
        report["historical_data_only_not_trainable"] = False
        report["by_league"]["nba"] = {
            "status": ("clocktime_all_NBA_games_research_only" if
                       slate.get("source_coverage_complete_for_all_nba_games")
                       else "HOLD_no_complete_NBA_schedule"),
            "published_slate_games": slate["slate_game_count_from_original_source"],
            "research_forecast_count_today": len(report["research_forward_probability_rows"]),
            "paired_archived_reference_markets": slate["paired_archive_market_count"],
            "verified_current_executable_quotes": 0,
            "certified_positive_ev_bets": 0,
            "data_verified_for_model_training": False,
        }
        sharp, _ = summarize_sharp_archive(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        props, _ = summarize_player_props(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        full, _ = summarize_full_game_markets(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        report["sharp_archive"] = sharp
        report["sharp_player_props"] = props
        report["sharp_full_game_markets"] = full
        always_edge = build_nba_sharp_edge(
            sharp, props, full, calibration, report["season_to_date_all_leagues"])
        report["nba_always_sharp_edge"] = always_edge
        save_nba_sharp_edge(always_edge, out)
        report["sharp_edge_clv"] = {
            "report_type": "NBA_ENTRY_TO_REAL_CLOSE_CLV_EVIDENCE_GATE",
            "status": "HOLD_NO_TRACKED_ENTRY_AND_AUTHENTIC_CLOSING_QUOTE",
            "verified_clv_percent": None, "matching_verified_entry_close_pairs": 0,
            "archived_same_market_repricings_are_not_CLV": True,
            "certified_positive_ev_bets": 0, "champion_001_modified": False,
        }
        report["sportsgameodds_archive_research"] = audit_source_archive(
            sgo_archive_dir, now=now)
    elif command == "run_season_form":
        report["season_to_date_all_leagues"] = review_season_artifacts(
            season_archive_dir or out / "missing_season_archive")
        (out / "ALL_EIGHT_LEAGUES_SEASON_LAST5_LAST10.json").write_text(
            json.dumps(report["season_to_date_all_leagues"],
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif command == "run_edge":
        report["research_edge_candidates"] = rank_research_edges(edge_rows or [])
    elif command == "run_arbitrage":
        # Crossbook mathematical screening independent of predictive model EV.
        # Existing SharpAPI archives only contain one book and cannot certify
        # execution or create opportunities from missing second-book prices.
        arb = scan_arbitrage(arbitrage_rows if arbitrage_rows is not None
                             else (sharp_rows or []), now=now)
        report["arbitrage_research"] = arb
        (out / "ARBITRAGE_RESEARCH.json").write_text(
            json.dumps(arb, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif command in ("run_sharp", "run_nfl_props_edge", "run_mixed_market"):
        # Read only already downloaded SharpAPI archives. Sportsbook-labeled
        # moneylines and exact-line player prop repricing are market research,
        # not native probabilities, sharp handle data, or certified EV.
        sharp_report, movements = summarize_sharp_archive(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        prop_report, prop_movements = summarize_player_props(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        game_report, game_movements = summarize_full_game_markets(
            sharp_rows or [], now=now, archive_run_ids=sharp_run_ids)
        report["sharp_archive"] = sharp_report
        report["sharp_player_props"] = prop_report
        report["sharp_full_game_markets"] = game_report
        if command == "run_mixed_market":
            # All four quote categories share one HOLD-only reference board.
            # No market can be ranked by profit without native exact-line p.
            mixed = mixed_market_board(game_report, prop_report)
            report["mixed_market_research"] = mixed
            sgo = audit_source_archive(sgo_archive_dir, now=now)
            report["sportsgameodds_archive_research"] = sgo
            # Keep provider feeds separated: SGO has unverified event/player
            # identities and main-market status, and cannot become SharpAPI EV.
            (out / "SGO_SEPARATE_SOURCE_RESEARCH.json").write_text(
                json.dumps(sgo, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (out / "MIXED_MARKET_GAME_PROP_RESEARCH.json").write_text(
                json.dumps(mixed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        calibration = sharp_calibration_dashboard(calibration_file)
        report["sharp_edge_calibration"] = calibration
        # A pre-close market reprice is never closing-line value. No actual
        # entry/closing-pair evidence is supplied to this archive-only scan.
        # Null CLV is required: it is unknown, NOT a zero-return bet.
        clv = {
            "report_type": "NBA_NFL_SHARP_EDGE_CLV_EVIDENCE_READINESS",
            "status": "HOLD_NO_TRACKED_ENTRY_AND_AUTHENTIC_CLOSING_QUOTE",
            "tracked_verified_entry_receipts_in_this_run": 0,
            "tracked_matching_verified_closing_quote_receipts_in_this_run": 0,
            "exact_market_entry_close_pairs": 0,
            "realized_clv_percent": None,
            "measured_positive_clv_bets": None,
            "archived_provider_market_repricing_observations": (
                len(game_movements) + len(prop_movements)),
            "market_repricing_is_verified_clv": False,
            "current_prestart_quotes_are_closing_prices": False,
            "requires": ("timestamped original selection, line and actual entry price; "
                         "independently verified same-market closing quote "
                         "at or just before the event starts"),
            "certified_positive_ev_bets": 0,
            "champion_001_modified": False,
            "automated_wagers": 0,
        }
        report["sharp_edge_clv"] = clv
        report["nfl_and_player_props_edge_research"] = {
            "nfl_primary_moneyline_archive_observations":
                sharp_report["eligible_quotes_by_league"].get("nfl", 0),
            "nfl_exact_prop_archive_observations":
                prop_report["valid_prop_quotes_by_league"].get("nfl", 0),
            "nba_exact_prop_archive_observations":
                prop_report["valid_prop_quotes_by_league"].get("nba", 0),
            "upcoming_research_prop_repricings":
                prop_report["upcoming_repricing_research_observations"],
            "prop_quotes_matched_by_provider_name_only_unverified":
                prop_report["valid_provider_name_only_quote_observations_research_only"],
            "prop_quotes_with_provider_id_unverified":
                prop_report["valid_provider_id_plus_name_quote_observations_research_only"],
            "prop_identity_conflict_market_groups_quarantined":
                prop_report["conflicting_provider_identity_market_groups_excluded"],
            "independently_verified_athlete_identities": 0,
            "today_nba_nfl_full_game_board_count":
                game_report["today_recent_upcoming_full_games"],
            "today_full_game_market_movement_research_observations":
                game_report["today_recent_upcoming_market_movement_observations"],
            "today_full_game_price_probability_boards":
                game_report["today_recent_upcoming_full_games"],
            "today_paired_prop_price_probability_markets":
                prop_report["today_recent_two_sided_prop_markets"],
            "calibration_status":
                calibration["persisted_nba_original_forward_calibration_status"],
            "clv_status": clv["status"],
            "nba_original_forward_games_graded_for_calibration":
                calibration["nba_original_graded_outcomes"],
            "independently_certified_exact_market_calibration": False,
            "price_implied_and_no_vig_probabilities_available": True,
            "independent_sharp_bettor_probability_available": False,
            "certified_model_probability_available": False,
            "validated_full_game_quote_rows_by_market":
                game_report["validated_source_quote_observations_by_league_and_market"],
            "verified_professional_sharp_flow": False,
            "verified_native_model_probabilities": 0,
            "verified_draftkings_checkout_quotes": 0,
            "certified_positive_ev_bets": 0,
            "bet_ready_selections": 0,
            "champion_001_modified": False,
            "decision": "PASS_NO_INDEPENDENTLY_VERIFIED_EDGE",
        }
        (out / "sharp_line_movements.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in movements), encoding="utf-8")
        (out / "sharp_prop_line_movements.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in prop_movements), encoding="utf-8")
        (out / "sharp_game_market_movements.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in game_movements),
            encoding="utf-8")
        (out / "NBA_NFL_FULL_GAME_MARKETS_RESEARCH.json").write_text(
            json.dumps(game_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        probability_board = {
            "report_type": "NBA_NFL_SHARP_EDGE_PRICE_PROBABILITIES_RESEARCH_ONLY",
            "source": "draftkings_labeled_sharpapi_archives_not_checkout",
            "full_games": game_report["today_game_market_board"],
            "nba_player_props":
                prop_report["today_player_prop_market_probability_board"]["nba"],
            "nfl_player_props":
                prop_report["today_player_prop_market_probability_board"]["nfl"],
            "native_model_probability": None,
            "verified_sharp_flow_probability": None,
            "certified_positive_ev_bets": 0,
            "champion_001_modified": False,
            "automated_wagers": 0,
            "decision": "HOLD_MARKET_PRICES_NOT_MODEL_PROBABILITIES",
        }
        (out / "NBA_NFL_SHARP_EDGE_PROBABILITIES.json").write_text(
            json.dumps(probability_board, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (out / "NBA_NFL_SHARP_EDGE_CALIBRATION.json").write_text(
            json.dumps(calibration, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (out / "NBA_NFL_SHARP_EDGE_CLV.json").write_text(
            json.dumps(clv, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (out / "NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json").write_text(
            json.dumps(report["nfl_and_player_props_edge_research"],
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif command == "run_readiness":
        # An explicit PC/phone command that requires real saved sources.
        # It does not create any calibrated probabilities or auto-certify
        # even if a historical/aggregator research market looks favorable.
        result = audit_betting_readiness(
            calibration_file=calibration_file, sharp_rows=sharp_rows,
            sharp_run_ids=sharp_run_ids, now=now)
        report["betting_readiness"] = result
        save_readiness(result, out / "BETTING_READINESS.json")
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
        report["research_forward_probability_rows"] = original[:25]
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
        report["research_forward_probability_rows"] = forward[:25]
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
    elif command == "run_audit":
        report["comprehensive_audit"] = full_audit(
            source_dir=certification_source_dir, sharp_dir=certification_sharp_dir,
            outcome_dir=audit_outcome_dir, calibration_dir=audit_calibration_dir,
            source_run_id=certification_source_run_id,
            sharp_run_id=certification_sharp_run_id,
            outcome_run_id=audit_outcome_run_id,
            calibration_run_id=audit_calibration_run_id)
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
    if command == "run_sports":
        report["season_to_date_all_leagues"] = review_season_artifacts(
            season_archive_dir or out / "missing_season_archive")
        (out / "ALL_EIGHT_LEAGUES_SEASON_LAST5_LAST10.json").write_text(
            json.dumps(report["season_to_date_all_leagues"],
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # A consistent independent-vs-market percentage report for EVERY successful command.
    # This never certifies a price, forecast, sharp-money flow or wager.
    dashboard = build_dashboard(report)
    report["probability_sharp_edge_dashboard"] = dashboard
    (out / "PROBABILITY_SHARP_EDGE_DASHBOARD.json").write_text(
        json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "PROBABILITY_SHARP_EDGE_DASHBOARD.md").write_text(
        render_dashboard(dashboard), encoding="utf-8")
    (out / "ONE_COMMAND_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if command == "run_audit":
        (out / "FULL_AUDIT_REPORT.json").write_text(
            json.dumps(report["comprehensive_audit"], indent=2, sort_keys=True)
            + "\n", encoding="utf-8")
    if command == "run_certify":
        (out / "CERTIFICATION_AUDIT.json").write_text(
            json.dumps(report["certification_review"], indent=2, sort_keys=True)
            + "\n", encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--command", choices=COMMANDS, default="model_status")
    p.add_argument("--days", type=int, default=None)
    p.add_argument("--end-date", default="")
    p.add_argument("--edge-input", help="Optional JSONL of external research forecasts and quotes")
    p.add_argument("--sharp-archive-dir", help="Downloaded existing SharpAPI run artifacts; no API calls")
    p.add_argument("--sgo-archive-dir", help="Downloaded existing SportsGameOdds run artifacts; no API calls")
    p.add_argument("--season-archive-dir", help="Saved season scoreboard and player boxscore artifacts; no source redating")
    p.add_argument("--arbitrage-input", help="Optional local canonical crossbook research-quote JSONL; never a live betting feed")
    p.add_argument("--source-runs-json", help="Actual GitHub source workflow metadata for read-only health view")
    p.add_argument("--certification-source-dir", help="Downloaded matching source pipeline artifact directory")
    p.add_argument("--nba-review-dir", help="Previously captured original NBA source review packets (research only)")
    p.add_argument("--nba-grade-archives-dir", help="Saved completed Github forward runs including original schedule bytes and run metadata")
    p.add_argument("--leaderboard-file", help="Read-only persisted V8 forward-research scorecard")
    p.add_argument("--calibration-file", help="Read-only persisted V8 forward calibration report")
    p.add_argument("--nfl-board-file", help="Read-only persistent NFL forward research scorecard")
    p.add_argument("--nhl-board-file", help="Read-only persistent NHL forward research scorecard")
    p.add_argument("--nba-qualified-history", help="Distinct independently reviewed NBA history file; only for unverified native research training")
    p.add_argument("--audit-outcome-dir", help="Saved completed outcome review artifact root")
    p.add_argument("--audit-calibration-dir", help="Saved completed calibration artifact root")
    p.add_argument("--audit-outcome-run-id", type=int)
    p.add_argument("--audit-calibration-run-id", type=int)
    p.add_argument("--certification-sharp-dir", help="Downloaded SharpAPI market baseline artifact directory")
    p.add_argument("--certification-source-run-id", type=int, help="Source workflow ID for evidence tracking")
    p.add_argument("--certification-sharp-run-id", type=int, help="Sharp workflow ID for research price reference")
    p.add_argument("--output-dir", default="v8_results/one_command")
    args = p.parse_args(argv)
    # Phone command "run NBA" always invokes the full research board,
    # including both sharp game/prop repricing, calibrated-model gate and CLV.
    # Direct execute("run_nba", end_date=...) stays a legacy HISTORICAL
    # source-only API for existing pinned research fixtures.
    if args.command == "run_nba":
        args.command = "run_nba_best_bets"
    rows = None
    if args.edge_input:
        path = Path(args.edge_input)
        if not path.is_file():
            raise FileNotFoundError(path)
        rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    sharp_rows, sharp_run_ids = [], []
    if args.command in ("run_sharp", "run_nfl_props_edge", "run_mixed_market", "run_nba_best_bets", "run_arbitrage", "run_readiness") and args.sharp_archive_dir:
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
    arbitrage_rows = None
    if args.command == "run_arbitrage" and args.arbitrage_input:
        path = Path(args.arbitrage_input)
        if not path.is_file() or path.is_symlink():
            raise ValueError("arbitrage_input_must_be_local_existing_file")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 50000:
            raise ValueError("arbitrage_input_row_budget_exceeded")
        arbitrage_rows = [json.loads(s) for s in lines if s.strip()]
        # Distinct manual sportsbook evidence may accompany downloaded
        # single-book archival observations, but cannot attest real checkout.
        arbitrage_rows += sharp_rows
    stop = date.fromisoformat(args.end_date) if args.end_date else None
    history_days = args.days if args.days is not None else (35 if args.command == "run_nba_best_bets" else 7)
    report = execute(args.command, history_days, stop, rows, output_dir=args.output_dir,
                     sharp_rows=sharp_rows, sharp_run_ids=sharp_run_ids,
                     arbitrage_rows=arbitrage_rows, sgo_archive_dir=args.sgo_archive_dir,
                     source_run_metadata=source_metadata,
                     certification_source_dir=args.certification_source_dir,
                     certification_sharp_dir=args.certification_sharp_dir,
                     certification_source_run_id=args.certification_source_run_id,
                     certification_sharp_run_id=args.certification_sharp_run_id,
                     audit_outcome_dir=args.audit_outcome_dir,
                     audit_calibration_dir=args.audit_calibration_dir,
                     audit_outcome_run_id=args.audit_outcome_run_id,
                     audit_calibration_run_id=args.audit_calibration_run_id,
                     nba_review_packets=nba_review_packets, nba_qualified_history=nba_qualified_history,
                     nba_grading_archive_dir=args.nba_grade_archives_dir,
                     leaderboard_file=args.leaderboard_file,
                     calibration_file=args.calibration_file,
                     nfl_nhl_board_files={"nfl":args.nfl_board_file, "nhl":args.nhl_board_file},
                     season_archive_dir=args.season_archive_dir)
    print(json.dumps({"command": args.command, "leagues": report["requested_leagues"],
                      "research_edges": len(report["research_edge_candidates"]),
                      "certified_bets": 0, "output": args.output_dir},
                     sort_keys=True))


if __name__ == "__main__":
    main()

# User-triggered NBA research execution on 2026-11-13; analytics unchanged.
# Nov 13 2026 user-requested NBA sharp edge, player-prop, CLV, calibration and 5-leg parlay research rerun.
# Archived sources only; no wagers; never promote unverified props or missing model probabilities.
# User-requested NBA refresh, 2026-11-13: research-only game market, player last-five/ten form, sharp edge, CLV and parlay preflight; no wager.
# Post-season-data-refresh: reload 8-league complete-scoreboard and player L5/L10 GH research artifacts on NBA command.
# User-requested immediate model refresh after eight-league season L5/L10 source collection, research-only, no stakes.
