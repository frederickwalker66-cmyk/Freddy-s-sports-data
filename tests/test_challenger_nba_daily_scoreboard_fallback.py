"""Fail-closed NBA daily scoreboard fallback, original NBA identities and Stats V3 path."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_daily_scoreboard_fallback import (
    validate_same_day_scoreboard, source_game_records,
)
from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL,
)
from challenger_nba_pregame_roster_identity import (
    run as roster_run, MAX_SCHEDULE_BYTES, MAX_BOX_BYTES,
)
from challenger_nba_official_stats_v3_inactives import (
    run as inactive_run, verify_inputs,
)

NOW=datetime(2026,11,5,22,0,tzinfo=timezone.utc)
GAME_START="2026-11-05T23:00:00Z"
GAME_ID="0022600001"


def game(status=1,start=GAME_START,home="Knicks",home_id=1610612752):
    return {
        "gameId":GAME_ID,"gameStatus":status,"gameTimeUTC":start,
        "homeTeam":{"teamId":home_id,"teamCity":"New York","teamName":home},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston","teamName":"Celtics"},
    }


def board(day="2026-11-05",league="00",games=None):
    if games is None:games=[game()]
    return json.dumps({"meta":{"version":1},"scoreboard":{
        "gameDate":day,"leagueId":league,"games":games
    }}).encode()


def official_box():
    return json.dumps({"game":{
        "gameId":GAME_ID,"gameStatus":1,"gameTimeUTC":GAME_START,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":"Knicks","teamTricode":"NYK",
                    "players":[{"personId":200,"name":"Jalen Brunson",
                                "status":"ACTIVE","notPlayingReason":None}]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS",
                    "players":[{"personId":100,"name":"Jayson Tatum",
                                "status":"INACTIVE","notPlayingReason":"Injury"}]}
    }}).encode()


def stats_v3():
    return json.dumps({"boxScoreSummary":{
        "gameId":GAME_ID,"gameStatus":1,"gameTimeUTC":GAME_START,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":"Knicks","teamTricode":"NYK","inactives":[]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS","inactives":[
                        {"personId":100,"firstName":"Jayson","familyName":"Tatum"}]}
    }}).encode()


def injury():
    return {
        "record_type":"nba_official_pdf_player_status_extracted_for_review_only",
        "game_date_et":"2026-11-05","matchup":"BOS@NYK",
        "team_name":"Boston Celtics","nba_team_abbreviation":"BOS",
        "source_player_name_display":"Jayson Tatum",
        "source_injury_designation":"Out",
        "nba_person_id":None,"espn_athlete_id":None,
        "player_current_game_active_status_verified":False,
        "roster_player_id_crosswalk_verified":False,
        "qualified_for_prop_training":False,
        "market_eligibility_verified":False,
        "certified_prediction":False,"bet_ready":False,
        "champion_001_modified":False,
    }


def injury_report():
    return {
        "stage":"challenger_nba_official_pregame_pdf_player_rows_review_only",
        "original_pdf_source_status":"captured_original_index_and_pdf",
        "pdf_extraction_error":None,
        "original_pdf_sha256":"a"*64,
        "actual_original_pdf_observed_utc":"2026-11-05T21:45:00Z",
        "player_rows_extracted_from_official_pdf":1,
        "teams_report_not_yet_submitted":0,
        "active_player_roster_verified":0,
        "individual_player_id_crosswalk_verified":0,
        "qualified_prop_training_observations":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,
        "champion_001_modified":False,
    }


def read_original(folder,events,at):
    return [injury()],[],injury_report()


def capture(source=None, bad_season=True, calls=None):
    def fetch(url,cap):
        if calls is not None:calls.append(url)
        if url == NBA_SCHEDULE_URL:
            if bad_season:raise OSError("season schedule unavailable")
            # Return a valid season source to verify no unnecessary fallback.
            return json.dumps({"leagueSchedule":{"leagueId":"00",
                "gameDates":[{"games":[{
                    **game(),
                    "gameDateTimeUTC":GAME_START,
                }]}]}}).encode()
        if url == NBA_TODAY_SCOREBOARD_URL:
            if cap != MAX_SCHEDULE_BYTES:raise AssertionError("wrong schedule limit")
            return board() if source is None else source
        if url.endswith("boxscore_"+GAME_ID+".json"):
            if cap!=MAX_BOX_BYTES:raise AssertionError("wrong boxscore limit")
            return official_box()
        raise AssertionError("unexpected network address " + url)
    return fetch


def save_source(directory,report,originals):
    root=Path(directory)
    root.mkdir(parents=True,exist_ok=True)
    (root/"nba_pregame_roster_identity_report.json").write_text(json.dumps(report))
    (root/"nba_pregame_roster_identity_review.jsonl").write_text("")
    if originals:
        data=root/"nba_roster_original_source_bytes"
        data.mkdir(exist_ok=True)
        for name,raw in originals.items():
            (data/name).write_bytes(raw)


class DailyBoardFallbackTests(unittest.TestCase):
    def test_same_day_nba_daily_scoreboard_has_exact_future_game(self):
        data,upcoming=validate_same_day_scoreboard(board(),NOW)
        self.assertEqual(data["scoreboard"]["leagueId"],"00")
        self.assertEqual(len(upcoming),1)
        self.assertEqual(upcoming[0]["official_nba_game_id"],GAME_ID)
        ids,kind=source_game_records(data)
        self.assertEqual(kind,"nba_daily_scoreboard_same_day_fallback")
        self.assertEqual(ids[GAME_ID],{"home":"1610612752","away":"1610612738"})

    def test_yesterdays_scoreboard_cannot_be_used_as_todays_pregame(self):
        with self.assertRaisesRegex(ValueError,"stale_or_wrong_league"):
            validate_same_day_scoreboard(board(day="2026-11-04"),NOW)

    def test_future_day_scoreboard_also_blocked(self):
        with self.assertRaisesRegex(ValueError,"stale_or_wrong_league"):
            validate_same_day_scoreboard(board(day="2026-11-06"),NOW)

    def test_wrong_league_rejected(self):
        with self.assertRaisesRegex(ValueError,"stale_or_wrong_league"):
            validate_same_day_scoreboard(board(league="01"),NOW)

    def test_duplicate_nba_game_id_fails_whole_scoreboard(self):
        g=game()
        with self.assertRaisesRegex(ValueError,"duplicate_or_invalid"):
            validate_same_day_scoreboard(board(games=[g,deepcopy(g)]),NOW)

    def test_duplicate_nba_team_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"same_team"):
            validate_same_day_scoreboard(board(games=[game(home_id=1610612738)]),NOW)

    def test_wrong_team_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"team_identity_not_official"):
            validate_same_day_scoreboard(board(games=[game(home="UnknownClub")]),NOW)

    def test_invalid_scoreboard_schema_fails(self):
        with self.assertRaisesRegex(ValueError,"unrecognized_nba_daily"):
            validate_same_day_scoreboard(b'{"scoreboard": null}',NOW)

    def test_finished_game_does_not_become_pregame(self):
        _,upcoming=validate_same_day_scoreboard(board(games=[game(status=3)]),NOW)
        self.assertEqual(upcoming,[])

    def test_scheduled_game_with_past_kickoff_not_used_as_future(self):
        _,upcoming=validate_same_day_scoreboard(
            board(games=[game(start="2026-11-05T21:00:00Z")]),NOW)
        self.assertEqual(upcoming,[])

    def test_morning_official_board_with_no_games_is_valid_empty_not_fake(self):
        _,upcoming=validate_same_day_scoreboard(board(games=[]),NOW)
        self.assertEqual(upcoming,[])

    def test_season_source_identity_extraction_still_supported(self):
        season=json.loads(capture(bad_season=False)(NBA_SCHEDULE_URL,MAX_SCHEDULE_BYTES))
        byid,kind=source_game_records(season)
        self.assertEqual(kind,"nba_season_schedule")
        self.assertEqual(byid[GAME_ID]["home"],"1610612752")

    def test_roster_collector_uses_daily_board_when_season_source_denied(self):
        calls=[]
        rows,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                               pdf_reader=read_original,fetcher=capture(calls=calls))
        self.assertEqual(calls[:2],[NBA_SCHEDULE_URL,NBA_TODAY_SCOREBOARD_URL])
        self.assertEqual(r["official_nba_schedule_source_url"],NBA_TODAY_SCOREBOARD_URL)
        self.assertEqual(r["official_nba_schedule_source_kind"],
                         "nba_daily_scoreboard_same_day_fallback")
        self.assertEqual(r["official_nba_schedule_source_errors"],
                         {NBA_SCHEDULE_URL:"OSError"})
        self.assertEqual(rows[0]["nba_person_id_candidate"],"100")
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nba_person_id_candidate_from_exact_scheduled_roster_research_only")
        self.assertEqual(r["official_game_requests_bounded"],1)
        self.assertEqual(files["nba_official_schedule.json"],board())
        self.assertEqual(r["official_nba_schedule_original_sha256"],
                         hashlib.sha256(board()).hexdigest())
        self.assertEqual(r["independently_confirmed_active_players"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_valid_season_schedule_does_not_ask_for_daily_board(self):
        calls=[]
        _,r,_=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                         pdf_reader=read_original,
                         fetcher=capture(bad_season=False,calls=calls))
        self.assertEqual(calls[0],NBA_SCHEDULE_URL)
        self.assertNotIn(NBA_TODAY_SCOREBOARD_URL,calls)
        self.assertEqual(r["official_nba_schedule_source_kind"],"nba_season_schedule")

    def test_stale_board_fail_closed_and_no_individual_game_request(self):
        calls=[]
        rows,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
             pdf_reader=read_original,
             fetcher=capture(source=board(day="2026-11-04"),calls=calls))
        self.assertEqual(calls,[NBA_SCHEDULE_URL,NBA_TODAY_SCOREBOARD_URL])
        self.assertEqual(r["official_game_requests_bounded"],0)
        self.assertEqual(files,{})
        self.assertIsNone(rows[0]["nba_person_id_candidate"])
        self.assertEqual(r["status"],"official_nba_schedule_and_daily_board_unavailable")

    def test_stats_v3_inactive_stage_reads_verified_daily_scoreboard_receipt(self):
        rows,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                               pdf_reader=read_original,fetcher=capture())
        with TemporaryDirectory() as tmp:
            save_source(tmp,r,files)
            source_calls=[]
            def fetch_v3(url):
                source_calls.append(url)
                return stats_v3()
            inactive,rep,raw=inactive_run(tmp,now=NOW,clock=lambda:NOW,fetcher=fetch_v3)
        self.assertEqual(len(inactive),1)
        self.assertEqual(inactive[0]["official_nba_person_id"],"100")
        self.assertEqual(rep["upstream_nba_game_identity_source"],
                         "nba_daily_scoreboard_same_day_fallback")
        self.assertEqual(rep["source_requests_attempted"],1)
        self.assertEqual(rep["source_responses_parsed"],1)
        self.assertEqual(len(source_calls),1)
        self.assertEqual(raw[GAME_ID],stats_v3())
        self.assertFalse(inactive[0]["official_final_active_list_authenticated"])
        self.assertEqual(rep["certified_positive_ev_bets"],0)

    def test_stats_v3_stale_daily_scoreboard_receipt_blocks_without_fetch(self):
        _,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                             pdf_reader=read_original,fetcher=capture())
        r["official_nba_schedule_observed_at_utc"]="2026-11-05T19:00:00Z"
        with TemporaryDirectory() as tmp:
            save_source(tmp,r,files)
            called=[]
            with self.assertRaisesRegex(ValueError,"stale_daily_scoreboard_receipt"):
                inactive_run(tmp,now=NOW,clock=lambda:NOW,
                             fetcher=lambda url:called.append(url))
            self.assertEqual(called,[])

    def test_daily_receipt_crossing_midnight_et_cannot_reuse_yesterdays_board(self):
        _,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                             pdf_reader=read_original,fetcher=capture())
        # Original source snapshot is 11:58pm ET; a replay after midnight
        # is prohibited even though the timestamp is only 3 minutes old.
        r["official_nba_schedule_observed_at_utc"]="2026-11-06T04:58:00Z"
        later=datetime(2026,11,6,5,1,tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            save_source(tmp,r,files)
            called=[]
            with self.assertRaisesRegex(ValueError,"stale_daily_scoreboard_receipt"):
                inactive_run(tmp,now=later,clock=lambda:later,
                             fetcher=lambda url:called.append(url))
            self.assertEqual(called,[])

    def test_stats_v3_forged_daily_source_kind_is_rejected(self):
        _,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                             pdf_reader=read_original,fetcher=capture())
        r["official_nba_schedule_source_kind"]="nba_season_schedule"
        with TemporaryDirectory() as tmp:
            save_source(tmp,r,files)
            with self.assertRaisesRegex(ValueError,"source_kind_mismatch"):
                inactive_run(tmp,now=NOW,clock=lambda:NOW,fetcher=lambda x:stats_v3())

    def test_stats_v3_tampered_original_scoreboard_hash_rejected(self):
        _,r,files=roster_run("synthetic",now=NOW,clock=lambda:NOW,
                             pdf_reader=read_original,fetcher=capture())
        with TemporaryDirectory() as tmp:
            save_source(tmp,r,files)
            with open(Path(tmp)/"nba_roster_original_source_bytes"/"nba_official_schedule.json","ab") as out:
                out.write(b"x")
            with self.assertRaisesRegex(ValueError,"altered_nba_original_schedule_bytes"):
                inactive_run(tmp,now=NOW,clock=lambda:NOW,fetcher=lambda x:stats_v3())


if __name__=="__main__":
    unittest.main()
