"""Grade actual archived V8 forward NBA research forecasts without altering them.

Inputs MUST come from completed GitHub Actions forecast artifacts + their own
GitHub API run metadata. Original ESPN schedule bytes are rehashed and checked
against every archived forecast. Outcomes are separately fetched only at
least 48 hours after scheduled tipoff and are matched by exact ESPN event ID,
home/away ESPN IDs and game date.

ESPN published finals are not league adjudication or sportsbook settlement.
Neither this scorecard nor GitHub timestamps independently certify probabilities
or original Champion-001 shadows. No bets or bookmaker requests.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from challenger_elo_walkforward import validate_game
from historical_outcomes import collect as collect_results, parse_time, scoreboard_url
from v8_nba_forward_research import VERSION, parse_schedule_original

NY = ZoneInfo("America/New_York")
DELAY_HOURS = 48
MAX_ARCHIVE_RUNS = 35
MAX_ARCHIVE_FORECASTS = 2000
MAX_SOURCE_DAYS = 35
MAX_BYTES_PER_FILE = 10_000_000
MIN_MATURE_GRADED_FOR_AGGREGATES = 50  # Same threshold as durable NBA leaderboard.


def read_json(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_BYTES_PER_FILE:
        raise ValueError("missing_or_unsafe_forward_archive_file")
    return json.loads(p.read_text(encoding="utf-8"))


def read_jsonl(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_BYTES_PER_FILE:
        raise ValueError("missing_or_unsafe_forward_archive_file")
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]


def _load_one_run(root, run_id):
    base = root / str(run_id)
    meta = read_json(base / "github_run.json")
    receipt = read_json(base / "ONE_COMMAND_REPORT.json")
    forecasts = read_jsonl(base / "nba_forward" / "NBA_FORWARD_FORECASTS.jsonl")
    status = read_json(base / "nba_forward" / "NBA_FORWARD_RESEARCH_STATUS.json")
    if (meta.get("id") != run_id or meta.get("head_branch") != "main"
            or meta.get("status") != "completed" or meta.get("conclusion") != "success"
            or meta.get("event") not in ("push", "workflow_dispatch", "schedule")
            or receipt.get("command") != "run_nba_forward"
            or receipt.get("champion_001_modified") is not False
            or receipt.get("certified_positive_ev_bets") != 0
            or status.get("stage") != "v8_elo_genuine_forward_clocktime_research_only"
            or status.get("champion_001_modified") is not False
            or status.get("original_champion_001_predictions_certified") != 0
            or status.get("independently_certified_v8_predictions") != 0
            or status.get("v8_research_forward_predictions") != len(forecasts)
            or status.get("forward_research_probabilities_recorded_before_tipoff") != len(forecasts)):
        raise ValueError("untrusted_or_nonforward_GitHub_run_artifact")
    created = parse_time(meta.get("created_at"))
    updated = parse_time(meta.get("updated_at"))
    capture = parse_time(status.get("captured_at_utc"))
    if not created <= capture <= updated:
        raise ValueError("run_metadata_does_not_bound_forecast_capture")
    if len(forecasts) > MAX_ARCHIVE_FORECASTS:
        raise ValueError("too_many_forecasts_in_one_run")
    original = {}
    valid = []
    for row in forecasts:
        if (not isinstance(row, dict)
                or row.get("record_type") != "v8_genuine_forward_clocktime_NBA_Elo_research_only"
                or row.get("league") != "nba"
                or row.get("model_version") != VERSION
                or row.get("champion_001_modified") is not False
                or row.get("certified_prediction") is not False
                or row.get("champion_001_shadow_certified") is not False
                or row.get("qualifies_for_original_champion_shadow_quota") is not False
                or row.get("forecast_reconstructed_after_game") is not False
                or row.get("bet_ready") is not False
                or row.get("verified_positive_ev") is not False
                or row.get("stake_usd") != 0
                or row.get("outcome") is not None
                or row.get("outcome_observed_at_utc") is not None):
            raise ValueError("forecast_misreported_as_certified_or_settled")
        event_id = row.get("espn_event_id")
        if not isinstance(event_id, str) or not event_id.isdecimal():
            raise ValueError("invalid_espn_forecast_id")
        recorded = parse_time(row["forecast_recorded_utc"])
        scheduled = parse_time(row["start_utc"])
        observed = parse_time(row["schedule_original_received_at_utc"])
        if not created <= observed <= recorded == capture <= updated < scheduled:
            raise ValueError("actual_run_or_capture_not_bounded_before_tipoff")
        p = row.get("model_probability_home_win_research_only")
        q = row.get("estimated_away_win_probability_research_only")
        if (type(p) not in (float, int) or type(q) not in (float, int)
                or not math.isfinite(p) or not math.isfinite(q)
                or not 0 < p < 1 or abs(p + q - 1) > 0.0000011):
            raise ValueError("unsupported_forecast_probability")
        day = scheduled.astimezone(NY).date()
        rawfile = base / "nba_forward" / ("nba_original_future_schedule_" + day.strftime("%Y%m%d") + ".json")
        if day not in original:
            original[day] = read_json(rawfile)
            raw = rawfile.read_bytes()
            url = scoreboard_url("nba", day)
            found = parse_schedule_original(original[day], raw, day, observed, url)
            original[day] = (raw, found)
        raw, parsed = original[day]
        if (row.get("schedule_original_sha256_local_receipt") != hashlib.sha256(raw).hexdigest()
                or row.get("schedule_source_url") != scoreboard_url("nba", day)):
            raise ValueError("source_bytes_or_URL_mismatch")
        matches = [item for item in parsed if item["espn_event_id"] == event_id]
        if len(matches) != 1:
            raise ValueError("forecast_does_not_match_original_schedule_bytes")
        source_game = matches[0]
        for key in ("home_team_espn_id", "away_team_espn_id", "start_utc"):
            if row.get(key) != source_game.get(key):
                raise ValueError("game_identity_drift_from_original_schedule")
        valid.append(dict(row, github_run_id=run_id,
                          github_run_created_at_utc=created.isoformat(),
                          github_run_completed_at_utc=updated.isoformat()))
    return valid


def load_archived_forecasts(archive_root):
    root = Path(archive_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("forecast_archives_directory_required")
    folders = [p for p in root.iterdir() if p.is_dir() and p.name.isdecimal() and not p.is_symlink()]
    if len(folders) > MAX_ARCHIVE_RUNS:
        raise ValueError("forecast_archive_run_budget_exceeded")
    all_rows, exclusions = [], Counter()
    ids = []
    for folder in sorted(folders, key=lambda p: int(p.name)):
        try:
            valid = _load_one_run(root, int(folder.name))
        except (ValueError, KeyError, TypeError, OverflowError, json.JSONDecodeError) as exc:
            exclusions["excluded_untrusted_run_" + type(exc).__name__] += 1
            continue
        all_rows.extend(valid)
        ids.append(int(folder.name))
    if len(all_rows) > MAX_ARCHIVE_FORECASTS:
        raise ValueError("forecast_archive_total_row_budget_exceeded")
    # One canonical earliest valid pregame forecast per exact NBA event ID.
    by_event, conflicts = {}, set()
    for row in sorted(all_rows, key=lambda x: (x["forecast_recorded_utc"], x["github_run_id"])):
        eid = row["espn_event_id"]
        if eid in conflicts:
            exclusions["previously_conflicted_event_quarantined"] += 1
            continue
        if eid in by_event:
            existing = by_event[eid]
            same_event = all(
                row[x] == existing[x] for x in
                ("home_team_espn_id", "away_team_espn_id", "start_utc", "model_version"))
            if not same_event or (row["forecast_recorded_utc"] == existing["forecast_recorded_utc"]
                                 and row["model_probability_home_win_research_only"] !=
                                 existing["model_probability_home_win_research_only"]):
                by_event.pop(eid)
                conflicts.add(eid)
                exclusions["conflicting_forward_event_quarantined"] += 1
            else:
                exclusions["later_duplicate_forecast_not_regraded"] += 1
        else:
            by_event[eid] = row
    return sorted(by_event.values(), key=lambda x: (x["start_utc"], x["espn_event_id"])), {
        "source_github_run_ids": ids,
        "raw_forward_rows_seen": len(all_rows),
        "unique_earliest_forecasts": len(by_event),
        "excluded_archive_or_duplicate_reasons": dict(sorted(exclusions.items())),
    }


def grade(records, as_of=None, collector=None, receipt=None):
    now = as_of or datetime.now(timezone.utc)
    now = parse_time(now.isoformat())
    if not isinstance(records, list):
        raise ValueError("forecasts_must_be_list")
    if len(records) > MAX_ARCHIVE_FORECASTS:
        raise ValueError("forecast_input_budget_exceeded")
    if len({x.get("espn_event_id") for x in records}) != len(records):
        raise ValueError("duplicate_grading_event_id")
    collector = collector or collect_results
    outcomes = {}
    coverage = {}
    mature_days = sorted({
        parse_time(row["start_utc"]).astimezone(NY).date()
        for row in records
        if parse_time(row["start_utc"]) + timedelta(hours=DELAY_HOURS) <= now
    })
    if len(mature_days) > MAX_SOURCE_DAYS:
        # Never silently label unqueried mature days as missed or lost.
        raise ValueError("grading_source_day_budget_exceeded")
    for day in mature_days:
        downloaded, source = collector(("nba",), 1, day)
        stats = source.get("by_league", {}).get("nba", {}) if isinstance(source, dict) else {}
        success = (source.get("leagues") == ["nba"]
                   and source.get("champion_001_modified") is False
                   and source.get("total_completed_results") == len(downloaded)
                   and stats.get("days_attempted") == 1
                   and stats.get("days_ok") == 1 and stats.get("days_failed") == 0)
        coverage[day] = bool(success)
        if not success:
            continue
        # The initial evaluation clock precedes the actual HTTP fetch. The
        # legitimate source receipt is created *after* the response bytes
        # arrive, so comparing it to the pre-fetch clock rejected real ESPN
        # results and crashed the entire live grade job. With an explicitly
        # supplied historical as_of keep that strict deadline to prevent future
        # results leaking into a retrospective evaluation. For live grading
        # accept only receipts no later than the actual completed fetch.
        source_receipt_deadline = (now if as_of is not None
                                   else datetime.now(timezone.utc))
        for row in downloaded:
            lg, started, eid, home, away, actual = validate_game(row)
            if (lg != "nba" or actual not in (0, 1)
                    or parse_time(row.get("retrieved_at_utc")) > source_receipt_deadline
                    or row.get("source_url") != scoreboard_url("nba", day)
                    or started.astimezone(NY).date() != day):
                raise ValueError("unsupported_published_outcome_source")
            if eid in outcomes:
                raise ValueError("duplicate_published_final_game_identity")
            outcomes[eid] = (row, started, home, away, actual)
    ledger, graded, reasons = [], [], Counter()
    for row in sorted(records, key=lambda x: (x["start_utc"], x["espn_event_id"])):
        scheduled = parse_time(row["start_utc"])
        day = scheduled.astimezone(NY).date()
        eid = row["espn_event_id"]
        status = "PENDING_48H_RESULT_MATURITY"
        result = None
        if scheduled + timedelta(hours=DELAY_HOURS) <= now:
            if not coverage.get(day):
                status = "HOLD_SOURCE_DAY_UNAVAILABLE"
            elif eid not in outcomes:
                status = "HOLD_COMPLETED_GAME_NOT_PUBLISHED"
            else:
                published, actual_start, home, away, y = outcomes[eid]
                if (home != row["home_team_espn_id"]
                        or away != row["away_team_espn_id"]
                        or actual_start <= parse_time(row["forecast_recorded_utc"])
                        or abs((actual_start - scheduled).total_seconds()) > 3600):
                    status = "HOLD_SCHEDULE_OR_TEAM_IDENTITY_CHANGED"
                else:
                    status = "GRADED_ESPN_PUBLISHED_FINAL_RESEARCH_ONLY"
                    p = row["model_probability_home_win_research_only"]
                    result = {
                        "home_won_from_ESPN_published_final": y,
                        "espn_published_home_score": published["home_score"],
                        "espn_published_away_score": published["away_score"],
                        "outcome_source_url": published["source_url"],
                        "outcome_retrieved_at_utc": published["retrieved_at_utc"],
                        "per_event_Brier": round((p-y)**2, 9),
                        "per_event_log_loss": round(
                            -(y*math.log(p)+(1-y)*math.log1p(-p)), 9),
                        "probability_classification": (
                            "home" if p > .5 else "away" if p < .5 else "pass"),
                        "winner_classification_correct": (
                            None if p == .5 else (int(p > .5) == y)),
                    }
                    graded.append((p,y,status))
        reasons[status] += 1
        ledger.append({
            "espn_event_id": eid,
            "forecast_original_github_run_id": row["github_run_id"],
            "forecast_recorded_utc": row["forecast_recorded_utc"],
            "original_scheduled_tipoff_utc": row["start_utc"],
            "model_version": row["model_version"],
            "original_model_probability_home_win": row["model_probability_home_win_research_only"],
            "evaluation_status": status,
            "graded_published_result": result,
            "original_forecast_modified": False,
            "official_league_outcome_independently_adjudicated": False,
            "bookmaker_settlement_verified": False,
            "champion_001_certified_shadow": False,
            "certified_prediction": False,
            "verified_positive_ev": False,
            "stake_usd": 0,
        })
    count = len(graded)
    decisions = [(p,y) for p,y,_ in graded if p != .5]
    report = {
        "version": "v8-NBA-forward-outcome-grader-v1",
        "status": ("PROVISIONAL_FORWARD_RESEARCH_RESULTS_NOT_CERTIFIED" if count else
                   "PENDING_OR_MISSING_PUBLISHED_RESULTS"),
        "evaluated_at_utc": now.isoformat(),
        "forecast_rows_in_scope": len(records),
        "real_forward_research_forecasts_graded": count,
        "forecasts_still_pending_or_unmatched": len(records) - count,
        "outcome_status_counts": dict(sorted(reasons.items())),
        "official_league_final_independently_verified": False,
        "model_has_untouched_prospective_research_scorecard": count > 0,
        "model_calibration_independently_certified": False,
        # Individual forward outcomes remain auditable, but aggregate skill
        # numbers are withheld until enough genuine graded predictions exist.
        # Reporting a 1- or 8-game "accuracy" creates misleading confidence.
        "probability_research_Brier": round(mean((p-y)**2 for p,y,_ in graded), 7)
            if count >= MIN_MATURE_GRADED_FOR_AGGREGATES else None,
        "probability_research_log_loss": round(mean(
            -(y*math.log(p)+(1-y)*math.log1p(-p)) for p,y,_ in graded), 7)
            if count >= MIN_MATURE_GRADED_FOR_AGGREGATES else None,
        "neutral_50_50_Brier_not_sportsbook": (
            .25 if count >= MIN_MATURE_GRADED_FOR_AGGREGATES else None),
        "classification_decisions_home_vs_away": len(decisions),
        "classification_accuracy_provisional": round(
            mean(int((p>.5)==bool(y)) for p,y in decisions), 6)
            if count >= MIN_MATURE_GRADED_FOR_AGGREGATES and decisions else None,
        "minimum_mature_grades_for_aggregate_skill": MIN_MATURE_GRADED_FOR_AGGREGATES,
        "meets_minimum_50_forward_graded_games": count >= MIN_MATURE_GRADED_FOR_AGGREGATES,
        "independent_publisher_or_GitHub_signatures_verified": False,
        "original_champion_001_executable_authenticated": False,
        "original_champion_001_shadows_certified": 0,
        "certified_v8_predictions": 0,
        "certified_positive_ev_bets": 0,
        "independently_verified_executable_DraftKings_odds": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "bet_ready": False,
        "archive_receipt": receipt or {},
        "warning": ("Only the FIRST archived genuine pretipoff V8 Elo research "
                    "probability per ESPN game is graded; no research probability "
                    "is backfilled from the final. Results are public ESPN scores "
                    "observed >=48h after the original start, not official league "
                    "settlement or independent model validation. No Champion-001 "
                    "certified shadows, live DraftKings odds, profitable EV or bets."),
    }
    return report, ledger


def save(report, ledger, directory):
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    (dest/"NBA_FORWARD_GRADING_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    (dest/"NBA_FORWARD_GRADING_LEDGER.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True)+"\n" for x in ledger),
        encoding="utf-8")


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archives-dir", required=True)
    p.add_argument("--output-dir", default="v8_results/nba_forward_grading")
    args=p.parse_args(argv)
    forecasts, receipt = load_archived_forecasts(args.archives_dir)
    summary, ledger = grade(forecasts, receipt=receipt)
    save(summary, ledger, args.output_dir)
    print(json.dumps({
        "archived_forward_forecasts":summary["forecast_rows_in_scope"],
        "graded":summary["real_forward_research_forecasts_graded"],
        "pending":summary["forecasts_still_pending_or_unmatched"],
        "Brier_research_only":summary["probability_research_Brier"],
        "certified_predictions":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
