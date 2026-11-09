"""Long-lived Git-branch SQLite archives for NFL/NHL actual forward research.

Sports are independent SQLite databases on research/nfl-nhl-forward-ledger.
Original future ESPN bytes, run metadata and earliest probability are copied
without overwrite. Results live in a separate table; NFL ties receive an
excluded research grade status (not a loss). Research leaderboard withholds
Brier/log-loss under 50 eligible forward games per sport/model.

Git branches are NOT immutable external custody, SHA256 local hashes are
NOT ESPN publisher signatures, ESPN finals are NOT bookmaker settlement.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean

from historical_outcomes import parse_time
from v8_nfl_nhl_forward import SPEC
from v8_nfl_nhl_forward_grade import (
    GRADED, NFL_TIE, MAX_GRADING_DAYS, grade, load_archives,
)

MIN_RESEARCH_GAMES = 50


def _dumps(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def _db_init(con):
    con.execute("PRAGMA foreign_keys=ON")
    version=con.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0,1) or con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        raise ValueError("invalid_existing_NFL_NHL_research_database")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS first_forecasts (
            event_id TEXT PRIMARY KEY,
            model_version TEXT NOT NULL,
            first_recorded_utc TEXT NOT NULL,
            start_utc TEXT NOT NULL,
            home_id TEXT NOT NULL,
            away_id TEXT NOT NULL,
            probability_home REAL NOT NULL CHECK(probability_home>0 AND probability_home<1),
            original_run_id INTEGER NOT NULL,
            original_json TEXT NOT NULL,
            quarantined INTEGER NOT NULL DEFAULT 0 CHECK(quarantined IN(0,1))
        );
        CREATE TABLE IF NOT EXISTS observed_outcomes (
            event_id TEXT PRIMARY KEY REFERENCES first_forecasts(event_id),
            state TEXT NOT NULL,
            home_won INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            url TEXT,
            published_observed_utc TEXT,
            grade_recorded_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS original_run_files (
            original_run_id INTEGER PRIMARY KEY,
            sha256_by_original_file_json TEXT NOT NULL
        );
    """)
    con.execute("PRAGMA user_version=1")


def _save_original_sources(parent, incoming, league, run_ids, db):
    added=0
    for rid in sorted(run_ids):
        src=Path(incoming)/league/str(rid)
        target=Path(parent)/"original_source_receipts"/str(rid)
        selected=[
            "github_run.json",
            league.upper()+"_FORWARD_RESEARCH_FORECASTS.jsonl",
            league.upper()+"_FORWARD_RESEARCH_STATUS.json",
            league.upper()+"_PUBLISHED_HISTORY_COVERAGE.json",
        ]
        selected.extend(p.name for p in sorted(src.glob(league+"_original_future_schedule_*.json")))
        hashes={}
        for name in selected:
            input=src/name
            if (not input.is_file() or input.is_symlink()
                    or input.stat().st_size>10_000_000):
                raise ValueError("original_completed_forecast_run_files_unavailable")
            blob=input.read_bytes()
            digest=hashlib.sha256(blob).hexdigest()
            hashes[name]=digest
            path=target/name
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise ValueError("source_original_forecast_receipt_changed")
            else:
                path.write_bytes(blob)
                added+=1
        marker=_dumps(hashes)
        old=db.execute(
            "SELECT sha256_by_original_file_json FROM original_run_files WHERE original_run_id=?",
            (rid,)).fetchone()
        if old is None:
            db.execute("INSERT INTO original_run_files VALUES (?,?)",(rid,marker))
        elif old[0]!=marker:
            raise ValueError("original_run_file_manifest_changed")
    return added


def _record_original_forecasts(db, records):
    added=duplicates=conflicts=0
    for forecast in records:
        eid=forecast["espn_event_id"]
        started=parse_time(forecast["start_utc"]).isoformat()
        timestamp=parse_time(forecast["forecast_recorded_utc"]).isoformat()
        fields=(
            forecast["model_version"],started,
            forecast["home_team_espn_id"],forecast["away_team_espn_id"])
        original=db.execute("""
            SELECT model_version,start_utc,home_id,away_id,
                   first_recorded_utc,probability_home,quarantined
            FROM first_forecasts WHERE event_id=?""",(eid,)).fetchone()
        p=forecast["model_probability_home_win_research_only"]
        if original is None:
            db.execute("INSERT INTO first_forecasts VALUES (?,?,?,?,?,?,?,?,?,?)",(
                eid,forecast["model_version"],timestamp,started,
                forecast["home_team_espn_id"],forecast["away_team_espn_id"],
                p,forecast["github_run_id"],_dumps(forecast),0))
            added+=1
        else:
            version,t,home,away,prior_stamp,prior_p,quarantined=original
            changed=(fields!=(version,t,home,away) or timestamp<prior_stamp
                     or (timestamp==prior_stamp and p!=prior_p))
            if changed and not quarantined:
                db.execute("UPDATE first_forecasts SET quarantined=1 WHERE event_id=?",(eid,))
                conflicts+=1
            elif not changed:
                duplicates+=1
    return {"new_original_forecasts":added,
            "later_repeated_forecasts_ignored":duplicates,
            "new_conflicting_event_ids_quarantined":conflicts}


