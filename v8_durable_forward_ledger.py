"""Durable Git-branch SQLite ledger for genuine NBA forward *research* forecasts.

Only an already validated original GitHub Actions forecast can enter this ledger.
It always preserves the earliest archived forecast as immutable historical input,
uses a separate settled-outcome table, and quarantines contradictory identities
rather than rewriting probabilities or converting research into certified picks.

The Git branch is longer-lived than 90-day GitHub Actions artifacts, but is NOT
immutable external custody: administrators can rewrite/delete branches and
model/source signatures remain independently unauthenticated. Export data too.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
from statistics import mean
from zoneinfo import ZoneInfo

from historical_outcomes import parse_time
from v8_nba_forward_grade import (
    MAX_SOURCE_DAYS, grade as grade_forward, load_archived_forecasts,
)
from v8_forward_calibration import build_from_database as build_forward_calibration

NY = ZoneInfo("America/New_York")
DATABASE_VERSION = 1
DATA_SUBDIR = "data/v8_forward"
GRADED_STATUS = "GRADED_ESPN_PUBLISHED_FINAL_RESEARCH_ONLY"
MIN_RESEARCH_SAMPLE = 50
MAX_RAW_FILE_BYTES = 10_000_000
RAW_FILES = (
    "github_run.json",
    "ONE_COMMAND_REPORT.json",
    "nba_forward/NBA_FORWARD_FORECASTS.jsonl",
    "nba_forward/NBA_FORWARD_RESEARCH_STATUS.json",
    "nba_forward/NBA_HISTORICAL_SOURCE_COVERAGE.json",
)


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _instant(value):
    return parse_time(value)


def _init_db(db):
    db.execute("PRAGMA foreign_keys=ON")
    v = db.execute("PRAGMA user_version").fetchone()[0]
    if v not in (0, DATABASE_VERSION):
        raise ValueError("unsupported_persistent_ledger_database_version")
    status = db.execute("PRAGMA integrity_check").fetchone()[0]
    if status != "ok":
        raise ValueError("persistent_research_database_integrity_failed")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS nba_forward_forecasts (
            espn_event_id TEXT PRIMARY KEY,
            model_version TEXT NOT NULL,
            original_forecast_utc TEXT NOT NULL,
            original_tipoff_utc TEXT NOT NULL,
            home_team_espn_id TEXT NOT NULL,
            away_team_espn_id TEXT NOT NULL,
            original_p_home REAL NOT NULL CHECK(original_p_home>0 AND original_p_home<1),
            original_run_id INTEGER NOT NULL,
            original_schedule_sha256 TEXT NOT NULL,
            original_record_json TEXT NOT NULL,
            quarantined INTEGER NOT NULL DEFAULT 0 CHECK(quarantined IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS nba_published_outcomes (
            espn_event_id TEXT PRIMARY KEY REFERENCES nba_forward_forecasts(espn_event_id),
            home_won INTEGER NOT NULL CHECK(home_won IN (0,1)),
            espn_published_home_score INTEGER NOT NULL,
            espn_published_away_score INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            source_retrieved_at_utc TEXT NOT NULL,
            first_graded_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS archived_original_runs (
            original_run_id INTEGER PRIMARY KEY,
            original_files_sha256_json TEXT NOT NULL
        );
    """)
    db.execute(f"PRAGMA user_version={DATABASE_VERSION}")


def _keep_original_receipts(root, durable_root, run_ids, db):
    """Store complete relevant original receipts; reject changed original bytes."""
    copied = 0
    for run_id in sorted(run_ids):
        src = Path(root) / str(run_id)
        dest = Path(durable_root) / "original_run_receipts" / str(run_id)
        selected = list(RAW_FILES)
        selected.extend("nba_forward/" + item.name
                        for item in sorted((src / "nba_forward").glob(
                            "nba_original_future_schedule_*.json")))
        digests = {}
        for rel in selected:
            target = src / rel
            if not target.is_file():
                if rel in RAW_FILES and rel != "nba_forward/NBA_HISTORICAL_SOURCE_COVERAGE.json":
                    raise ValueError("previously_validated_archive_missing_required_original_receipt")
                continue
            if target.is_symlink() or target.stat().st_size > MAX_RAW_FILE_BYTES:
                raise ValueError("unsafe_original_receipt_size_or_link")
            data = target.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            digests[rel] = digest
            output = dest / rel
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                if output.is_symlink() or hashlib.sha256(output.read_bytes()).hexdigest() != digest:
                    raise ValueError("original_forecast_receipt_cannot_be_changed")
            else:
                output.write_bytes(data)
                copied += 1
        digest_json = _canon(digests)
        old = db.execute(
            "SELECT original_files_sha256_json FROM archived_original_runs WHERE original_run_id=?",
            (run_id,)).fetchone()
        if old is None:
            db.execute("INSERT INTO archived_original_runs VALUES (?,?)", (run_id,digest_json))
        elif old[0] != digest_json:
            raise ValueError("original_receipt_file_set_or_hash_changed")
    return copied


