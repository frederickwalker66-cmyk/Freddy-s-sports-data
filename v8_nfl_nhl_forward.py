"""NFL and NHL genuine clock-time V8 forward research probability receipts.

Separately recorded Elo rule forecasts, using published ESPN regular-season
finals genuinely retrieved before the forecast; never Champion-001 forecasts,
licensed bookmaker prices, calibrated probabilities, or betting selections.
NFL ties are omitted from the binary win/loss update and grading target:
the resulting probability is CONDITIONAL on a non-tie, NOT an actionable NFL
two-way moneyline estimate. All grades and sportsbook settlement remain HOLD.

Each original future ESPN schedule response is preserved byte-for-byte, along
with the local SHA-256 and response-completion wall-clock. A local hash/GitHub
timestamp alone cannot externally authenticate source provenance.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger_elo_walkforward import validate_game
from challenger_research_features import validated as validate_history_row
from historical_outcomes import collect as collect_history, parse_time, scoreboard_url
from independent_schedule_review import download_json_original

NY = ZoneInfo("America/New_York")
# Frozen in the initial forward research version, NOT fitted on outcome data.
SPEC = {
    "nfl": {"k": 18.0, "home_elo": 45.0, "minimum_prior_games": 35,
            "lookahead_days": 7, "version": "v8-nfl-elo-forward-v0-k18-ha45"},
    "nhl": {"k": 16.0, "home_elo": 35.0, "minimum_prior_games": 50,
            "lookahead_days": 2, "version": "v8-nhl-elo-forward-v0-k16-ha35"},
}
HISTORY_DAYS = 35
RESULT_ASSUMED_LAG_HOURS = 48
MAX_SCHEDULE_BYTES = 5_000_000


def _time_from_clock(clock):
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone_aware_realtime_clock_required")
    return value.astimezone(timezone.utc)


def _rating_probability(home, away, league):
    settings = SPEC[league]
    p = 1.0 / (1.0 + 10 ** ((away-home-settings["home_elo"])/400.0))
    if not math.isfinite(p) or not 0.001 < p < 0.999:
        raise ValueError("unacceptable_research_probability")
    return p


def historical_ratings(league, rows, asof):
    """Replay only genuinely retrieved, 48h-matured regular-season results."""
    if league not in SPEC:
        raise ValueError("unsupported_forward_research_league")
    now = parse_time(asof.isoformat())
    if not isinstance(rows, list):
        raise ValueError("original_history_list_required")
    seen, used, ties, mature = set(), [], 0, 0
    for item in rows:
        validate_history_row(item)
        game_league, start, eid, home, away, result = validate_game(item)
        if game_league != league or item.get("season_type") != 2:
            raise ValueError("mixed_or_nonregular_season_history")
        if (not isinstance(eid, str) or not eid.isdecimal()
                or item.get("source_url") != scoreboard_url(league, start.astimezone(NY).date())):
            raise ValueError("historical_event_or_scoreboard_day_mismatch")
        if eid in seen:
            raise ValueError("duplicate_published_history_event")
        seen.add(eid)
        observed = parse_time(item.get("retrieved_at_utc"))
        if observed > now:
            raise ValueError("published_final_not_retrieved_prior_to_forecast")
        if start + timedelta(hours=RESULT_ASSUMED_LAG_HOURS) > now:
            continue
        mature += 1
        if result is None:
            ties += 1
            continue
        used.append((start, eid, home, away, result))
    used.sort(key=lambda g:(g[0],g[1]))
    rating = defaultdict(lambda:1500.0)
    waiting = []
    for start, group in groupby(used, key=lambda x:x[0]):
        matured = [item for item in waiting if item[0] <= start]
        waiting = [item for item in waiting if item[0] > start]
        for _,home,away,y,p in sorted(matured, key=lambda x:(x[0],x[1],x[2])):
            change = SPEC[league]["k"]*(y-p)
            rating[home] += change
            rating[away] -= change
        for _,eid,home,away,y in group:
            p = _rating_probability(rating[home],rating[away],league)
            waiting.append((start+timedelta(hours=RESULT_ASSUMED_LAG_HOURS),home,away,y,p))
    # Every eligible historical event is now >=48h in the past.
    for _,home,away,y,p in sorted(waiting, key=lambda x:(x[0],x[1],x[2])):
        change = SPEC[league]["k"]*(y-p)
        rating[home] += change
        rating[away] -= change
    return dict(rating), {"matured_games":mature,"matured_binary_games":len(used),
                          "matured_ties_excluded":ties}


def parse_original_future_schedule(league, payload, raw, day, received_at):
    """Verify the original response is contemporaneous and each event is pre."""
    if (league not in SPEC or not isinstance(payload,dict)
            or not isinstance(raw,bytes) or not 0<len(raw)<=MAX_SCHEDULE_BYTES
            or json.loads(raw)!=payload):
        raise ValueError("source_original_ESPN_bytes_not_verified_locally")
    games=payload.get("events")
    if not isinstance(games,list) or len(games)>=500:
        raise ValueError("ESPN_schedule_shape_missing_or_possibly_truncated")
    when=parse_time(received_at.isoformat())
    result=[]
    ids=set()
    for item in games:
        if not isinstance(item,dict):
            continue
        season=item.get("season")
        if not isinstance(season,dict) or type(season.get("type")) is not int or season["type"]!=2:
            continue
        status=item.get("status")
        if (not isinstance(status,dict) or not isinstance(status.get("type"),dict)
                or status["type"].get("state")!="pre"):
            continue
        comp=item.get("competitions")
        if not isinstance(comp,list) or len(comp)!=1 or not isinstance(comp[0],dict):
            continue
        teams=comp[0].get("competitors")
        if not isinstance(teams,list) or len(teams)!=2:
            continue
        sides={}
        for row in teams:
            if not isinstance(row,dict) or row.get("homeAway") not in ("home","away"):
                break
            team=row.get("team")
            if not isinstance(team,dict):
                break
            teamid=str(team.get("id") or "")
            name=team.get("displayName")
            if not teamid.isdecimal() or not isinstance(name,str) or not name.strip():
                break
            if row["homeAway"] in sides:
                break
            sides[row["homeAway"]]=(teamid,name.strip())
        if set(sides)!={"home","away"} or sides["home"][0]==sides["away"][0]:
            continue
        try:
            start=parse_time(item.get("date") or comp[0].get("date"))
        except (ValueError,TypeError):
            continue
        if (start<=when or start.astimezone(NY).date()!=day
                or start>when+timedelta(days=8)):
            continue
        eid=str(item.get("id") or "")
        if not eid.isdecimal():
            continue
        if eid in ids:
            raise ValueError("duplicate_future_schedule_event_identity")
        ids.add(eid)
        result.append({
            "league":league,"espn_event_id":eid,"start_utc":start.isoformat(),
            "home_team_espn_id":sides["home"][0],"away_team_espn_id":sides["away"][0],
            "home_team":sides["home"][1],"away_team":sides["away"][1],
            "schedule_original_received_at_utc":when.isoformat(),
            "schedule_original_sha256_local_receipt":hashlib.sha256(raw).hexdigest(),
            "schedule_source_url":scoreboard_url(league,day),
        })
    return result


def project(league, history, coverage, future, recorded_at):
    """Produce strictly prestart research forecasts or an explicit HOLD."""
    if league not in SPEC or not isinstance(future,list) or not isinstance(coverage,dict):
        raise ValueError("original_source_evidence_required")
    now=parse_time(recorded_at.isoformat())
    by=coverage.get("by_league",{}).get(league,{})
    days,okay,failed=(by.get("days_attempted"),by.get("days_ok"),by.get("days_failed"))
    if (coverage.get("leagues")!=[league] or coverage.get("champion_001_modified") is not False
            or type(days) is not int or not 1<=days<=35
            or type(okay) is not int or type(failed) is not int
            or min(okay,failed)<0 or okay+failed!=days
            or coverage.get("total_completed_results")!=len(history)):
        raise ValueError("historical_source_day_counts_do_not_reconcile")
    reasons=Counter()
    ratings={}
    detail={"matured_games":0,"matured_binary_games":0,"matured_ties_excluded":0}
    if failed:
        reasons["historical_ESPN_source_days_failed"]=failed
    else:
        ratings,detail=historical_ratings(league,history,now)
        if detail["matured_binary_games"]<SPEC[league]["minimum_prior_games"]:
            reasons["minimum_matured_binary_history_unmet"]=1
    forecasts=[]
    seen=set()
    for game in future:
        if not isinstance(game,dict) or game.get("league")!=league:
            raise ValueError("foreign_future_league")
        eid=game.get("espn_event_id")
        if eid in seen:
            raise ValueError("duplicate_future_events_across_days")
        seen.add(eid)
        t=parse_time(game.get("start_utc"))
        observed=parse_time(game.get("schedule_original_received_at_utc"))
        if not observed<=now<t:
            reasons["event_started_or_source_was_observed_after_forecast"]=reasons.get(
                "event_started_or_source_was_observed_after_forecast",0)+1
            continue
        if reasons.get("historical_ESPN_source_days_failed") or reasons.get("minimum_matured_binary_history_unmet"):
            continue
        home,away=game.get("home_team_espn_id"),game.get("away_team_espn_id")
        if (not isinstance(home,str) or not home.isdecimal()
                or not isinstance(away,str) or not away.isdecimal() or home==away):
            raise ValueError("future_team_identity_invalid")
        p=_rating_probability(ratings.get(home,1500.),ratings.get(away,1500.),league)
        forecasts.append({
            "record_type":"v8_genuine_forward_clocktime_multisport_Elo_research_only",
            "league":league,
            "espn_event_id":eid,
            "home_team":game["home_team"],"away_team":game["away_team"],
            "home_team_espn_id":home,"away_team_espn_id":away,
            "start_utc":t.isoformat(),"forecast_recorded_utc":now.isoformat(),
            "schedule_original_received_at_utc":observed.isoformat(),
            "schedule_original_sha256_local_receipt":
                game["schedule_original_sha256_local_receipt"],
            "schedule_source_url":game["schedule_source_url"],
            "model_version":SPEC[league]["version"],
            "model_probability_home_win_research_only":round(p,9),
            "model_probability_away_win_research_only":round(1-p,9),
            "model_target":(
                "NFL_home_vs_away_given_no_tie_NOT_a_market_moneyline"
                if league=="nfl" else
                "NHL_fullgame_published_winner_including_OT_SO_not_market_verified"),
            "original_history_matured_games":detail["matured_binary_games"],
            "historical_ties_excluded":detail["matured_ties_excluded"],
            "assumed_history_final_publication_lag_hours":RESULT_ASSUMED_LAG_HOURS,
            "original_prediction_recorded_before_tipoff":True,
            "future_outcome":None,"published_final_observed_at_utc":None,
            "qualified_for_certified_champion_001_shadow":False,
            "model_independently_calibrated":False,
            "bookmaker_checkout_price_verified":False,
            "official_league_final_independently_adjudicated":False,
            "certified_prediction":False,"positive_ev_bet":False,
            "bet_ready":False,"stake_usd":0,"champion_001_modified":False,
        })
    return forecasts, {
        "stage":"v8_nfl_nhl_forward_original_source_research_only",
        "league":league,"model_version":SPEC[league]["version"],
        "recorded_at_utc":now.isoformat(),
        "published_history_retrieved":len(history),
        "source_days_attempted":days,
        "source_days_ok":okay,"source_days_failed":failed,
        **detail,
        "history_minimum_binary_games":SPEC[league]["minimum_prior_games"],
        "schedule_future_events_identified":len(future),
        "forecast_probabilities_recorded_before_start":len(forecasts),
        "hold_reasons":dict(sorted(reasons.items())),
        "forecast_target_is_true_DraftKings_moneyline":False,
        "independently_verified_executable_DraftKings_quotes":0,
        "original_champion_001_certified_predictions":0,
        "certified_v8_predictions":0,"certified_positive_ev_bets":0,
        "automated_wagers":0,"champion_001_modified":False,"bet_ready":False,
        "warning":(
            "Original schedule bytes and capture times are local/GitHub "
            "receipts, not independent authentication. ESPN historical finals "
            "were retrieved at the actual scan time and earlier outcomes "
            "are assumed mature after 48h. NFL tie outcomes are excluded: "
            "binary forecast conditions on no tie and MUST NOT be marketed "
            "as an actionable NFL moneyline price. NHL overtime/shootout "
            "settlement is also unaudited. These are not Champion-001 "
            "predictions or independently certified positive EV."),
    }


def capture(league, output_dir, *, history_days=HISTORY_DAYS,
            history_collector=collect_history,
            fetch_schedule=download_json_original, clock=None):
    if league not in SPEC:
        raise ValueError("unsupported_forward_league")
    if type(history_days) is not int or not 1<=history_days<=35:
        raise ValueError("history_days_outside_1_to_35")
    clock=clock or (lambda:datetime.now(timezone.utc))
    first=_time_from_clock(clock)
    root=Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError("forward_source_artifact_directory_must_be_empty")
    root.mkdir(parents=True,exist_ok=True)
    last_completed_day=first.astimezone(NY).date()-timedelta(days=1)
    history,coverage=history_collector((league,),history_days,last_completed_day)
    future,failures,original_files=[],[],[]
    capture_day=first.astimezone(NY).date()
    for offset in range(SPEC[league]["lookahead_days"]):
        day=capture_day+timedelta(days=offset)
        url=scoreboard_url(league,day)
        try:
            payload,raw=fetch_schedule(url)
            observed=_time_from_clock(clock)
            if observed<first or observed.astimezone(NY).date()!=capture_day:
                raise ValueError("source_clock_regressed_or_crossed_date")
            events=parse_original_future_schedule(league,payload,raw,day,observed)
            filename=f"{league}_original_future_schedule_{day:%Y%m%d}.json"
            with (root/filename).open("xb") as stream:
                stream.write(raw)
            original_files.append({
                "file":filename,"sha256":hashlib.sha256(raw).hexdigest(),
                "completed_source_response_at_utc":observed.isoformat(),
            })
            future.extend(events)
        except (ValueError,TypeError,TimeoutError,OSError,KeyError) as exc:
            failures.append({"date_et":day.isoformat(),"error_type":type(exc).__name__})
    forecasted=_time_from_clock(clock)
    if forecasted.astimezone(NY).date()!=capture_day:
        raise ValueError("forecast_run_crossed_Eastern_calendar_date")
    rows,report=project(league,history,coverage,future,forecasted)
    if failures:
        report["hold_reasons"]["future_schedule_source_days_failed"]=len(failures)
        report["source_future_schedule_failures"]=failures
    report["source_original_schedules_saved"]=original_files
    report["history_collection_started_at_utc"]=first.isoformat()
    report["github_run_id_self_reported"]=__import__("os").environ.get("GITHUB_RUN_ID")
    prefix=league.upper()
    (root/f"{prefix}_FORWARD_RESEARCH_FORECASTS.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf-8")
    (root/f"{prefix}_FORWARD_RESEARCH_STATUS.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (root/f"{prefix}_PUBLISHED_HISTORY_COVERAGE.json").write_text(
        json.dumps(coverage,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return rows,report


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--league",required=True,choices=sorted(SPEC))
    p.add_argument("--history-days",type=int,default=35)
    p.add_argument("--output-dir",default="v8_results/new_sport_forward")
    args=p.parse_args()
    results,summary=capture(args.league,args.output_dir,history_days=args.history_days)
    print(json.dumps({
        "sport":args.league,
        "forward_research_forecasts_recorded":len(results),
        "historical_games_retrieved":summary["published_history_retrieved"],
        "matured_binary_games":summary["matured_binary_games"],
        "schedule_future_events":summary["schedule_future_events_identified"],
        "holds":summary["hold_reasons"],
        "certified_predictions":0,"verified_positive_ev_bets":0,
    },sort_keys=True))
