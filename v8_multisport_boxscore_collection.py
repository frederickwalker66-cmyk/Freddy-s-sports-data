"""Incremental league-specific season-to-date ESPN player boxscore cache.

Requires completed *same-season* ESPN score event IDs. This does NOT
infer any roster identity from sportsbook provider data. Default fetch
budget is 250 event summaries per league run, timestamps each receipt,
retains previously validated rows and never claims complete seasons when
source games remain uncollected. Request failures are explicit.
"""
from __future__ import annotations

from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path

from historical_outcomes import parse_time
from challenger_research_features import validated
from v8_all_sports_season_form import season_anchor,source_league_season_scope,NY
from v8_all_sports_player_form import STATS, _window, ESPN_SUMMARY_ROOT,SPORT_PATH
from v8_multisport_boxscore_intake import fetch_boxscore,parse_box_score

MAX_NEW_SUMMARIES=250
MAX_BOX_ROWS=300000
MAX_SCORE_EVENTS=10000


def _validate_player_rows(league,rows,score_lookup,asof):
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or row.get("league")!=league
                or row.get("published_boxscore_research_only") is not True
                or row.get("champion_001_modified") is not False
                or row.get("independently_verified_player_stats") is not False
                or row.get("qualified_for_player_prop_training") is not False):
            raise ValueError("invalid_previous_player_box_source_provenance")
        eid,pid,tid=(row.get(k) for k in ("espn_event_id","espn_player_id","espn_team_id"))
        if (not isinstance(eid,str) or eid not in score_lookup
                or not isinstance(pid,str) or not pid.isdecimal()
                or not isinstance(tid,str) or not tid.isdecimal()
                or (eid,pid) in seen):
            raise ValueError("duplicate_or_mismatched_season_ESPN_player")
        seen.add((eid,pid))
        score=score_lookup[eid]
        if tid not in (score["home_team_espn_id"],score["away_team_espn_id"]):
            raise ValueError("player_team_not_in_ESPN_historical_score")
        if (row.get("event_start_utc") != score["event_start_utc"]
                or row.get("source_url")!=
                ESPN_SUMMARY_ROOT+SPORT_PATH[league]+"/summary?event="+eid
                or parse_time(row["retrieved_at_utc"])>asof):
            raise ValueError("player_original_source_time_or_event_mismatch")
        s=row.get("stats")
        if not isinstance(s,dict) or set(s)-set(STATS[league]):
            raise ValueError("stat_not_supported_for_player_league")
    return seen


def _board(league,player_rows,score_lookup,score_manifest,asof):
    regular_ids={eid for eid,g in score_lookup.items()
                 if source_league_season_scope(league,g["season_type"])}
    # Today's / yesterday's results are deliberately in the 48h embargo.
    # They MUST NOT falsely block coverage of all *eligible* matured games.
    matured_ids={eid for eid in regular_ids
                 if parse_time(score_lookup[eid]["event_start_utc"])+
                    timedelta(hours=48)<=asof}
    observed_ids={p["espn_event_id"] for p in player_rows}
    source_complete=(score_manifest.get("source_coverage_complete") is True
                     and not matured_ids-observed_ids)
    by_player=defaultdict(list)
    for row in player_rows:
        if row["did_not_play"] is not False:
            continue
        start=parse_time(row["event_start_utc"])
        if start+timedelta(hours=48)>asof:
            continue
        vals=row.get("stats") or {}
        if not any(v is not None for v in vals.values()):
            continue
        by_player[row["espn_player_id"]].append({
            "start":start,"event_id":row["espn_event_id"],
            "team_id":row["espn_team_id"],"stats":vals,
        })
    results={}
    for pid,v in by_player.items():
        v.sort(key=lambda x:(x["start"],x["event_id"]))
        results[pid]={
            "historical_espn_player_id":pid,
            "historical_espn_team_ids":sorted({x["team_id"] for x in v}),
            "last5":_window(v,league,5,source_complete),
            "last10":_window(v,league,10,source_complete),
            "historical_appearances_in_cached_season":len(v),
            "current_team_or_active_roster_confirmed":False,
            "player_prop_market_probability":None,
            "champion_001_modified":False,
        }
    return {
        "report_type":"EIGHT_LEAGUE_SEASON_PLAYER_LAST5_LAST10_STATS",
        "league":league,"as_of_utc":asof.isoformat(),
        "original_score_event_count_regular_season":len(regular_ids),
        "regular_season_events_with_parsed_player_rows":len(regular_ids&observed_ids),
        "matured_events_eligible_for_source_player_boxes":len(matured_ids),
        "matured_events_with_source_player_boxes":len(matured_ids&observed_ids),
        "matured_events_still_missing_boxscore":len(matured_ids-observed_ids),
        "soccer_market_competition_stage_unverified":league in ("mls","uefa_champions_league"),
        "source_scoreboard_coverage_complete":score_manifest.get("source_coverage_complete"),
        "player_boxscore_event_coverage_complete":source_complete,
        "player_ids_observed":len(results),
        "players_with_complete_last5":sum(x["last5"]["complete_window_for_sport_stats"]
                                           for x in results.values()),
        "players_with_complete_last10":sum(x["last10"]["complete_window_for_sport_stats"]
                                            for x in results.values()),
        "players":results,"team_and_player_current_roster_not_verified":True,
        "bookmaker_prop_price_and_player_crosswalk_verified":False,
        "certified_positive_ev_bets":0,"champion_001_modified":False,
    }


