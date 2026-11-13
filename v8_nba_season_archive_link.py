"""Attach full-season source-only NBA last-5 and last-10 to the V8 slate.

Never alters previously recorded Elo probability, current-roster claims,
bookmaker odds, player-prop model p or Champion-001. Source artifacts
must be from a prior completed run with original published-score receipt
timestamps <= the current as-of clock. No file means explicit N/A.
"""
from __future__ import annotations
import json
from pathlib import Path

from historical_outcomes import parse_time
from v8_all_sports_season_form import build_season_game_form
from v8_all_sports_player_form import build_all_player_form

MAX_SCORE_BYTES=12_000_000
MAX_PLAYER_BYTES=100_000_000


def _read(path,cap):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>cap:
        raise ValueError("season_snapshot_file_missing_or_too_large")
    if path.suffix==".jsonl":
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
                if x.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def link_saved_nba_season(slate, as_of_utc, source_dir, output_dir):
    at=parse_time(as_of_utc.isoformat() if hasattr(as_of_utc,"isoformat")
                  else as_of_utc)
    if source_dir is None:
        return {"status":"NOT_YET_COLLECTED","source_season_artifact_available":False,
                "complete_team_last5":0,"complete_team_last10":0,
                "complete_player_last5":0,"complete_player_last10":0,
                "champion_001_modified":False,"certified_positive_ev_bets":0}
    folder=Path(source_dir)
    try:
        coverage=_read(folder/"SEASON_COVERAGE.json",MAX_SCORE_BYTES)
        player_cov=_read(folder/"player_boxes"/"PLAYER_BOX_COVERAGE.json",MAX_SCORE_BYTES)
        scores=_read(folder/"SEASON_RESULTS.jsonl",MAX_SCORE_BYTES)
        players=_read(folder/"player_boxes"/"PLAYER_BOX_HISTORY.jsonl",MAX_PLAYER_BYTES)
        if (coverage.get("league")!="nba" or player_cov.get("league")!="nba"
                or coverage.get("champion_001_modified") is not False
                or player_cov.get("champion_001_modified") is not False
                or parse_time(coverage["as_of_utc"])>at
                or parse_time(player_cov["as_of_utc"])>at
                or coverage["conservative_collection_anchor_et"]!=
                   player_cov["season_anchor_et"]):
            raise ValueError("untrusted_or_future_NBA_season_artifact")
        if not isinstance(slate,list):
            raise ValueError("NBA_slate_list_required")
        future=[]
        for g in slate:
            if not isinstance(g,dict):
                raise ValueError("invalid_NBA_slate_game")
            tip=parse_time(g["start_utc"])
            if tip<=at or g.get("source_event_state")!="pre":
                continue
            home,away=g.get("home_team_id"),g.get("away_team_id")
            if (not isinstance(home,str) or not isinstance(away,str)
                    or not home.isdecimal() or not away.isdecimal()):
                raise ValueError("missing_NBA_ESPN_team_identity")
            future.append({
                "league":"nba","espn_event_id":g["espn_event_id"],
                "home_team_espn_id":home,"away_team_espn_id":away,
                "start_utc":g["start_utc"],
            })
        game=build_season_game_form(
            scores,future,at,{"nba":coverage})
        # A historically observed player's old team ID does NOT establish
        # today's active roster. These targets are research candidates only.
        teamids={(g["espn_event_id"],tid) for g in future
                 for tid in (g["home_team_espn_id"],g["away_team_espn_id"])}
        candidates={}
        for row in players:
            if not isinstance(row,dict) or row.get("league")!="nba":
                raise ValueError("other_sport_in_NBA_player_history")
            for eid,tid in teamids:
                if row.get("espn_team_id")==tid and row.get("did_not_play") is False:
                    candidates[(eid,row["espn_player_id"])]={
                        "league":"nba","espn_event_id":eid,
                        "espn_player_id":row["espn_player_id"],
                        "start_utc":next(g["start_utc"] for g in future
                                         if g["espn_event_id"]==eid),
                    }
        p=build_all_player_form(players,list(candidates.values()),
                                at,{"nba":coverage})
        dest=Path(output_dir)
        dest.mkdir(parents=True,exist_ok=True)
        (dest/"NBA_SEASON_MATCHUP_LAST5_LAST10.json").write_text(
            json.dumps(game,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        (dest/"NBA_SEASON_PLAYER_LAST5_LAST10.json").write_text(
            json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        game_views=game["fixtures"].values()
        pv=p["players_by_event"].values()
        status={
            "status":"SOURCE_ONLY_SEASON_L5_L10_NOT_A_BET",
            "source_season_artifact_available":True,
            "source_day_coverage_complete":coverage.get("source_coverage_complete"),
            "player_boxscore_game_coverage_complete":
                player_cov.get("player_boxscore_event_coverage_complete"),
            "slate_future_games_with_history":len(game["fixtures"]),
            "historical_ESPN_player_ID_candidates_NOT_roster_verified":len(pv),
            "complete_team_last5":sum(
                v["home"]["last5"]["complete_window"]+
                v["away"]["last5"]["complete_window"] for v in game_views),
            "complete_team_last10":sum(
                v["home"]["last10"]["complete_window"]+
                v["away"]["last10"]["complete_window"] for v in game["fixtures"].values()),
            "complete_player_last5":sum(
                v["last5"]["complete_window_for_sport_stats"] for v in pv),
            "complete_player_last10":sum(
                v["last10"]["complete_window_for_sport_stats"]
                for v in p["players_by_event"].values()),
            "historical_props_are_not_forward_probabilities":True,
            "sgo_price_to_ESPN_player_identity_not_verified":True,
            "certified_positive_ev_bets":0,"champion_001_modified":False,
        }
        return status
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
        return {
            "status":"HOLD_SEASON_ARTIFACT_VALIDATION_ERROR",
            "failure_class":type(exc).__name__,
            "source_season_artifact_available":False,
            "complete_team_last5":0,"complete_team_last10":0,
            "complete_player_last5":0,"complete_player_last10":0,
            "certified_positive_ev_bets":0,"champion_001_modified":False,
        }
