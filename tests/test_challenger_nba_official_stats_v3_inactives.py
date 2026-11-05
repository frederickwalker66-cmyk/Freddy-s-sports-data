"""NBA Stats V3 inactives: synthetic only, never certify full Active List."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_official_stats_v3_inactives import (
    run, main, parse_stats_v3, stats_url, plan,
)

NOW=datetime(2026,11,5,22,0,tzinfo=timezone.utc)
START="2026-11-05T23:00:00Z"


def schedule(gid="0022600001",start=START,status=1):
    return json.dumps({"leagueSchedule":{"leagueId":"00","gameDates":[
        {"games":[{"gameId":gid,"gameStatus":status,
                   "gameDateTimeUTC":start,
                   "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                               "teamName":"Knicks"},
                   "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                               "teamName":"Celtics"}}]}]}}).encode()


def summary(status=1,game_id="0022600001",start=START,home="Knicks",
            home_id=1610612752,away_id=1610612738,
            inactives=None,missing_home=False):
    if inactives is None:
        inactives=[{"personId":100,"firstName":"Jayson","familyName":"Tatum",
                    "jerseyNum":"0"}]
    return json.dumps({"boxScoreSummary":{
        "gameId":game_id,"gameStatus":status,"gameTimeUTC":start,
        "homeTeam":{"teamCity":"New York","teamName":home,"teamTricode":"NYK",
                    "teamId":home_id,**({} if missing_home else {"inactives":[]})},
        "awayTeam":{"teamCity":"Boston","teamName":"Celtics","teamTricode":"BOS",
                    "teamId":away_id,"inactives":inactives}}}).encode()


def base_report(raw=None, available=True):
    raw=raw or schedule()
    return {
        "stage":"challenger_nba_scheduled_roster_identity_review_only",
        "official_schedule_source_available":available,
        "official_nba_schedule_original_sha256":hashlib.sha256(raw).hexdigest() if available else None,
        "original_source_sha256":{"nba_official_schedule.json":hashlib.sha256(raw).hexdigest()} if available else {},
        "independently_confirmed_active_players":0,
        "verified_nba_to_espn_to_draftkings_player_id_crosswalks":0,
        "qualified_player_prop_training_observations":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,"automated_bets_placed":0,
        "champion_001_modified":False,
    }


def folder(root,raw=None,available=True):
    raw=raw or schedule()
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    r=base_report(raw,available)
    (root/"nba_pregame_roster_identity_report.json").write_text(json.dumps(r))
    if available:
        p=root/"nba_roster_original_source_bytes"
        p.mkdir(exist_ok=True)
        (p/"nba_official_schedule.json").write_bytes(raw)
    return r


def execute(source=None, schedule_raw=None, available=True, now=NOW):
    with TemporaryDirectory() as tmp:
        folder(tmp,schedule_raw,available)
        called=[]
        def fetch(url):
            called.append(url)
            return summary() if source is None else source
        r=run(tmp,now=now,clock=lambda:now,fetcher=fetch)
        return (*r,called)


class NBAStatsV3InactiveTests(unittest.TestCase):
    def test_explicit_nba_stats_inactive_is_not_complete_active_list(self):
        rows,r,orig,calls=execute()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["official_nba_person_id"],"100")
        self.assertEqual(rows[0]["source_inactive_name"],"Jayson Tatum")
        self.assertTrue(rows[0]["source_explicit_inactive_pregame"])
        self.assertFalse(rows[0]["confirmed_final_game_inactive"])
        self.assertFalse(rows[0]["official_final_active_list_authenticated"])
        self.assertFalse(rows[0]["all_nonlisted_players_assumed_active"])
        self.assertFalse(rows[0]["qualified_for_prop_training"])
        self.assertEqual(r["independently_confirmed_game_day_active_players"],0)
        self.assertEqual(r["independently_confirmed_game_day_inactive_players"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertEqual(r["source_requests_attempted"],1)
        self.assertEqual(calls,[stats_url("0022600001")])
        self.assertEqual(orig["0022600001"],summary())
        self.assertEqual(r["observed_game_source_sha256"]["0022600001"],
                         hashlib.sha256(summary()).hexdigest())

    def test_empty_inactive_arrays_do_not_imply_every_player_active(self):
        rows,r,orig,_=execute(source=summary(inactives=[]))
        self.assertEqual(rows,[])
        self.assertTrue(r["no_inactive_rows_does_not_mean_everyone_active"])
        self.assertEqual(r["source_responses_parsed"],1)
        self.assertEqual(r["independently_confirmed_game_day_active_players"],0)
        self.assertEqual(len(orig),1)

    def test_stats_source_missing_inactives_array_is_unusable(self):
        rows,r,orig,_=execute(source=summary(missing_home=True))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})
        self.assertEqual(orig,{})

    def test_game_id_mismatch_is_rejected(self):
        rows,r,orig,_=execute(source=summary(game_id="0022600002"))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})
        self.assertFalse(orig)

    def test_game_final_status_cannot_be_backfilled_as_pregame(self):
        rows,r,orig,_=execute(source=summary(status=3))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_responses_parsed"],0)
        self.assertEqual(r["source_failures"],{"ValueError":1})
        self.assertFalse(orig)

    def test_game_in_progress_status_is_also_rejected(self):
        rows,r,orig,_=execute(source=summary(status=2))
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_game_start_clock_mismatch_rejected(self):
        rows,r,_,_=execute(source=summary(start="2026-11-05T23:15:00Z"))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_team_name_mismatch_rejected(self):
        rows,r,_,_=execute(source=summary(home="Lakers"))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_team_id_mismatch_rejected(self):
        rows,r,_,_=execute(source=summary(home_id=1610612747))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_duplicate_player_id_in_same_inactive_list_rejected(self):
        p={"personId":100,"firstName":"Jayson","familyName":"Tatum"}
        rows,r,_,_=execute(source=summary(inactives=[p,p]))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_missing_person_id_rejected(self):
        rows,r,_,_=execute(source=summary(inactives=[
            {"personId":None,"firstName":"Jayson","familyName":"Tatum"}]))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_missing_player_name_rejected(self):
        rows,r,_,_=execute(source=summary(inactives=[
            {"personId":100,"firstName":"","familyName":""}]))
        self.assertEqual(rows,[])
        self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_stats_endpoint_access_denied_keeps_no_fake_rows(self):
        with TemporaryDirectory() as tmp:
            folder(tmp)
            def fail(url):
                raise OSError("no HTTP permission")
            rows,r,raw=run(tmp,now=NOW,clock=lambda:NOW,fetcher=fail)
        self.assertEqual(rows,[])
        self.assertEqual(raw,{})
        self.assertEqual(r["status"],"source_denied_or_not_ready")
        self.assertEqual(r["source_failures"],{"OSError":1})

    def test_no_game_inside_120min_prevents_any_http_calls(self):
        rows,r,raw,calls=execute(now=datetime(2026,11,5,18,tzinfo=timezone.utc))
        self.assertEqual(rows,[])
        self.assertEqual(calls,[])
        self.assertEqual(r["eligible_scheduled_games"],0)
        self.assertEqual(r["status"],"no_upcoming_game_inside_120min_window")

    def test_at_or_after_tipoff_cannot_request_past_game(self):
        rows,r,raw,calls=execute(now=datetime(2026,11,5,23,tzinfo=timezone.utc))
        self.assertEqual(rows,[])
        self.assertEqual(calls,[])
        self.assertEqual(r["source_requests_attempted"],0)

    def test_empty_upstream_schedule_avoids_http(self):
        rows,r,raw,calls=execute(available=False)
        self.assertEqual(rows,[])
        self.assertEqual(r["status"],"original_nba_schedule_unavailable_no_requests")
        self.assertEqual(calls,[])

    def test_changed_archived_schedule_bytes_hard_rejected(self):
        with TemporaryDirectory() as tmp:
            folder(tmp)
            p=Path(tmp)/"nba_roster_original_source_bytes"/"nba_official_schedule.json"
            p.write_bytes(p.read_bytes()+b"garbage")
            with self.assertRaisesRegex(ValueError,"altered_nba_original_schedule_bytes"):
                run(tmp,now=NOW,clock=lambda:NOW,fetcher=lambda x:summary())

    def test_promoted_input_report_rejected_before_network(self):
        with TemporaryDirectory() as tmp:
            r=folder(tmp)
            r["certified_positive_ev_bets"]=1
            (Path(tmp)/"nba_pregame_roster_identity_report.json").write_text(json.dumps(r))
            called=[]
            with self.assertRaisesRegex(ValueError,"promoted_nba_inactive_input"):
                run(tmp,now=NOW,clock=lambda:NOW,fetcher=lambda url:called.append(url))
            self.assertEqual(called,[])

    def test_fetch_finish_after_tipoff_discards_source_bytes(self):
        with TemporaryDirectory() as tmp:
            folder(tmp)
            seq=iter([datetime(2026,11,5,23,1,tzinfo=timezone.utc)])
            rows,r,orig=run(tmp,now=NOW,clock=lambda:next(seq),fetcher=lambda url:summary())
            self.assertEqual(rows,[])
            self.assertEqual(orig,{})
            self.assertEqual(r["source_failures"],{"ValueError":1})

    def test_invalid_stats_source_json_is_not_promoted(self):
        rows,r,raw,_=execute(source=b'not JSON')
        self.assertEqual(rows,[])
        self.assertFalse(raw)
        self.assertEqual(r["source_failures"],{"JSONDecodeError":1})

    def test_explicit_inactive_is_preliminary_not_bookmaker_dnp(self):
        rows,r,_,_=execute()
        self.assertFalse(rows[0]["bookmaker_prop_eligibility_verified"])
        self.assertFalse(rows[0]["player_participation_or_dnp_verified"])
        self.assertIsNone(rows[0]["model_probability"])
        self.assertEqual(r["automated_bets_placed"],0)
        self.assertFalse(r["champion_001_modified"])

    def test_cli_unavailable_upstream_still_writes_research_report(self):
        with TemporaryDirectory() as tmp:
            folder(tmp,available=False)
            out=Path(tmp)/"out"
            self.assertEqual(main(["--roster-dir",tmp,"--output-dir",str(out)]),0)
            r=json.loads((out/"nba_stats_v3_inactive_report.json").read_text())
            self.assertEqual(r["source_requests_attempted"],0)
            self.assertEqual(r["certified_champion_001_predictions"],0)
            self.assertFalse((out/"nba_stats_v3_original_source_bytes").exists())


if __name__=="__main__":
    unittest.main()
