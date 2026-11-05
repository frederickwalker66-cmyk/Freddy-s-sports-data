"""Pregame NBA league game-roster ID candidates against archived official injury rows.

This is prospective, review-only source corroboration. An official NBA player
ID associated with an exact team/name in a scheduled game's liveData boxscore
is an ID *candidate*, not proof of active participation, an authenticated
ESPN/DraftKings ID crosswalk, a bookmaker prop, or a model training feature.
Never use a live/final game boxscore as if it had been observed before tipoff.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_nba_injury_pdf_player_rows import (
    TEAM_CODES, TEAMS, STATUSES, run as read_original_injury_rows,
    MAX_EVENTS as MAX_EVENT_INPUT,
)
from challenger_nba_player_two_source_review import canonical, official_url
from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, official_nba_events, nba_team_name,
    MAX_ACCEPTED_CLOCK_DIFF_SECONDS,
)
from challenger_prospective_outcome_validation import instant
from challenger_nba_daily_scoreboard_fallback import validate_same_day_scoreboard

ET = ZoneInfo("America/New_York")
MAX_GAMES = 4
MAX_INJURY_ROWS = 300
MAX_SCHEDULE_BYTES = 18_000_000
MAX_BOX_BYTES = 4_000_000
MAX_GAME_AHEAD_SECONDS = 2 * 86400
MAX_INJURY_AGE_SECONDS = 24 * 3600
MAX_GAME_SNAPSHOT_AGE_SECONDS = 6 * 3600
SOURCE_CLASS = "official_nba_scheduled_game_boxscore_pregame_id_candidates"
RESULT_TYPE = "challenger_nba_pregame_roster_player_id_review_only"
FILINGS_TYPE = "nba_official_pdf_team_report_not_submitted_research_only"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_clock(clock):
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("capture_clock_must_have_timezone")
    return now.astimezone(timezone.utc)


def fetch_source(url, maximum):
    if url in (NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL):
        if maximum != MAX_SCHEDULE_BYTES:
            raise ValueError("wrong_nba_official_schedule_source_size_limit")
    else:
        game_id = url.rsplit("_", 1)[-1].removesuffix(".json")
        if url != official_url(game_id) or maximum != MAX_BOX_BYTES:
            raise ValueError("unapproved_nba_roster_source_url")
    if maximum not in (MAX_SCHEDULE_BYTES, MAX_BOX_BYTES):
        raise ValueError("unapproved_nba_roster_source_maximum")
    req = Request(url, headers={
        "User-Agent": "FreddysPicksProspectivePlayerIDs/1.0",
        "Accept": "application/json",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
    })
    with urlopen(req, timeout=18) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("oversized_nba_original_roster_source")
    return raw


def decode_json(raw, cap):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= cap:
        raise ValueError("bad_nba_original_roster_bytes")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("bad_nba_roster_json_object")
    return obj


def verify_injury_evidence(rows, filings, receipt, now):
    """Never accept projected active status or a fabricated pregame receipt."""
    if (not isinstance(rows, list) or len(rows) > MAX_INJURY_ROWS
            or not isinstance(filings, list) or not isinstance(receipt, dict)
            or receipt.get("stage") != "challenger_nba_official_pregame_pdf_player_rows_review_only"
            or receipt.get("original_pdf_source_status") != "captured_original_index_and_pdf"
            or receipt.get("pdf_extraction_error") is not None
            or receipt.get("player_rows_extracted_from_official_pdf") != len(rows)
            or receipt.get("teams_report_not_yet_submitted") != len(filings)
            or receipt.get("active_player_roster_verified") != 0
            or receipt.get("individual_player_id_crosswalk_verified") != 0
            or receipt.get("qualified_prop_training_observations") != 0
            or receipt.get("certified_champion_001_predictions") != 0
            or receipt.get("certified_challenger_001_predictions") != 0
            or receipt.get("certified_positive_ev_bets") != 0
            or receipt.get("bet_ready_selections") != 0
            or receipt.get("champion_001_modified") is not False):
        raise ValueError("unquarantined_or_missing_pdf_player_source_evidence")
    observed = instant(receipt.get("actual_original_pdf_observed_utc"))
    if not observed <= now or (now-observed).total_seconds() > MAX_INJURY_AGE_SECONDS:
        raise ValueError("stale_or_future_original_injury_pdf_observation")
    file_sha = receipt.get("original_pdf_sha256")
    if not isinstance(file_sha, str) or not re.fullmatch("[0-9a-f]{64}", file_sha):
        raise ValueError("original_nba_pdf_hash_missing")
    seen, submissions = set(), set()
    for filing in filings:
        if (not isinstance(filing, dict)
                or filing.get("record_type") != FILINGS_TYPE
                or filing.get("filing_status") != "not_yet_submitted"
                or filing.get("confirmed_all_players_available") is not False
                or filing.get("player_clearance_count") != 0
                or filing.get("bet_ready") is not False
                or filing.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nba_unsubmitted_filing")
        tcode = filing.get("team_abbreviation")
        if tcode not in TEAM_CODES or filing.get("team_name") != TEAM_CODES[tcode]:
            raise ValueError("bad_nba_pdf_unsubmitted_team")
        k=(filing.get("game_date_et"), filing.get("matchup"), tcode)
        if k in submissions:
            raise ValueError("duplicate_nba_team_unsubmitted_filing")
        submissions.add(k)
    for row in rows:
        if (not isinstance(row, dict)
                or row.get("record_type") != "nba_official_pdf_player_status_extracted_for_review_only"
                or row.get("nba_person_id") is not None
                or row.get("espn_athlete_id") is not None
                or row.get("player_current_game_active_status_verified") is not False
                or row.get("roster_player_id_crosswalk_verified") is not False
                or row.get("qualified_for_prop_training") is not False
                or row.get("market_eligibility_verified") is not False
                or row.get("certified_prediction") is not False
                or row.get("bet_ready") is not False
                or row.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nba_injury_player_row")
        c=row.get("nba_team_abbreviation")
        if c not in TEAM_CODES or row.get("team_name") != TEAM_CODES[c]:
            raise ValueError("bad_original_pdf_team_identity")
        display=canonical(row.get("source_player_name_display"))
        if not display or row.get("source_injury_designation") not in STATUSES:
            raise ValueError("invalid_pdf_player_name_or_status")
        matchup=row.get("matchup")
        if not isinstance(matchup, str) or not re.fullmatch("[A-Z]{2,3}@[A-Z]{2,3}", matchup):
            raise ValueError("invalid_pdf_player_game_identity")
        away,home=matchup.split("@")
        if away not in TEAM_CODES or home not in TEAM_CODES or away == home or c not in (home,away):
            raise ValueError("pdf_team_not_in_exact_matchup")
        k=(row.get("game_date_et"),matchup,c)
        if k in submissions:
            raise ValueError("player_listed_on_unsubmitted_team_filing")
        key=k+(display,)
        if key in seen:
            raise ValueError("duplicate_original_pdf_player_same_club_game")
        seen.add(key)
    return observed


def _valid_future_espn(events, observed, now):
    """Use actual capture time, exact full-team and game start, no guessed IDs."""
    if not isinstance(events,list) or len(events)>MAX_EVENT_INPUT:
        raise ValueError("invalid_espn_pregame_schedule_batch")
    grouped=defaultdict(list)
    seen=set()
    for e in events:
        if not isinstance(e,dict) or e.get("league")!="nba":
            continue
        if (e.get("record_type")!="prospective_evidence_snapshot_research_only"
                or e.get("player_level_status_parsed_and_verified") is not False
                or e.get("qualified_for_challenger_backtest") is not False
                or e.get("certified_prediction") is not False
                or e.get("model_probability") is not None
                or e.get("bet_ready") is not False
                or e.get("champion_001_modified") is not False):
            raise ValueError("unsafe_espn_injury_research_event")
        eid=e.get("espn_schedule_event_id")
        if not isinstance(eid,str) or not eid.isdecimal() or eid in seen:
            raise ValueError("duplicate_upcoming_espn_event_identity")
        seen.add(eid)
        start=instant(e.get("event_start_utc"))
        snap=instant(e.get("snapshot_completed_at_utc"))
        if (not snap<=observed<=now<start or
                (now-snap).total_seconds()>MAX_GAME_SNAPSHOT_AGE_SECONDS):
            continue
        h,a=nba_team_name(e.get("home_team")),nba_team_name(e.get("away_team"))
        if h not in TEAMS or a not in TEAMS or h==a:
            continue
        key=(start.astimezone(ET).date().isoformat(), TEAMS[a]+"@"+TEAMS[h])
        grouped[key].append({"espn_event_id":eid,"start":start})
    return grouped


def match_official_schedule(injury_rows, schedule, observed, now, events=None):
    """Join NBA injury report to NBA-operated scheduled game identity only."""
    nba_games=official_nba_events(schedule)
    espn_events=_valid_future_espn(events,observed,now) if events is not None else None
    by_key=defaultdict(list)
    seen_ids=set()
    for g in nba_games:
        gid=g["official_nba_game_id"]
        if not isinstance(gid,str) or not re.fullmatch("[0-9]{10}", gid) or gid in seen_ids:
            raise ValueError("invalid_or_duplicate_official_scheduled_game")
        seen_ids.add(gid)
        h,a=g["home"],g["away"]
        if h not in TEAMS or a not in TEAMS or h==a:
            continue
        start=g["start"]
        key=(start.astimezone(ET).date().isoformat(),TEAMS[a]+"@"+TEAMS[h])
        by_key[key].append(g)
    pairs=defaultdict(list)
    for r in injury_rows:
        pairs[(r["game_date_et"],r["matchup"])].append(r)
    candidates, problems={},{}
    for key,rows in pairs.items():
        games=[g for g in by_key[key]
               if now<g["start"]
               and observed<g["start"]
               and 0 < (g["start"]-now).total_seconds() <=MAX_GAME_AHEAD_SECONDS]
        if len(games)!=1:
            problems[key] = ("ambiguous_official_game_identity" if len(games)>1
                             else "no_unique_future_official_nba_game")
            continue
        selected=games[0]
        if espn_events is not None:
            possible=[e for e in espn_events[key] if
                      abs((e["start"]-selected["start"]).total_seconds()) <=
                      MAX_ACCEPTED_CLOCK_DIFF_SECONDS]
            if len(possible)!=1:
                problems[key] = ("ambiguous_espn_official_identity" if len(possible)>1
                                 else "missing_exact_espn_official_pregame_crosswalk")
                continue
            espn_id=possible[0]["espn_event_id"]
        else:
            espn_id=None
        candidates[key]={"game_id":selected["official_nba_game_id"],
                         "start":selected["start"],
                         "home":selected["home"],"away":selected["away"],
                         "espn_id":espn_id}
    return candidates, problems


def parse_pregame_nba_box(raw, planned, read_at):
    """Scheduled game only. Extract name/personId, NOT active/inactive clearance."""
    obj=decode_json(raw,MAX_BOX_BYTES)
    g=obj.get("game")
    if not isinstance(g,dict) or str(g.get("gameId"))!=planned["game_id"]:
        raise ValueError("wrong_game_in_nba_pregame_boxscore")
    if g.get("gameStatus") not in (1,"1"):
        raise ValueError("nba_boxscore_not_a_pregame_scheduled_state")
    if read_at>=planned["start"]:
        raise ValueError("nba_game_started_during_roster_capture")
    official_time=instant(g.get("gameTimeUTC"))
    if abs((official_time-planned["start"]).total_seconds())>MAX_ACCEPTED_CLOCK_DIFF_SECONDS:
        raise ValueError("nba_boxscore_and_schedule_start_disagree")
    out={}
    all_ids=set()
    for side in ("home","away"):
        team=g.get(side+"Team")
        if not isinstance(team,dict):
            raise ValueError("missing_official_nba_roster_team")
        name=nba_team_name(str(team.get("teamCity") or "")+" "+str(team.get("teamName") or ""))
        if name!=planned[side]:
            raise ValueError("official_nba_roster_wrong_team")
        tri=team.get("teamTricode")
        if tri is not None and tri!=TEAMS[name]:
            raise ValueError("official_nba_roster_team_tricode_mismatch")
        tid=team.get("teamId")
        if type(tid) not in (int,str) or not str(tid).isdigit():
            raise ValueError("missing_nba_official_team_id")
        array=team.get("players")
        if not isinstance(array,list) or not 1<=len(array)<=35:
            raise ValueError("missing_or_oversized_scheduled_player_list")
        by_name={}
        seen_team_ids=set()
        for p in array:
            if not isinstance(p,dict):
                raise ValueError("malformed_official_nba_pregame_player")
            person=p.get("personId")
            full=canonical(p.get("name"))
            if (type(person) not in (int,str) or not str(person).isdigit()
                    or not full or str(person) in all_ids or full in by_name
                    or str(person) in seen_team_ids):
                raise ValueError("ambiguous_official_nba_roster_player_identity")
            all_ids.add(str(person))
            seen_team_ids.add(str(person))
            status=p.get("status")
            reason=p.get("notPlayingReason")
            if status is not None and not isinstance(status,str):
                raise ValueError("unknown_nba_roster_status_format")
            if reason is not None and not isinstance(reason,str):
                raise ValueError("unknown_nba_not_playing_reason_format")
            by_name[full]={"person_id":str(person), "team_id":str(tid),
                           "printed_player_name":p["name"],
                           "raw_game_roster_status":status,
                           "raw_not_playing_reason":reason}
        out[side]=by_name
    return out


def review_identity(injury_rows, candidates, problems, boxes, source_checks,
                    injury_time, no_espn_events=False):
    results, statuses=[],Counter()
    for item in injury_rows:
        key=(item["game_date_et"],item["matchup"])
        record={
            "record_type":RESULT_TYPE,"league":"nba",
            "game_date_et":item["game_date_et"],"matchup":item["matchup"],
            "nba_report_team":item["team_name"],
            "nba_report_name":item["source_player_name_display"],
            "nba_report_designation":item["source_injury_designation"],
            "nba_report_original_observed_at_utc":injury_time.isoformat(),
            "nba_game_id_candidate":candidates[key]["game_id"] if key in candidates else None,
            "espn_event_id_candidate":candidates[key]["espn_id"] if key in candidates else None,
            "nba_person_id_candidate":None,"official_nba_team_id_candidate":None,
            "source_nba_roster_printed_name":None,"source_nba_roster_raw_status":None,
            "source_nba_not_playing_reason":None,
            "roster_original_raw_sha256":source_checks.get(key,{}).get("sha256"),
            "roster_original_observed_at_utc":source_checks.get(key,{}).get("observed"),
            "nba_roster_match_is_identity_candidate_only":True,
            "independently_authenticated_player_id_crosswalk":False,
            "current_game_active_inactive_verified":False,
            "draftkings_player_id_verified":False,
            "roster_status_is_final_active_list":False,
            "qualified_for_player_prop_training":False,
            "certified_prediction":False,"bet_ready":False,
            "champion_001_modified":False,
        }
        if key in problems:
            status=problems[key]
        elif key not in boxes:
            status=source_checks.get(key,{}).get("status","nba_scheduled_roster_source_missing")
        else:
            planned=candidates[key]
            side=("home" if TEAMS[nba_team_name(item["team_name"])]==TEAMS[planned["home"]]
                  else "away")
            match=boxes[key][side].get(canonical(item["source_player_name_display"]))
            if match is None:
                status="player_not_found_with_exact_same_team_name_in_official_pregame_roster"
            else:
                record["nba_person_id_candidate"]=match["person_id"]
                record["official_nba_team_id_candidate"]=match["team_id"]
                record["source_nba_roster_printed_name"]=match["printed_player_name"]
                record["source_nba_roster_raw_status"]=match["raw_game_roster_status"]
                record["source_nba_not_playing_reason"]=match["raw_not_playing_reason"]
                status=("nba_person_id_candidate_from_exact_scheduled_roster_research_only"
                        if no_espn_events else
                        "nba_person_id_candidate_with_espn_game_crosswalk_research_only")
        record["crosscheck_status"]=status
        results.append(record)
        statuses[status]+=1
    # A same-team name collision or the same person ID assigned to two source
    # player rows is unresolved; never emit a falsely unique mapped candidate.
    ids=Counter((r["nba_game_id_candidate"],r["nba_person_id_candidate"])
                for r in results if r["nba_person_id_candidate"] is not None)
    for r in results:
        key=(r["nba_game_id_candidate"],r["nba_person_id_candidate"])
        if r["nba_person_id_candidate"] and ids[key]>1:
            statuses[r["crosscheck_status"]]-=1
            r["crosscheck_status"]="same_nba_person_id_matches_multiple_injury_rows"
            r["nba_person_id_candidate"]=None
            r["official_nba_team_id_candidate"]=None
            statuses[r["crosscheck_status"]]+=1
    return results,dict(sorted((k,v) for k,v in statuses.items() if v))


def run(capture_dir, events=None, now=None, fetcher=None, clock=None,
        pdf_reader=None, max_games=MAX_GAMES):
    if type(max_games) is not int or not 1<=max_games<=MAX_GAMES:
        raise ValueError("nba_pregame_roster_game_budget_invalid")
    clock=clock or (lambda:datetime.now(timezone.utc))
    now=now or checked_clock(clock)
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("nba_roster_observation_time_naive")
    now=now.astimezone(timezone.utc)
    fetcher=fetcher or fetch_source
    pdf_reader=pdf_reader or read_original_injury_rows
    rows,filings,receipt=pdf_reader(capture_dir,events or [],now)
    # No original PDF means no index or roster request. It cannot be inferred.
    if receipt.get("original_pdf_source_status")!="captured_original_index_and_pdf":
        report=empty_report(receipt,0,"original_injury_source_not_available")
        return [],report,{}
    observed=verify_injury_evidence(rows,filings,receipt,now)
    if not rows:
        return [],empty_report(receipt,0,"no_explicit_pdf_player_entries"),{}
    index_raw=None
    schedule=None
    current=now
    schedule_source=None
    errors={}
    # Only the NBA-operated season URL first; a denied/stale/broken season
    # response may fall back to the NBA-owned same-day scoreboard. Never
    # invent game identities, bypass a blocked CDN, or use a yesterday board.
    for url in (NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL):
        try:
            candidate_raw=fetcher(url,MAX_SCHEDULE_BYTES)
            observed_after=checked_clock(clock)
            if observed_after<now or (observed_after-now).total_seconds()>90:
                raise ValueError("nba_roster_schedule_fetch_clock_invalid")
            if url==NBA_TODAY_SCOREBOARD_URL:
                candidate,_=validate_same_day_scoreboard(candidate_raw,observed_after)
            else:
                candidate=decode_json(candidate_raw,MAX_SCHEDULE_BYTES)
                if not isinstance(candidate.get("leagueSchedule"),dict):
                    raise ValueError("primary_nba_season_schedule_schema_missing")
                official_nba_events(candidate)
            index_raw=candidate_raw
            schedule=candidate
            schedule_source=url
            current=observed_after
            break
        except (OSError,ValueError,TypeError,TimeoutError,UnicodeError,
                OverflowError,KeyError) as exc:
            errors[url]=type(exc).__name__
    if schedule is None:
        report=empty_report(receipt,len(rows),"official_nba_schedule_and_daily_board_unavailable")
        report["official_nba_schedule_source_errors"]=errors
        return review_identity(rows,{},{
            (r["game_date_et"],r["matchup"]):"official_nba_future_schedule_unavailable"
            for r in rows}, {}, {}, observed,events is None)[0],report,{}
    schedule_observed=current
    candidates,problems=match_official_schedule(rows,schedule,observed,current,events)
    keys=sorted(candidates,key=lambda k:(candidates[k]["start"],candidates[k]["game_id"]))
    if len(keys)>max_games:
        for key in keys[max_games:]:
            problems[key]="outside_bounded_scheduled_roster_capture"
            del candidates[key]
        keys=keys[:max_games]
    boxes,source_meta,archive={}, {}, {"nba_official_schedule.json":index_raw}
    for key in keys:
        plan=candidates[key]
        game_id=plan["game_id"]
        try:
            raw=fetcher(official_url(game_id),MAX_BOX_BYTES)
            after=checked_clock(clock)
            if after<current or (after-current).total_seconds()>90:
                raise ValueError("nba_roster_game_fetch_clock_invalid")
            parsed=parse_pregame_nba_box(raw,plan,after)
            boxes[key]=parsed
            archive["nba_pregame_box_"+game_id+".json"]=raw
            source_meta[key]={"status":"source_parsed_scheduled_state",
                              "sha256":digest(raw),"observed":after.isoformat()}
            current=after
        except (OSError,ValueError,TypeError,TimeoutError,UnicodeError,OverflowError,KeyError) as exc:
            source_meta[key]={"status":"pregame_roster_source_blocked_"+type(exc).__name__,
                              "sha256":None,"observed":None}
    results,by_status=review_identity(rows,candidates,problems,boxes,source_meta,
                                      observed,events is None)
    report=base_report(receipt,len(rows))
    report.update({
        "official_schedule_source_available":True,
        "official_nba_schedule_source_url":schedule_source,
        "official_nba_schedule_source_kind":(
            "nba_daily_scoreboard_same_day_fallback"
            if schedule_source==NBA_TODAY_SCOREBOARD_URL
            else "nba_season_schedule"),
        "official_nba_schedule_source_errors":errors,
        "official_nba_schedule_original_sha256":digest(index_raw),
        "official_nba_schedule_observed_at_utc":schedule_observed.isoformat(),
        "official_game_requests_bounded":len(keys),
        "official_game_source_states":{candidates[k]["game_id"]:source_meta.get(k,{}).get("status")
                                       for k in keys},
        "player_identity_review_statuses":by_status,
        "nba_person_id_candidates_without_id_cross_source_authentication":
            sum(r["nba_person_id_candidate"] is not None for r in results),
        "matched_espn_game_crosswalk_candidates":
            len({v["espn_id"] for v in candidates.values() if v["espn_id"]}),
    })
    report["original_source_sha256"]={fname:digest(raw) for fname,raw in archive.items()}
    return results,report,archive


def base_report(receipt, count):
    return {
        "stage":"challenger_nba_scheduled_roster_identity_review_only",
        "source_class":SOURCE_CLASS,
        "original_nba_injury_pdf_sha256":receipt.get("original_pdf_sha256"),
        "original_pdf_player_rows":count,
        "official_nba_schedule_original_sha256":None,
        "official_schedule_source_available":False,
        "official_nba_schedule_source_url":None,
        "official_nba_schedule_source_kind":None,
        "official_nba_schedule_source_errors":{},
        "official_game_requests_bounded":0,
        "nba_person_id_candidates_without_id_cross_source_authentication":0,
        "matched_espn_game_crosswalk_candidates":0,
        "player_identity_review_statuses":{},
        "original_source_sha256":{},
        "independently_confirmed_active_players":0,
        "verified_nba_to_espn_to_draftkings_player_id_crosswalks":0,
        "qualified_player_prop_training_observations":0,
        "trained_player_prop_models":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,"automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("Scheduled NBA liveData roster is not an official final active list. "
                   "NBA person ID candidates from exact same-game/team/name matching "
                   "do not authenticate ESPN/DraftKings IDs, injury clearance, "
                   "source publication time, minutes or market settlement.")
    }


def empty_report(receipt,count,status):
    report=base_report(receipt,count)
    report["status"]=status
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir",required=True)
    p.add_argument("--events")
    p.add_argument("--output-dir",default="nba_roster_identity_research")
    p.add_argument("--max-games",type=int,default=MAX_GAMES)
    a=p.parse_args(argv)
    events=None
    if a.events:
        path=Path(a.events)
        if not path.is_file():
            raise FileNotFoundError("missing_nba_pregame_event_snapshots")
        events=[json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
                if s.strip()]
    results,report,originals=run(a.capture_dir,events,max_games=a.max_games)
    dest=Path(a.output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"nba_pregame_roster_identity_review.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in results),encoding="utf-8")
    (dest/"nba_pregame_roster_identity_report.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    if originals:
        root=dest/"nba_roster_original_source_bytes"
        root.mkdir(parents=True,exist_ok=True)
        for fname,raw in sorted(originals.items()):
            path=root/fname
            if path.exists():
                raise FileExistsError("refusing_to_overwrite_original_nba_pregame_roster")
            path.write_bytes(raw)
    print(json.dumps({
        "injury_pdf_player_rows":report["original_pdf_player_rows"],
        "nba_person_id_review_candidates":report["nba_person_id_candidates_without_id_cross_source_authentication"],
        "confirmed_active":0,"certified_player_props":0,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