def _due_forecasts(db, now):
    rows=db.execute("""SELECT original_json FROM first_forecasts AS f
        WHERE quarantined=0 AND NOT EXISTS(
            SELECT 1 FROM observed_outcomes AS o WHERE o.event_id=f.event_id)
        ORDER BY start_utc,event_id""").fetchall()
    pending=[]; days=set(); deferred=0
    for (raw,) in rows:
        f=json.loads(raw)
        start=parse_time(f["start_utc"])
        if start+timedelta(hours=48)>now:
            continue
        date=start.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
        if date not in days and len(days)>=MAX_GRADING_DAYS:
            deferred+=1
            continue
        days.add(date)
        pending.append(f)
    return pending,deferred


def _record_outcomes(db, ledger, now):
    count=excluded=0
    for row in ledger:
        status=row["grade_status"]
        if status not in (GRADED,NFL_TIE):
            continue
        if (row["original_prediction_changed"] is not False
                or row["certified_champion_shadow"] is not False
                or row["positive_ev_certified"] is not False):
            raise ValueError("research_grading_must_not_be_promoted_to_certified")
        final=row["published_result_research_only"]
        if status==GRADED:
            if not isinstance(final,dict):
                raise ValueError("qualified_grade_missing_separate_ESPN_evidence")
            y=final["ESPN_published_home_won"]
            home=final["home_final_score_research"]
            away=final["away_final_score_research"]
            if (type(y) is not int or y not in (0,1)
                    or type(home) is not int or type(away) is not int
                    or home==away or int(home>away)!=y):
                raise ValueError("invalid_binary_research_published_final")
            url=final["source_url"]
            observed=final["source_retrieved_at_utc"]
            count+=1
        else:
            # An NFL tie is excluded from a conditional NON-TIE forecast;
            # it never increments numerator/denominator of binary accuracy.
            y=home=away=url=observed=None
            excluded+=1
        db.execute("""INSERT INTO observed_outcomes
            VALUES (?,?,?,?,?,?,?,?)""",(
            row["espn_event_id"],status,y,home,away,url,observed,
            now.isoformat()))
    return {"new_ESPN_binary_research_outcomes":count,
            "new_NFL_ties_excluded_from_binary_grading":excluded}


