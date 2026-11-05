"""Offline-only NBA-operated Stats ScoreboardV3 third-source validation tests."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from unittest.mock import patch
import unittest

from challenger_nba_stats_v3_schedule_fallback import (
    stats_url_for_observation, verify_stats_v3_scoreboard,
)
from challenger_nba_pregame_roster_identity import (
    run as roster_run, fetch_source, NBA_SCHEDULE_URL,
    NBA_TODAY_SCOREBOARD_URL, MAX_SCHEDULE_BYTES,
)
from challenger_nba_official_stats_v3_inactives import run as inactive_run

NOW = datetime(2026,11,5,22,0,tzinfo=timezone.utc)
GID="0022600001"
TIP="2026-11-05T23:00:00Z"


def game(status=1, gid=GID, start=TIP, home="Knicks"):
    return {
        "gameId":gid,"gameStatus":status,"gameTimeUTC":start,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York","teamName":home},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston","teamName":"Celtics"},
    }


def stats_board(day="2026-11-05", league="00", games=None):
    return json.dumps({"meta":{"version":3},"scoreboard":{
        "gameDate":day,"leagueId":league,"games":[game()] if games is None else games
    }}).encode("utf8")


def nba_box():
    return json.dumps({"game":{
        "gameId":GID,"gameStatus":1,"gameTimeUTC":TIP,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":"Knicks","teamTricode":"NYK",
                    "players":[{"personId":200,"name":"Jalen Brunson",
                                "status":"ACTIVE","notPlayingReason":None}]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS",
                    "players":[{"personId":100,"name":"Jayson Tatum",
                                "status":"INACTIVE","notPlayingReason":"Injury"}]},
    }}).encode("utf8")


def inactive_box():
    return json.dumps({"boxScoreSummary":{
        "gameId":GID,"gameStatus":1,"gameTimeUTC":TIP,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":"Knicks","teamTricode":"NYK","inactives":[]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS",
                    "inactives":[{"personId":100,"firstName":"Jayson",
                                  "familyName":"Tatum"}]},
    }}).encode("utf8")


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


def injury_reader(path, events, now):
    return [injury()],[],{
        "stage":"challenger_nba_official_pregame_pdf_player_rows_review_only",
        "original_pdf_source_status":"captured_original_index_and_pdf",
        "pdf_extraction_error":None,"original_pdf_sha256":"a"*64,
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


def source_fetch(board=None, calls=None, deny_stats=False):
    if board is None:
        board=stats_board()
    def fetch(url, cap):
        if calls is not None:
            calls.append(url)
        if url in (NBA_SCHEDULE_URL,NBA_TODAY_SCOREBOARD_URL):
            raise HTTPError(url,403,"Forbidden",None,None)
        if url==stats_url_for_observation(NOW):
            if deny_stats:raise HTTPError(url,403,"Forbidden",None,None)
            if cap!=MAX_SCHEDULE_BYTES:raise AssertionError("wrong source byte cap")
            return board
        if url.endswith("boxscore_"+GID+".json"):
            return nba_box()
        raise AssertionError("unapproved fixture source called")
    return fetch


def run_roster(board=None, calls=None, deny_stats=False):
    return roster_run("synthetic",now=NOW,clock=lambda:NOW,pdf_reader=injury_reader,
                      fetcher=source_fetch(board,calls,deny_stats))


def save_roster(folder, report, raw):
    root=Path(folder)
    (root/"nba_pregame_roster_identity_report.json").write_text(json.dumps(report))
    d=root/"nba_roster_original_source_bytes"
    d.mkdir()
    for filename,data in raw.items():
        (d/filename).write_bytes(data)


class StatsV3ScoreboardFallbackTests(unittest.TestCase):
    def test_stats_url_pinned_to_real_eastern_day(self):
        self.assertEqual(stats_url_for_observation(NOW),
                         "https://stats.nba.com/stats/scoreboardv3?GameDate=2026-11-05&LeagueID=00")

    def test_stats_url_uses_eastern_day_near_utc_midnight(self):
        self.assertIn("2026-11-05",stats_url_for_observation(
            datetime(2026,11,6,1,0,tzinfo=timezone.utc)))

    def test_url_requires_aware_source_clock(self):
        with self.assertRaisesRegex(ValueError,"aware_observation"):
            stats_url_for_observation(datetime(2026,11,5))

    def test_exact_stats_endpoint_and_original_bytes_yield_one_scheduled_game(self):
        p,g=verify_stats_v3_scoreboard(stats_board(),stats_url_for_observation(NOW),NOW)
        self.assertEqual(p["scoreboard"]["leagueId"],"00")
        self.assertEqual(len(g),1)
        self.assertEqual(g[0]["official_nba_game_id"],GID)

    def test_wrong_source_date_url_is_rejected_before_data_parse(self):
        with self.assertRaisesRegex(ValueError,"source_not_for_observed_eastern_date"):
            verify_stats_v3_scoreboard(
                stats_board(),"https://stats.nba.com/stats/scoreboardv3?GameDate=2026-11-04&LeagueID=00",NOW)

    def test_stale_date_in_stats_payload_is_not_future_pregame(self):
        with self.assertRaisesRegex(ValueError,"stale_or_wrong_league"):
            verify_stats_v3_scoreboard(stats_board(day="2026-11-04"),
                                       stats_url_for_observation(NOW),NOW)

    def test_stats_payload_wrong_league_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"stale_or_wrong_league"):
            verify_stats_v3_scoreboard(stats_board(league="01"),
                                       stats_url_for_observation(NOW),NOW)

    def test_duplicate_game_ids_invalid_even_if_both_scheduled(self):
        same=game()
        with self.assertRaisesRegex(ValueError,"duplicate_or_invalid"):
            verify_stats_v3_scoreboard(stats_board(games=[same,dict(same)]),
                                       stats_url_for_observation(NOW),NOW)

    def test_in_progress_game_never_treated_as_future_scheduled(self):
        _,future=verify_stats_v3_scoreboard(stats_board(games=[game(status=2)]),
                                          stats_url_for_observation(NOW),NOW)
        self.assertEqual(future,[])

    def test_both_nba_cdn_denials_proceed_to_exact_stats_api(self):
        called=[]
        rows,r,original=run_roster(calls=called)
        self.assertEqual(called[:3],[NBA_SCHEDULE_URL,NBA_TODAY_SCOREBOARD_URL,
                                     stats_url_for_observation(NOW)])
        self.assertEqual(r["official_nba_schedule_source_kind"],
                         "nba_stats_v3_scoreboard_same_day_fallback")
        self.assertEqual(r["official_nba_schedule_source_url"],
                         stats_url_for_observation(NOW))
        self.assertEqual(r["official_nba_schedule_source_errors"],{
            NBA_SCHEDULE_URL:"HTTP_403",NBA_TODAY_SCOREBOARD_URL:"HTTP_403",
        })
        self.assertEqual(r["official_nba_schedule_original_sha256"],
                         hashlib.sha256(stats_board()).hexdigest())
        self.assertEqual(original["nba_official_schedule.json"],stats_board())
        self.assertEqual(rows[0]["nba_person_id_candidate"],"100")
        self.assertEqual(r["independently_confirmed_active_players"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_downstream_stats_inactive_stage_accepts_verified_stats_scoreboard(self):
        _,r,original=run_roster()
        with TemporaryDirectory() as tmp:
            save_roster(tmp,r,original)
            called=[]
            def fetch(url):
                called.append(url)
                return inactive_box()
            rows,report,files=inactive_run(
                tmp,now=NOW,clock=lambda:NOW,fetcher=fetch)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["official_nba_person_id"],"100")
        self.assertEqual(report["upstream_nba_game_identity_source"],
                         "nba_stats_v3_scoreboard_same_day_fallback")
        self.assertEqual(report["source_responses_parsed"],1)
        self.assertEqual(len(called),1)
        self.assertEqual(files[GID],inactive_box())
        self.assertFalse(rows[0]["confirmed_final_game_inactive"])
        self.assertEqual(report["certified_positive_ev_bets"],0)

    def test_after_midnight_eastern_old_scoreboard_not_replayed(self):
        _,r,original=run_roster()
        after=datetime(2026,11,6,5,1,tzinfo=timezone.utc)
        # Verify that a re-used previous-day source is rejected before HTTP.
        r["official_nba_schedule_observed_at_utc"]="2026-11-06T04:58:00Z"
        with TemporaryDirectory() as tmp:
            save_roster(tmp,r,original)
            called=[]
            with self.assertRaisesRegex(ValueError,"stale_daily_scoreboard_receipt"):
                inactive_run(tmp,now=after,clock=lambda:after,
                             fetcher=lambda url:called.append(url))
            self.assertEqual(called,[])

    def test_forged_stats_source_url_or_kind_rejected(self):
        _,r,original=run_roster()
        r["official_nba_schedule_source_kind"]="nba_season_schedule"
        with TemporaryDirectory() as tmp:
            save_roster(tmp,r,original)
            with self.assertRaisesRegex(ValueError,"source_kind_mismatch"):
                inactive_run(tmp,now=NOW,clock=lambda:NOW,
                             fetcher=lambda url:inactive_box())

    def test_denied_stats_source_produces_zero_ids_without_fake_stats(self):
        called=[]
        rows,r,files=run_roster(calls=called,deny_stats=True)
        self.assertEqual(len(called),3)
        self.assertEqual(r["status"],"official_nba_all_three_operated_schedules_unavailable")
        self.assertEqual(r["official_nba_schedule_source_errors"][
            stats_url_for_observation(NOW)],"HTTP_403")
        self.assertEqual(files,{})
        self.assertIsNone(rows[0]["nba_person_id_candidate"])
        self.assertEqual(r["certified_champion_001_predictions"],0)

    def test_stats_fetch_source_headers_are_explicit_and_safe(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return stats_board()
        captured=[]
        def opener(req,timeout):
            captured.append(req)
            return Response()
        with patch("challenger_nba_pregame_roster_identity.urlopen",side_effect=opener):
            data=fetch_source(stats_url_for_observation(NOW),MAX_SCHEDULE_BYTES)
        self.assertEqual(data,stats_board())
        self.assertEqual(captured[0].get_header("X-nba-stats-origin"),"stats")
        self.assertEqual(captured[0].get_header("X-nba-stats-token"),"true")

    def test_tampered_original_stats_scoreboard_bytes_block_downstream(self):
        _,r,original=run_roster()
        with TemporaryDirectory() as tmp:
            save_roster(tmp,r,original)
            path=Path(tmp)/"nba_roster_original_source_bytes"/"nba_official_schedule.json"
            path.write_bytes(path.read_bytes()+b"X")
            with self.assertRaisesRegex(ValueError,"altered_nba_original_schedule_bytes"):
                inactive_run(tmp,now=NOW,clock=lambda:NOW,
                             fetcher=lambda url:inactive_box())


if __name__=="__main__":
    unittest.main()
