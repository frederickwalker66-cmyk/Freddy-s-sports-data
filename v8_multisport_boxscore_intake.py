"""Bounded ESPN original-source player boxscore adapters for all eight leagues.

ESPN summary schemas vary by sport and may not contain comparable props;
unrecognized fields remain missing, not zeros. The parser requires event
and team IDs to match a *separately captured* ESPN score final and a
completed-game status. Single-provider values remain unverified for
bookmaker settlement, availability, and independent model training.

NBA and college hoops share PTS/REB/AST/3PT vectors; football has passing,
rushing, receiving categories; MLB distinguishes batting from pitching;
hockey uses skater vs goalie stats; soccer is best effort and often
provides no usable ESPN boxscore player vectors (report unavailable).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import re
from urllib.request import Request, urlopen

from historical_outcomes import parse_time
from challenger_research_features import validated
from v8_all_sports_player_form import ESPN_SUMMARY_ROOT, SPORT_PATH, STATS

MAX_SUMMARY_BYTES=4_000_000
MAX_ATHLETES_PER_SUMMARY=260


def _int(v, minv=0, maxv=3000):
    if type(v) is int and minv<=v<=maxv:
        return v
    if isinstance(v,str) and re.fullmatch(r"-?\d{1,5}",v.strip()):
        i=int(v.strip())
        return i if minv<=i<=maxv else None
    return None


def _minutes(v):
    if type(v) in (int,float) and 0<=v<=130:
        return round(float(v),3)
    if isinstance(v,str) and re.fullmatch(r"\d{1,3}(:[0-5]\d)?",v):
        h=v.split(":")
        n=int(h[0])+(int(h[1])/60 if len(h)>1 else 0)
        return round(n,3) if n<=130 else None
    return None


def _made(v):
    if not isinstance(v,str) or not re.fullmatch(r"\d{1,2}-\d{1,2}",v):
        return None
    a,b=map(int,v.split("-"))
    return a if a<=b else None


def _ip_outs(v):
    if type(v) not in (int,float,str):
        return None
    s=str(v)
    if not re.fullmatch(r"\d{1,2}(\.\d)?",s):
        return None
    full,_,rem=s.partition(".")
    if rem not in ("","0","1","2"):
        return None
    return 3*int(full)+(int(rem) if rem else 0)


def _football(cat,cells,out):
    if cat=="passing":
        ca=cells.get("C/ATT") or cells.get("CMP/ATT")
        if isinstance(ca,str) and re.fullmatch(r"\d{1,3}/\d{1,3}",ca):
            x,y=map(int,ca.split("/"))
            if x<=y:
                out["passing_completions"]=x
                out["passing_attempts"]=y
        for key,label in (("passing_yards","YDS"),("passing_touchdowns","TD"),
                          ("passing_interceptions","INT")):
            v=_int(cells.get(label), -150 if key=="passing_yards" else 0)
            if v is not None:
                out[key]=v
    elif cat=="rushing":
        for key,label,minimum in (("rushing_attempts","CAR",0),
                                  ("rushing_yards","YDS",-150),
                                  ("rushing_touchdowns","TD",0)):
            v=_int(cells.get(label),minimum)
            if v is not None:out[key]=v
    elif cat=="receiving":
        for key,aliases,minimum in (
                ("receiving_yards",("YDS",),-150),
                ("receptions",("REC",),0),
                ("receiving_targets",("TGTS","TGT"),0),
                ("receiving_touchdowns",("TD",),0)):
            v=next((_int(cells.get(k),minimum) for k in aliases if
                    _int(cells.get(k),minimum) is not None),None)
            if v is not None:out[key]=v


def _baseball(cat,cells,out):
    # ESPN category names vary ("batting", "Batters", "Batting Stats").
    # When the label vector itself establishes batting/pitching, use it
    # rather than treating a valid player stat array as unavailable.
    c=cat.strip().lower()
    if "pitch" in c or any(k in cells for k in ("IP","WHIP","ERA")):
        scope="pitching"
    elif ("bat" in c or "hitt" in c or
          any(k in cells for k in ("AB","RBI","AVG","BA"))):
        scope="batting"
    else:
        scope="unidentified"
    if scope=="batting":
        for key,aliases in (
                ("hits",("H",)),("runs",("R",)),("rbis",("RBI",)),
                ("home_runs",("HR",)),("total_bases",("TB",)),
                ("stolen_bases",("SB",)),("batting_walks",("BB",)),
                ("batting_strikeouts",("SO","K"))):
            for label in aliases:
                v=_int(cells.get(label))
                if v is not None:
                    out[key]=v
                    break
    elif scope=="pitching":
        for key,aliases in (
                ("pitching_strikeouts",("SO","K")),
                ("hits_allowed",("H",)),("earned_runs",("ER",)),
                ("walks_allowed",("BB",))):
            for label in aliases:
                v=_int(cells.get(label))
                if v is not None:
                    out[key]=v
                    break
        outs=_ip_outs(cells.get("IP"))
        if outs is not None:out["pitching_outs"]=outs


def _basketball(cells,out):
    for key,aliases in (
            ("points",("PTS",)),("rebounds",("REB",)),("assists",("AST",)),
            ("steals",("STL",)),("blocks",("BLK",)),("turnovers",("TO",))):
        for name in aliases:
            v=_int(cells.get(name))
            if v is not None:
                out[key]=v
                break
    three=_made(cells.get("3PT"))
    if three is not None:out["threes_made"]=three
    mins=_minutes(cells.get("MIN"))
    if mins is not None:out["minutes"]=mins


def _hockey(cat,cells,out):
    lower=cat.lower()
    if "goal" in lower:
        v=_int(cells.get("SV") or cells.get("SAVES"))
        if v is not None:out["saves"]=v
        return
    for key,aliases in (
            ("goals",("G",)),("assists",("A",)),
            ("points",("PTS","P")),("shots_on_goal",("SOG","S")),
            ("blocked_shots",("BS","BLK","BLOCKED"))):
        for name in aliases:
            v=_int(cells.get(name))
            if v is not None:
                out[key]=v
                break


def _soccer(cells,out):
    for key,aliases in (
            ("goals",("G","GLS","GOALS")),("assists",("A","AST","ASSISTS")),
            ("shots",("SH","SHOTS")),("shots_on_target",("SOG","SOT")),
            ("saves",("SV","SAVES"))):
        for label in aliases:
            v=_int(cells.get(label))
            if v is not None:out[key]=v;break
    mins=_minutes(cells.get("MIN") or cells.get("MINS"))
    if mins is not None:out["minutes"]=mins


def parse_box_score(league, data, historical_event, observed_utc):
    """Map source summary to partial stat vectors, quarantine unsupported shapes."""
    if league not in STATS:
        raise ValueError("unknown_eight_sport_league")
    validated(historical_event)
    eid=historical_event["espn_event_id"]
    if historical_event["league"]!=league or historical_event.get("season_type")!=2:
        raise ValueError("summary_and_regular_season_game_mismatch")
    observed=parse_time(observed_utc.isoformat() if isinstance(observed_utc,datetime)
                        else observed_utc)
    started=parse_time(historical_event["event_start_utc"])
    if not started < observed:
        raise ValueError("summary_not_captured_after_game_start")
    if not isinstance(data,dict) or not isinstance(data.get("header"),dict):
        raise ValueError("missing_ESPN_summary_header")
    header=data["header"]
    if str(header.get("id"))!=eid:
        raise ValueError("summary_espn_event_ID_mismatch")
    comps=header.get("competitions")
    if not isinstance(comps,list) or len(comps)!=1 or not isinstance(comps[0],dict):
        raise ValueError("ambiguous_ESPN_summary_competition")
    comp=comps[0]
    if (not isinstance(comp.get("status"),dict)
            or not isinstance(comp["status"].get("type"),dict)
            or comp["status"]["type"].get("completed") is not True):
        raise ValueError("ESPN_summary_event_not_final")
    cdate=comp.get("date")
    if cdate is not None and parse_time(cdate)!=started:
        raise ValueError("ESPN_summary_start_differs_from_original_score")
    teams=comp.get("competitors")
    if (not isinstance(teams,list) or len(teams)!=2
            or {str(x.get("team",{}).get("id")) for x in teams}
            != {historical_event["home_team_espn_id"],
                historical_event["away_team_espn_id"]}):
        raise ValueError("ESPN_summary_scoreboard_team_ID_mismatch")
    groups=(data.get("boxscore") or {}).get("players")
    if not isinstance(groups,list) or len(groups)!=2:
        raise ValueError("ESPN_summary_missing_two_team_player_vectors")
    people={}
    for group in groups:
        tid=str((group.get("team") or {}).get("id"))
        if tid not in {historical_event["home_team_espn_id"],
                       historical_event["away_team_espn_id"]}:
            raise ValueError("ESPN_summary_group_team_disagrees_with_scoreboard")
        cats=group.get("statistics")
        if not isinstance(cats,list):
            raise ValueError("ESPN_summary_missing_player_categories")
        for category in cats:
            if not isinstance(category,dict):
                continue
            labels=category.get("names") or category.get("labels")
            athletes=category.get("athletes")
            if not isinstance(labels,list) or not isinstance(athletes,list):
                continue
            label_set=[str(v).upper().strip() for v in labels]
            subtype=str(category.get("name") or category.get("displayName") or "").lower()
            seen_in_category=set()
            for athlete in athletes:
                if not isinstance(athlete,dict):
                    continue
                info=athlete.get("athlete") or {}
                pid=str(info.get("id") or "")
                if not pid.isdecimal() or pid in seen_in_category:
                    raise ValueError("duplicate_or_invalid_ESPN_player_identity")
                seen_in_category.add(pid)
                values=athlete.get("stats")
                if not isinstance(values,list) or len(values)!=len(labels):
                    if athlete.get("didNotPlay") is True and values in ([],None):
                        values=[]
                    else:
                        raise ValueError("ESPN_incomplete_player_stat_vector")
                cells=dict(zip(label_set,values))
                key=(pid,tid)
                item=people.setdefault(key,{"stats":{},"dnp":None,"player_name":info.get("displayName")})
                if athlete.get("didNotPlay") is True:
                    if item["dnp"] is False:
                        raise ValueError("inconsistent_ESPN_DNP_status")
                    item["dnp"]=True
                    continue
                parsed={}
                if league in ("nba","ncaab"):
                    _basketball(cells,parsed)
                elif league in ("nfl","ncaaf"):
                    _football(subtype,cells,parsed)
                elif league=="mlb":
                    _baseball(subtype,cells,parsed)
                elif league=="nhl":
                    _hockey(subtype,cells,parsed)
                else:
                    _soccer(cells,parsed)
                if parsed:
                    if item["dnp"] is True:
                        raise ValueError("inconsistent_ESPN_DNP_status")
                    item["dnp"]=False
                    item["stats"].update(parsed)
    if len(people)>MAX_ATHLETES_PER_SUMMARY:
        raise ValueError("ESPN_summary_player_row_budget_exceeded")
    output=[]
    for (pid,tid),item in sorted(people.items()):
        if item["dnp"] is None:
            continue  # no confirmed player participation or parseable stats
        if item["dnp"] is False and not item["stats"]:
            continue
        output.append({
            "league":league,"espn_event_id":eid,"espn_player_id":pid,
            "espn_team_id":tid,"historical_player_name_not_roster_verified":item["player_name"],
            "event_start_utc":started.isoformat(),
            "retrieved_at_utc":observed.isoformat(),
            "source_url":ESPN_SUMMARY_ROOT+SPORT_PATH[league]+"/summary?event="+eid,
            "event_start_from_original_scoreboard":cdate is None,
            "season_type":2,"did_not_play":item["dnp"],
            "stats":{k:v for k,v in item["stats"].items() if k in STATS[league]},
            "published_boxscore_research_only":True,
            "independently_verified_player_stats":False,
            "qualified_for_player_prop_training":False,
            "historical_prop_settlement_verified":False,
            "bookmaker_player_id_crosswalk_verified":False,
            "champion_001_modified":False,
        })
    return output


def fetch_boxscore(league,event_id):
    if league not in SPORT_PATH or not isinstance(event_id,str) or not event_id.isdecimal():
        raise ValueError("invalid_ESPN_summary_request")
    url=ESPN_SUMMARY_ROOT+SPORT_PATH[league]+"/summary?event="+event_id
    request=Request(url,headers={"Accept":"application/json",
                                 "User-Agent":"FreddysPicksSeasonFormResearch/1.0"})
    with urlopen(request,timeout=14) as f:
        raw=f.read(MAX_SUMMARY_BYTES+1)
    if len(raw)>MAX_SUMMARY_BYTES:
        raise ValueError("oversized_ESPN_summary")
    response=json.loads(raw)
    if not isinstance(response,dict):
        raise ValueError("malformed_ESPN_summary")
    return response