def collect_player_boxes(league,history_dir,output_dir,*,previous_dir=None,
                         clock=None,fetcher=fetch_boxscore,
                         max_new_summaries=MAX_NEW_SUMMARIES):
    if league not in STATS:
        raise ValueError("unrecognized_eight_sport_league")
    if (type(max_new_summaries) is not int or
            not 1<=max_new_summaries<=MAX_NEW_SUMMARIES):
        raise ValueError("max_player_summary_requests_exceeded")
    clock=clock or (lambda:datetime.now(timezone.utc))
    def at():
        t=clock()
        if not isinstance(t,datetime) or t.tzinfo is None:
            raise ValueError("source_receipt_clock_not_aware")
        return t.astimezone(timezone.utc)
    start=at()
    hd=Path(history_dir)
    coverage=json.loads((hd/"SEASON_COVERAGE.json").read_text())
    if (coverage.get("league")!=league or
            coverage.get("champion_001_modified") is not False):
        raise ValueError("player_score_season_source_mismatch")
    raw=(hd/"SEASON_RESULTS.jsonl").read_bytes()
    if len(raw)>12_000_000:
        raise ValueError("oversized_season_historical_score_file")
    scores=[json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    if len(scores)>MAX_SCORE_EVENTS:
        raise ValueError("score_season_game_budget_exceeded")
    lookup={}
    for g in scores:
        validated(g)
        if g["league"]!=league or parse_time(g["retrieved_at_utc"])>start:
            raise ValueError("untrusted_historical_score_source")
        eid=g["espn_event_id"]
        if eid in lookup:
            raise ValueError("duplicate_event_in_score_history")
        lookup[eid]=g
    cache=[]
    if previous_dir is not None:
        folder=Path(previous_dir)
        prev_report=json.loads((folder/"PLAYER_BOX_COVERAGE.json").read_text())
        if (prev_report.get("league")!=league or
                prev_report.get("season_anchor_et")!=coverage["conservative_collection_anchor_et"]):
            raise ValueError("previous_player_season_incompatible")
        prevfile=folder/"PLAYER_BOX_HISTORY.jsonl"
        if prevfile.stat().st_size>100_000_000:
            raise ValueError("previous_player_data_too_large")
        cache=[json.loads(x) for x in prevfile.read_text().splitlines() if x.strip()]
        if len(cache)>MAX_BOX_ROWS:
            raise ValueError("previous_player_row_budget_exceeded")
    existing=_validate_player_rows(league,cache,lookup,start)
    complete_ids={eid for eid,pid in existing}
    eligible=[
        g for g in scores if source_league_season_scope(league,g.get("season_type"))
        and parse_time(g["event_start_utc"])+timedelta(hours=48)<=start
        and g["espn_event_id"] not in complete_ids
    ]
    eligible.sort(key=lambda x:(x["event_start_utc"],x["espn_event_id"]),reverse=True)
    attempted=eligible[:max_new_summaries]
    failures=Counter()
    failed_ids=[]
    success=[]
    for g in attempted:
        try:
            payload=fetcher(league,g["espn_event_id"])
            observed=at()
            rows=parse_box_score(league,payload,g,observed.isoformat())
            if not rows:
                failures["no_structurally_usable_player_stats"]+=1
                failed_ids.append(g["espn_event_id"])
                continue
            cache.extend(rows)
            success.append(g["espn_event_id"])
        except (TypeError,ValueError,KeyError,IndexError,OSError,TimeoutError) as e:
            failures[type(e).__name__]+=1
            failed_ids.append(g["espn_event_id"])
    asof=at()
    if asof.astimezone(NY).date()!=start.astimezone(NY).date():
        raise ValueError("player_box_collection_crossed_Eastern_day")
    if len(cache)>MAX_BOX_ROWS:
        raise ValueError("season_player_history_rows_exceed_budget")
    _validate_player_rows(league,cache,lookup,asof)
    # A successful source day with no parseable boxscore is not zero stats.
    board=_board(league,cache,lookup,coverage,asof)
    manifest={
        "report_type":"SEASON_TO_DATE_MULTISPORT_PLAYER_BOX_COLLECTION",
        "league":league,
        "season_anchor_et":coverage["conservative_collection_anchor_et"],
        "boxscore_events_attempted_now":len(attempted),
        "boxscore_events_with_usable_stats_now":len(success),
        "boxscore_events_failed_now":len(failed_ids),
        "boxscore_unavailable_source_error_classes":dict(sorted(failures.items())),
        "failed_event_ids":failed_ids[:40],
        "original_scoreboard_regular_season_events":board["original_score_event_count_regular_season"],
        "regular_season_boxscore_events_with_player_rows":
            board["regular_season_events_with_parsed_player_rows"],
        "matured_events_eligible_for_player_boxscore":
            board["matured_events_eligible_for_source_player_boxes"],
        "matured_events_missing_player_boxscore":
            board["matured_events_still_missing_boxscore"],
        "player_boxscore_event_coverage_complete":
            board["player_boxscore_event_coverage_complete"],
        "source_scoreboard_coverage_complete":
            board["source_scoreboard_coverage_complete"],
        "total_player_box_rows_captured":len(cache),
        "as_of_utc":asof.isoformat(),
        "all_8_leagues_event_box_parser_attempt_supported":True,
        "ESPN_player_boxscore_schema_can_be_unavailable_by_sport":True,
        "independently_authenticated_player_prop_settlements":0,
        "bookmaker_player_ID_verified_crosswalks":0,
        "certified_positive_ev_bets":0,
        "champion_001_modified":False,"wagers_placed":0,
    }
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=True)
    (root/"PLAYER_BOX_HISTORY.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in cache),encoding="utf-8")
    (root/"PLAYER_BOX_COVERAGE.json").write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (root/"PLAYER_LAST5_LAST10.json").write_text(
        json.dumps(board,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    lines=[
        f"# {league.upper()} historical player stats — last five / ten",
        f"**As of:** {asof.isoformat()}",
        f"**ESPN boxscore games captured / score games:** "
        f"{board['regular_season_events_with_parsed_player_rows']} / "
        f"{board['original_score_event_count_regular_season']}",
        f"**Complete source coverage:** {board['player_boxscore_event_coverage_complete']}",
        f"**Players with source-complete last 5 / last 10:** "
        f"{board['players_with_complete_last5']} / {board['players_with_complete_last10']}",
        "**Historical ESPN player IDs are not verified current active rosters or sportsbook player IDs.**",
        "**Missing stat or game is N/A; source data is NOT predictive prop probabilities or +EV.**",
        "| Historical ESPN player ID | Matured appearances in cached season | "
        "L5 complete | L10 complete | Example L5 stat averages |",
        "|---|---:|---|---|---|",
    ]
    for pid,p in list(sorted(board["players"].items()))[:80]:
        stats=p["last5"]["season_to_date_stats_last_window_average"]
        sample=", ".join(f"{key}={value}" for key,value in stats.items()
                         if value is not None)[:120] or "N/A"
        lines.append(f"| {pid} | {p['historical_appearances_in_cached_season']} "
                     f"| {p['last5']['complete_window_for_sport_stats']} "
                     f"| {p['last10']['complete_window_for_sport_stats']} | {sample} |")
    (root/"PLAYER_LAST5_LAST10.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return manifest,board

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--league",required=True,choices=sorted(STATS))
    p.add_argument("--season-dir",required=True)
    p.add_argument("--previous-dir")
    p.add_argument("--output-dir",required=True)
    p.add_argument("--max-new-summaries",type=int,default=MAX_NEW_SUMMARIES)
    a=p.parse_args(argv)
    report,board=collect_player_boxes(
        a.league,a.season_dir,a.output_dir,previous_dir=a.previous_dir,
        max_new_summaries=a.max_new_summaries)
    print(json.dumps({
        "league":a.league,
        "player_boxes_fetched":report["boxscore_events_with_usable_stats_now"],
        "attempted":report["boxscore_events_attempted_now"],
        "missing_events":report["original_scoreboard_regular_season_events"]-
                         report["regular_season_boxscore_events_with_player_rows"],
        "last5_complete":board["players_with_complete_last5"],
        "last10_complete":board["players_with_complete_last10"],
        "certified_positive_ev_bets":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