def _scoreboard(db,league,clock,changes,deferred,receipts):
    history=[]; metrics=defaultdict(list); counts=Counter()
    pairs=db.execute("""SELECT f.event_id,f.model_version,f.first_recorded_utc,
        f.start_utc,f.probability_home,f.original_run_id,f.original_json,
        f.quarantined,o.state,o.home_won,o.home_score,o.away_score,
        o.url,o.published_observed_utc
        FROM first_forecasts AS f LEFT JOIN observed_outcomes AS o
        ON f.event_id=o.event_id ORDER BY f.start_utc,f.event_id""").fetchall()
    for (eid,model,forecasted,start,p,runid,raw,quarantined,
         resolved,y,home_score,away_score,url,observed) in pairs:
        if quarantined:
            status="QUARANTINED_CONFLICTING_ID"
        elif resolved is not None:
            status=resolved
        elif parse_time(start)+timedelta(hours=48)>clock:
            status="PENDING_48H_POST_START_MATURITY"
        else:
            status="HOLD_WAITING_FOR_VERIFIED_PUBLISHED_RESULT"
        counts[status]+=1
        if status==GRADED:
            metrics[model].append((p,y))
        old=json.loads(raw)
        history.append({
            "sport":league,"espn_event_id":eid,"model_version":model,
            "original_recorded_utc":forecasted,"first_source_run_id":runid,
            "original_game_start_utc":start,"original_probability_home_research_only":p,
            "home_team":old.get("home_team"),"away_team":old.get("away_team"),
            "status":status,"ESPN_published_home_won_research":y,
            "ESPN_published_home_final":home_score,
            "ESPN_published_away_final":away_score,
            "published_source_url":url,"published_received_utc":observed,
            "certified_champion_001_prediction":False,"certified_positive_EV":False,
            "stake_usd":0,
        })
    models=[]
    for model,values in sorted(metrics.items()):
        n=len(values)
        eligible=n>=MIN_RESEARCH_GAMES
        decision=[(p,y) for p,y in values if p!=.5]
        models.append({
            "model":model,"league":league,
            "original_forward_ESPN_games_graded":n,
            "research_Brier":round(mean((p-y)**2 for p,y in values),8) if eligible else None,
            "research_log_loss":round(mean(
                -(y*math.log(p)+(1-y)*math.log1p(-p)) for p,y in values),8) if eligible else None,
            "research_direction_accuracy":round(mean(
                int((p>.5)==bool(y)) for p,y in decision),6)
                if eligible and decision else None,
            "rank_eligible_after_50":eligible,
            "model_independently_calibrated":False,"market_betting_ready":False,
        })
    ranked=sorted((x for x in models if x["rank_eligible_after_50"]),
                  key=lambda x:(x["research_Brier"],-x["original_forward_ESPN_games_graded"]))
    return {
        "version":"v8-NFL-NHL-durable-forward-v1",
        "sport":league,"generated_at_utc":clock.isoformat(),
        "original_saved_forecasts":len(pairs),
        "original_game_identity_conflicts_quarantined":counts["QUARANTINED_CONFLICTING_ID"],
        "pending_48h":counts["PENDING_48H_POST_START_MATURITY"],
        "unmatched_or_source_missing":counts["HOLD_WAITING_FOR_VERIFIED_PUBLISHED_RESULT"],
        "graded_research_games":counts[GRADED],
        "published_NFL_ties_excluded":counts[NFL_TIE] if league=="nfl" else 0,
        "research_model_scorecards_including_insufficient_samples":models,
        "research_ranked_models_after_50":ranked,
        "status":("PROVISIONAL_FORWARD_RESEARCH_RANKING_NOT_BETTING_CERTIFIED"
                  if ranked else "HOLD_Fewer_than_50_research_forward_grades_per_model"),
        "last_synchronization":changes,
        "matured_date_queries_deferred_due_to_budget":deferred,
        "source_research_receipts":receipts,
        "branch_durable_but_independently_tamperproof":False,
        "ESPN_final_is_independently_verified_bookmaker_settlement":False,
        "certified_champion_001_shadows":0,
        "verified_sportsbook_checkout_quotes":0,
        "certified_positive_ev_bets":0,"automated_wagers":0,
        "champion_001_modified":False,"bet_ready":False,
        "warning":(
            "Original V8 research forecasts were saved before start, but "
            "Git branch and local SHA256 are not external signatures. "
            "NFL ties are excluded from conditional non-tie binary forecasts. "
            "NHL OT/SO sportsbook market grading unaudited. "
            "50 published-forward non-tie games only unlock provisional "
            "research metrics; no calibrated betting model, odds or profit claims."),
    },history


def sync(league, incoming_archives, directory, *, now=None, collector=None):
    if league not in SPEC:
        raise ValueError("unsupported_saved_forward_league")
    clock=now or datetime.now(timezone.utc)
    if not isinstance(clock,datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_archive_clock_required")
    clock=clock.astimezone(timezone.utc)
    folder=Path(directory)
    folder.mkdir(parents=True,exist_ok=True)
    new,receipts=load_archives(incoming_archives,league)
    dbfile=folder/"FIRST_FORECASTS.sqlite"
    with sqlite3.connect(dbfile) as db:
        _db_init(db)
        receipts_added=_save_original_sources(
            folder,incoming_archives,league,receipts["original_completed_github_run_ids"],db)
        changes=_record_original_forecasts(db,new)
        due,deferred=_due_forecasts(db,clock)
        graded,grades=grade(league,due,now=clock,collector=collector)
        changes.update(_record_outcomes(db,grades,clock))
        changes["original_source_receipt_files_saved"]=receipts_added
        changes["due_forecast_rows_checked"]=len(due)
        report,history=_scoreboard(db,league,clock,changes,deferred,receipts)
        db.commit()
    (folder/"FORWARD_RESEARCH_LEADERBOARD.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (folder/"FIRST_FORECAST_HISTORY.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in history),encoding="utf-8")
    return report,history


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--league",required=True,choices=sorted(SPEC))
    p.add_argument("--incoming-archives",required=True)
    p.add_argument("--output-dir",required=True)
    args=p.parse_args()
    result,rows=sync(args.league,args.incoming_archives,args.output_dir)
    print(json.dumps({
        "sport":result["sport"],"original_forecasts":result["original_saved_forecasts"],
        "forward_binary_games_graded":result["graded_research_games"],
        "NFL_ties_excluded":result["published_NFL_ties_excluded"],
        "not_yet_mature":result["pending_48h"],
        "certified_predictions":0,"certified_positive_EV_bets":0,
    },sort_keys=True))