def _forecast_values(record):
    event = record.get("espn_event_id")
    if not isinstance(event, str) or not event.isdecimal():
        raise ValueError("invalid_original_forecast_event_id")
    now = _instant(record.get("forecast_recorded_utc"))
    start = _instant(record.get("start_utc"))
    if not now < start:
        raise ValueError("forecast_not_before_tipoff")
    p = record.get("model_probability_home_win_research_only")
    if type(p) not in (int,float) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("invalid_original_model_probability")
    source_run = record.get("github_run_id")
    if type(source_run) is not int or source_run < 1:
        raise ValueError("original_GitHub_run_identifier_required")
    return (
        event,
        record["model_version"],now.isoformat(),start.isoformat(),
        record["home_team_espn_id"],record["away_team_espn_id"],
        float(p),source_run,record["schedule_original_sha256_local_receipt"],
        _canon(record),0,
    )


def _store_forecasts(db, incoming):
    added=0
    skipped=0
    quarantined=0
    for row in incoming:
        event,version,when,start,home,away,p,source,sha,original,flag = _forecast_values(row)
        old=db.execute("""SELECT model_version,original_forecast_utc,original_tipoff_utc,
                         home_team_espn_id,away_team_espn_id,original_p_home,quarantined
                         FROM nba_forward_forecasts WHERE espn_event_id=?""",(event,)).fetchone()
        if old is None:
            db.execute("""INSERT INTO nba_forward_forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                       (event,version,when,start,home,away,p,source,sha,original,flag))
            added += 1
            continue
        original_version,original_when,original_start,original_home,original_away,original_p,already_quarantined=old
        same_game=(original_version,original_start,original_home,original_away)==(version,start,home,away)
        if not same_game or when < original_when or (when==original_when and p!=original_p):
            if not already_quarantined:
                db.execute("UPDATE nba_forward_forecasts SET quarantined=1 WHERE espn_event_id=?",(event,))
                quarantined+=1
        else:
            skipped+=1  # Later version NEVER overwrites first recorded receipt.
    return {"new_forecasts_inserted":added,"existing_or_later_forecasts_ignored":skipped,
            "new_identity_or_earliest_timestamp_conflicts_quarantined":quarantined}


def _forecasts_pending_grading(db, clock):
    rows=db.execute("""SELECT original_record_json FROM nba_forward_forecasts AS f
                       WHERE quarantined=0 AND NOT EXISTS(
                         SELECT 1 FROM nba_published_outcomes AS o
                         WHERE o.espn_event_id=f.espn_event_id)
                       ORDER BY original_tipoff_utc, espn_event_id""").fetchall()
    pending=[]
    dates=set()
    deferred=0
    for (raw,) in rows:
        forecast=json.loads(raw)
        if _instant(forecast["start_utc"])+timedelta(hours=48)>clock:
            continue
        day=_instant(forecast["start_utc"]).astimezone(NY).date()
        if day not in dates and len(dates)>=MAX_SOURCE_DAYS:
            deferred+=1
            continue
        dates.add(day)
        pending.append(forecast)
    return pending,deferred,len(dates)


def _store_grades(db, rows, clock):
    added=0
    for row in rows:
        if row.get("evaluation_status")!=GRADED_STATUS:
            continue
        result=row.get("graded_published_result")
        if not isinstance(result,dict):
            raise ValueError("graded_outcome_missing_published_evidence")
        event=row["espn_event_id"]
        if (row.get("original_forecast_modified") is not False
                or row.get("certified_prediction") is not False
                or row.get("champion_001_certified_shadow") is not False
                or row.get("verified_positive_ev") is not False):
            raise ValueError("cannot_promote_research_grades_to_certified")
        y=result.get("home_won_from_ESPN_published_final")
        home=result.get("espn_published_home_score")
        away=result.get("espn_published_away_score")
        if (type(y) is not int or y not in (0,1) or type(home) is not int
                or type(away) is not int or not 0<=home<=999 or not 0<=away<=999
                or home==away or int(home>away)!=y):
            raise ValueError("contradictory_published_final")
        db.execute("""INSERT INTO nba_published_outcomes VALUES (?,?,?,?,?,?,?)""",
                   (event,y,home,away,result["outcome_source_url"],
                    result["outcome_retrieved_at_utc"],clock.isoformat()))
        added+=1
    return added


def _scoreboard(db,clock, source_receipt, sync_counts, grade_summary, deferred):
    all_rows = db.execute("""SELECT f.espn_event_id,f.model_version,f.original_forecast_utc,
               f.original_tipoff_utc,f.original_p_home,f.original_run_id,f.original_record_json,
               f.quarantined,o.home_won,o.espn_published_home_score,
               o.espn_published_away_score,o.source_url,o.source_retrieved_at_utc
               FROM nba_forward_forecasts AS f LEFT JOIN nba_published_outcomes AS o
               ON f.espn_event_id=o.espn_event_id
               ORDER BY f.original_tipoff_utc, f.espn_event_id""").fetchall()
    model_data=defaultdict(list)
    pending_maturity=0
    due_ungraded=0
    quarantined=0
    history=[]
    for eid,model,forecasted,started,p,runid,raw,quarantine,y,hscore,ascore,url,retrieved in all_rows:
        if quarantine:
            status="QUARANTINED_CONFLICT_NOT_GRADED"
            quarantined+=1
        elif y is None and _instant(started)+timedelta(hours=48)>clock:
            status="PENDING_48H_RESULT_MATURITY"
            pending_maturity+=1
        elif y is None:
            status="HOLD_NO_GRADED_PUBLISHED_RESULT"
            due_ungraded+=1
        else:
            status=GRADED_STATUS
            model_data[model].append((p,y,started))
        record=json.loads(raw)
        history.append({
            "sport":"nba", "espn_event_id":eid,
            "model_version":model,"original_forecast_utc":forecasted,
            "original_tipoff_utc":started,"original_GitHub_run_id":runid,
            "original_home_team":record.get("home_team"),
            "original_away_team":record.get("away_team"),
            "original_model_home_win_probability":p,
            "grade_status":status,
            "home_won_published_final_research_only":y,
            "home_score_published":hscore,
            "away_score_published":ascore,
            "published_final_source_url":url,
            "published_final_observed_utc":retrieved,
            "certified_champion_001_shadow":False,
            "certified_prediction":False,"positive_ev_certified":False,
            "wager_stake_usd":0,
        })
    models=[]
    for version, vals in sorted(model_data.items()):
        scored=len(vals)
        direction=[(p,y) for p,y,_ in vals if p!=.5]
        brier=mean((p-y)**2 for p,y,_ in vals)
        logloss=mean(-(y*math.log(p)+(1-y)*math.log1p(-p)) for p,y,_ in vals)
        models.append({
            "model_version":version,
            "sport":"nba",
            "graded_forward_research_games":scored,
            "mean_Brier_lower_is_better":round(brier,8),
            "mean_log_loss_lower_is_better":round(logloss,8),
            "neutral_half_Brier_not_sportsbook":.25,
            "home_vs_away_classification_accuracy":(
                round(mean(int((p>.5)==bool(y)) for p,y in direction),6)
                if direction else None),
            "win_direction_decisions":len(direction),
            "ranking_eligible":scored>=MIN_RESEARCH_SAMPLE,
            "research_only_not_certified":True,
            "positive_ev_certified":0,
        })
    leaderboard=[dict(x) for x in sorted(
        (m for m in models if m["ranking_eligible"]),
        key=lambda m:(m["mean_Brier_lower_is_better"],-m["graded_forward_research_games"]))]
    total_scored=sum(len(v) for v in model_data.values())
    board={
        "version":"v8-durable-forward-NBA-research-scoreboard-v1",
        "generated_at_utc":clock.isoformat(),
        "persistent_store":"GitHub branch research/forward-ledger data/v8_forward",
        "database_is_externally_immutable_or_audited":False,
        "nba_unique_original_forecasts_archived":len(all_rows),
        "nba_original_forecasts_quarantined":quarantined,
        "nba_forecasts_pending_48h":pending_maturity,
        "nba_forecasts_due_without_published_grade":due_ungraded,
        "nba_forward_forecasts_graded_research_only":total_scored,
        "nba_graded_minimum_required_for_research_ranking":MIN_RESEARCH_SAMPLE,
        "ranking_status":(
            "PROVISIONAL_RESEARCH_RANKING_NOT_CERTIFIED" if leaderboard
            else "NO_MODEL_WITH_50_AUTHENTIC_FORWARD_GRADED_GAMES"),
        "research_model_scorecards_including_small_samples":models,
        "research_only_ranked_models":leaderboard,
        "new_forecast_sync":sync_counts,
        "last_graded_batch":grade_summary,
        "matured_ungraded_source_dates_deferred_due_to_budget":deferred,
        "raw_archive_receipt":source_receipt,
        "certified_champion_001_shadows":0,
        "certified_v8_probabilities":0,
        "certified_positive_ev_bets":0,
        "independently_verified_checkout_odds":0,
        "automatic_real_money_wagers":0,
        "champion_001_modified":False,
        "bet_ready":False,
        "warning":(
            "Long-lived Git-branch SQLite/JSONL storage is not immutable custody. "
            "Only original validated GH action V8 forward research receipts are stored; "
            "ESPn published finals are provisional, not independent league settlement. "
            "No authentic Champion-001 executable, independent probability validation, "
            "verified sportsbook price or betting edge is established."),
    }
    return board,history


def sync(incoming_root, output_dir, *, now=None, collector=None):
    """Persist validated new pregame records and separately grade mature outcomes."""
    clock=now or datetime.now(timezone.utc)
    if not isinstance(clock,datetime) or clock.tzinfo is None:
        raise ValueError("aware_clock_required")
    clock=clock.astimezone(timezone.utc)
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=True)
    incoming, receipt=load_archived_forecasts(incoming_root)
    db_path=root/"NBA_FORWARD_RESEARCH.sqlite"
    with sqlite3.connect(db_path) as db:
        _init_db(db)
        copied=_keep_original_receipts(incoming_root,root,
                                       receipt["source_github_run_ids"],db)
        sync_counts=_store_forecasts(db,incoming)
        to_grade,deferred,days=_forecasts_pending_grading(db,clock)
        if len(to_grade)>2000:
            raise ValueError("too_many_pending_forecasts_for_one_grading_batch")
        # In a LIVE pipeline, the source receipt is stamped after the ESPN
        # HTTP response. Passing the scan-start clock as a historical as_of
        # causes the genuine post-fetch timestamp to be rejected as future
        # data. Retrospective/test calls with an explicit now must keep their
        # strict historical cutoff; only real-clock calls use live mode.
        grading_as_of = clock if now is not None else None
        grade_summary,ledger=grade_forward(
            to_grade,as_of=grading_as_of,collector=collector)
        if now is None:
            completed_at = datetime.now(timezone.utc)
            if completed_at < clock:
                raise ValueError("live_grading_clock_moved_backwards")
            clock = completed_at
        added_grades=_store_grades(db,ledger,clock)
        sync_counts["original_receipt_files_added"]=copied
        sync_counts["new_ESPN_published_outcomes_recorded"]=added_grades
        sync_counts["mature_outcome_source_days_checked"]=days
        board,history=_scoreboard(db,clock,receipt,sync_counts,grade_summary,deferred)
        db.commit()
    calibration = build_forward_calibration(
        db_path, root / "CALIBRATION.json")
    board["forward_calibration_report_version"] = calibration["version"]
    board["forward_calibration_status"] = calibration["status"]
    board["forward_calibration_graded_NBA_games"] = calibration["graded_research_NBA_games"]
    if board["forward_calibration_graded_NBA_games"] != board["nba_forward_forecasts_graded_research_only"]:
        raise ValueError("calibration_and_original_ledger_grades_do_not_reconcile")
    (root/"LEADERBOARD.json").write_text(
        json.dumps(board,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (root/"FORECAST_HISTORY.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in history),
        encoding="utf-8")
    return board,history


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--incoming-archives",required=True)
    p.add_argument("--output-dir",default=DATA_SUBDIR)
    args=p.parse_args(argv)
    board,history=sync(args.incoming_archives,args.output_dir)
    print(json.dumps({
        "archived_original_forecasts":board["nba_unique_original_forecasts_archived"],
        "forward_research_games_graded":board["nba_forward_forecasts_graded_research_only"],
        "pending_under_48h":board["nba_forecasts_pending_48h"],
        "due_without_published_grade":board["nba_forecasts_due_without_published_grade"],
        "new_forecasts":board["new_forecast_sync"]["new_forecasts_inserted"],
        "new_grades":board["new_forecast_sync"]["new_ESPN_published_outcomes_recorded"],
        "ranked_eligible_research_models":len(board["research_only_ranked_models"]),
        "forward_calibration_status":board["forward_calibration_status"],
        "champion_001_certified_shadows":0,"certified_positive_EV_bets":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
