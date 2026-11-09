"""Verify and grade original NFL/NHL V8 *research* probability receipts.

Only completed GitHub run metadata plus saved byte-for-byte original ESPN
future schedules qualify as an authentic pre-start local research record.
The first qualified probability per exact game ID is frozen; later copies
cannot rewrite it. A 48h minimum elapsed since the originally scheduled
kickoff/puck drop precedes result retrieval.

NFL forecasts are CONDITIONAL ON NO TIE, NOT two-way market moneylines:
published ties are excluded from binary grading, not treated as losses.
NHL results include published postgame winner but exact OT/shootout
bookmaker market settlement is NOT verified. All output research-only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from challenger_elo_walkforward import validate_game
from historical_outcomes import collect as collect_scores, parse_time, scoreboard_url
from v8_nfl_nhl_forward import SPEC, parse_original_future_schedule

NY = ZoneInfo("America/New_York")
MIN_RESULT_DELAY_HOURS = 48
MAX_RUNS = 35
MAX_FORECASTS = 2000
MAX_GRADING_DAYS = 35
MAX_FILE_BYTES = 10_000_000
GRADED = "GRADED_ESPN_PUBLISHED_RESEARCH_ONLY"
NFL_TIE = "EXCLUDED_NFL_PUBLISHED_TIE_CONDITIONAL_BINARY_TARGET"


def read_file(path, *, json_lines=False):
    path=Path(path)
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > MAX_FILE_BYTES):
        raise ValueError("missing_unsafe_or_oversized_forecast_source")
    data=path.read_bytes()
    if json_lines:
        return [json.loads(x) for x in data.splitlines() if x.strip()]
    return json.loads(data)


def _validated_run(root, league, run_id):
    parent=Path(root)/league/str(run_id)
    metadata=read_file(parent/"github_run.json")
    saved=read_file(parent/(league.upper()+"_FORWARD_RESEARCH_STATUS.json"))
    forecasts=read_file(parent/(league.upper()+"_FORWARD_RESEARCH_FORECASTS.jsonl"),
                        json_lines=True)
    if (metadata.get("id")!=run_id or metadata.get("head_branch")!="main"
            or metadata.get("status")!="completed" or metadata.get("conclusion")!="success"
            or metadata.get("event") not in ("push","schedule","workflow_dispatch")
            or saved.get("stage")!="v8_nfl_nhl_forward_original_source_research_only"
            or saved.get("league")!=league
            or saved.get("model_version")!=SPEC[league]["version"]
            or saved.get("forecast_probabilities_recorded_before_start")!=len(forecasts)
            or saved.get("original_champion_001_certified_predictions")!=0
            or saved.get("certified_v8_predictions")!=0
            or saved.get("certified_positive_ev_bets")!=0
            or saved.get("champion_001_modified") is not False
            or saved.get("bet_ready") is not False):
        raise ValueError("incorrect_or_promoted_original_forward_run")
    created=parse_time(metadata.get("created_at"))
    finished=parse_time(metadata.get("updated_at"))
    recorded=parse_time(saved.get("recorded_at_utc"))
    if not created<=recorded<=finished:
        raise ValueError("original_forecast_clock_outside_completed_GitHub_run")
    if len(forecasts)>MAX_FORECASTS:
        raise ValueError("unsafe_forecast_row_count")
    raw_by_day={}
    seen=set()
    accepted=[]
    for x in forecasts:
        if (not isinstance(x,dict)
                or x.get("record_type")!="v8_genuine_forward_clocktime_multisport_Elo_research_only"
                or x.get("league")!=league
                or x.get("model_version")!=SPEC[league]["version"]
                or x.get("champion_001_modified") is not False
                or x.get("qualified_for_certified_champion_001_shadow") is not False
                or x.get("model_independently_calibrated") is not False
                or x.get("bookmaker_checkout_price_verified") is not False
                or x.get("certified_prediction") is not False
                or x.get("positive_ev_bet") is not False
                or x.get("bet_ready") is not False or x.get("stake_usd") !=0
                or x.get("future_outcome") is not None
                or x.get("published_final_observed_at_utc") is not None
                or x.get("original_prediction_recorded_before_tipoff") is not True):
            raise ValueError("untrusted_or_relabelled_original_research_prediction")
        if x.get("model_target")!=(
                "NFL_home_vs_away_given_no_tie_NOT_a_market_moneyline"
                if league=="nfl" else
                "NHL_fullgame_published_winner_including_OT_SO_not_market_verified"):
            raise ValueError("invalid_model_target_or_market_mislabel")
        eid=x.get("espn_event_id")
        if type(eid) is not str or not eid.isdecimal() or eid in seen:
            raise ValueError("duplicate_or_invalid_forward_game_id")
        seen.add(eid)
        observed=parse_time(x.get("schedule_original_received_at_utc"))
        timestamp=parse_time(x.get("forecast_recorded_utc"))
        start=parse_time(x.get("start_utc"))
        # Completed GitHub run must also precede start; fail closed if not.
        if not created<=observed<=timestamp==recorded<=finished<start:
            raise ValueError("original_forecast_not_provably_recorded_before_start")
        prob=x.get("model_probability_home_win_research_only")
        away=x.get("model_probability_away_win_research_only")
        if (type(prob) not in (float,int) or type(away) not in (float,int)
                or not math.isfinite(prob) or not math.isfinite(away)
                or not 0<prob<1 or abs(prob+away-1)>0.0000011):
            raise ValueError("invalid_conditional_research_probability")
        date_et=start.astimezone(NY).date()
        day=date_et.strftime("%Y%m%d")
        source=parent/(league+"_original_future_schedule_"+day+".json")
        if day not in raw_by_day:
            raw=source.read_bytes() if source.is_file() and not source.is_symlink() and source.stat().st_size<MAX_FILE_BYTES else b""
            if not raw:
                raise ValueError("original_future_ESPN_source_bytes_missing")
            parsed=json.loads(raw)
            items=parse_original_future_schedule(league,parsed,raw,date_et,observed)
            raw_by_day[day]=(raw,items)
        raw,items=raw_by_day[day]
        if (x.get("schedule_source_url")!=scoreboard_url(league,date_et)
                or x.get("schedule_original_sha256_local_receipt")!=hashlib.sha256(raw).hexdigest()):
            raise ValueError("original_ESPN_source_hash_or_url_mismatch")
        match=[g for g in items if g["espn_event_id"]==eid]
        if len(match)!=1 or any(x.get(k)!=match[0][k] for k in
                                    ("start_utc","home_team_espn_id","away_team_espn_id")):
            raise ValueError("original_schedule_event_identity_drift")
        accepted.append(dict(x,github_run_id=run_id,
                             github_run_created_at_utc=created.isoformat(),
                             github_run_completed_at_utc=finished.isoformat()))
    return accepted


def load_archives(root, league):
    if league not in SPEC:
        raise ValueError("unsupported_multisport_forward_league")
    folder=Path(root)/league
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("original_GitHub_forecast_archive_directory_required")
    paths=[p for p in folder.iterdir() if p.is_dir() and p.name.isdecimal() and not p.is_symlink()]
    if len(paths)>MAX_RUNS:
        raise ValueError("original_archive_run_budget_exceeded")
    found=[]; valid_runs=[]; exclusions=Counter()
    for path in sorted(paths,key=lambda p:int(p.name)):
        try:
            rows=_validated_run(root,league,int(path.name))
        except (ValueError,KeyError,TypeError,UnicodeDecodeError,json.JSONDecodeError) as exc:
            exclusions["unsafe_source_run_"+type(exc).__name__]+=1
            continue
        found.extend(rows)
        valid_runs.append(int(path.name))
    if len(found)>MAX_FORECASTS:
        raise ValueError("total_forward_archived_forecast_budget_exceeded")
    by_id={}; conflicted=set()
    for row in sorted(found,key=lambda r:(r["forecast_recorded_utc"],r["github_run_id"])):
        eid=row["espn_event_id"]
        if eid in conflicted:
            continue
        old=by_id.get(eid)
        if old is None:
            by_id[eid]=row
            continue
        match=all(old[k]==row[k] for k in (
            "model_version","start_utc","home_team_espn_id","away_team_espn_id"))
        if not match or (old["forecast_recorded_utc"]==row["forecast_recorded_utc"]
                        and old["model_probability_home_win_research_only"]!=
                            row["model_probability_home_win_research_only"]):
            by_id.pop(eid)
            conflicted.add(eid)
            exclusions["conflicting_game_identity_quarantined"]+=1
        else:
            exclusions["later_forecast_ignored"]+=1
    return sorted(by_id.values(),key=lambda r:(r["start_utc"],r["espn_event_id"])),{
        "league":league,"original_completed_github_run_ids":valid_runs,
        "source_forward_rows_loaded":len(found),
        "first_unique_event_forecasts_accepted":len(by_id),
        "source_exclusions":dict(sorted(exclusions.items())),
        "independently_certified_predictions":0,
    }


def grade(league, forecasts, *, now=None, collector=None, source_receipt=None):
    if league not in SPEC or not isinstance(forecasts,list):
        raise ValueError("league_and_original_forecasts_required")
    current=now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current,datetime) or current.tzinfo is None:
        raise ValueError("timezone_aware_grading_clock_required")
    current=current.astimezone(timezone.utc)
    if len(forecasts)>MAX_FORECASTS or len({
        x.get("espn_event_id") for x in forecasts
    })!=len(forecasts):
        raise ValueError("duplicate_or_oversized_forward_grading_input")
    collector=collector or collect_scores
    mature_dates=sorted({
        parse_time(f["start_utc"]).astimezone(NY).date() for f in forecasts
        if parse_time(f["start_utc"])+timedelta(hours=MIN_RESULT_DELAY_HOURS)<=current
    })
    if len(mature_dates)>MAX_GRADING_DAYS:
        raise ValueError("graded_source_dates_exceed_bounded_window")
    by_id={}; coverage={}
    for day in mature_dates:
        rows,meta=collector((league,),1,day)
        stat=meta.get("by_league",{}).get(league,{}) if isinstance(meta,dict) else {}
        success=(
            isinstance(rows,list) and meta.get("leagues")==[league]
            and meta.get("champion_001_modified") is False
            and meta.get("total_completed_results")==len(rows)
            and stat.get("days_attempted")==1 and stat.get("days_ok")==1
            and stat.get("days_failed")==0
        )
        coverage[day]=success
        if not success:continue
        for result in rows:
            lg,started,eid,home,away,y=validate_game(result)
            if (lg!=league or result.get("season_type")!=2
                    or result.get("source_url")!=scoreboard_url(league,day)
                    or started.astimezone(NY).date()!=day
                    or parse_time(result.get("retrieved_at_utc"))>current):
                raise ValueError("published_score_is_not_verified_source_shape")
            if eid in by_id:
                raise ValueError("duplicated_ESPN_final_event")
            by_id[eid]=(result,started,home,away,y)
    rows=[]; graded=[]; states=Counter()
    for f in sorted(forecasts,key=lambda x:(x["start_utc"],x["espn_event_id"])):
        scheduled=parse_time(f["start_utc"])
        event=f["espn_event_id"]
        day=scheduled.astimezone(NY).date()
        status="PENDING_48H_POST_START_MATURITY"
        published=None
        if scheduled+timedelta(hours=MIN_RESULT_DELAY_HOURS)<=current:
            if not coverage.get(day):
                status="HOLD_ESPN_SOURCE_DAY_UNAVAILABLE"
            elif event not in by_id:
                status="HOLD_NO_PUBLISHED_COMPLETED_EVENT"
            else:
                score,realstart,home,away,y=by_id[event]
                if (home!=f["home_team_espn_id"] or away!=f["away_team_espn_id"]
                        or realstart<=parse_time(f["forecast_recorded_utc"])
                        or abs((realstart-scheduled).total_seconds())>3600):
                    status="HOLD_CHANGED_EVENT_OR_TEAM_IDENTITY"
                elif y is None:
                    status=(NFL_TIE if league=="nfl"
                            else "HOLD_NHL_TIED_PUBLISHED_FINAL_NO_VERIFIED_WINNER")
                else:
                    status=GRADED
                    p=f["model_probability_home_win_research_only"]
                    published={
                        "ESPN_published_home_won":y,
                        "home_final_score_research":score["home_score"],
                        "away_final_score_research":score["away_score"],
                        "source_url":score["source_url"],
                        "source_retrieved_at_utc":score["retrieved_at_utc"],
                        "Brier_research":round((p-y)**2,9),
                        "log_loss_research":round(
                            -(y*math.log(p)+(1-y)*math.log1p(-p)),9),
                        "correct_more_likely_side": (
                            None if p==.5 else int(p>.5)==y),
                    }
                    graded.append((p,y))
        states[status]+=1
        rows.append({
            "sport":league,"espn_event_id":event,"model_version":f["model_version"],
            "first_original_github_run_id":f["github_run_id"],
            "original_forecast_utc":f["forecast_recorded_utc"],
            "original_scheduled_start_utc":f["start_utc"],
            "original_p_home_research":f["model_probability_home_win_research_only"],
            "grade_status":status,"published_result_research_only":published,
            "NFL_tie_excluded_from_binary_grading":status==NFL_TIE,
            "original_prediction_changed":False,
            "certified_champion_shadow":False,"positive_ev_certified":False,
            "bet_ready":False,"stake_usd":0,
        })
    count=len(graded)
    decisions=[(p,y) for p,y in graded if p!=.5]
    return {
        "version":"v8-nfl-nhl-forward-grade-v1","league":league,
        "graded_asof_utc":current.isoformat(),
        "original_forward_forecasts_in_scope":len(forecasts),
        "actual_ESPN_published_grades":count,
        "still_pending_or_on_hold":len(forecasts)-count,
        "state_counts":dict(sorted(states.items())),
        "NFL_ties_excluded_from_conditional_binary_target":states[NFL_TIE],
        "research_Brier":round(mean((p-y)**2 for p,y in graded),8) if count>=50 else None,
        "research_log_loss":round(mean(
            -(y*math.log(p)+(1-y)*math.log1p(-p)) for p,y in graded),8) if count>=50 else None,
        "win_direction_accuracy":round(mean(
            int((p>.5)==bool(y)) for p,y in decisions),6)
            if len(decisions)>=50 else None,
        "minimum_forward_binary_grades_for_research_summary":50,
        "original_model_independently_authenticated":False,
        "published_ESPN_is_official_sportsbook_settlement":False,
        "real_executable_DraftKings_checkout_quotes":0,
        "certified_champion_001_shadows":0,
        "certified_positive_ev_bets":0,"automated_wagers":0,
        "champion_001_modified":False,"bet_ready":False,
        "source_archive_receipt":source_receipt or {},
        "warning":(
            "Only first original pregame research probabilities are scored "
            "against ESPN-published finals >=48h later; NFL ties are excluded "
            "from non-tie binary research target. NHL games include published "
            "OT/SO winner but exact sportsbook settlement unverified. "
            "Brier/logloss withheld below 50 forward-graded binary games. "
            "No verified Champion-001 predictions, bookmaker prices, +EV or bets."),
    },rows


def write_report(report,ledger,destination):
    dest=Path(destination)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"FORWARD_GRADE_REPORT.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (dest/"FORWARD_GRADE_LEDGER.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in ledger),encoding="utf-8")


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--league",required=True,choices=sorted(SPEC))
    p.add_argument("--archives",required=True)
    p.add_argument("--output-dir",default="v8_results/sport_grade")
    args=p.parse_args()
    rows,receipt=load_archives(args.archives,args.league)
    result,ledger=grade(args.league,rows,source_receipt=receipt)
    write_report(result,ledger,args.output_dir)
    print(json.dumps({
        "league":args.league,"original_forward_forecasts":len(rows),
        "graded_binary_games":result["actual_ESPN_published_grades"],
        "NFL_ties_excluded":result["NFL_ties_excluded_from_conditional_binary_target"],
        "certified_positive_ev_bets":0,
    },sort_keys=True))
