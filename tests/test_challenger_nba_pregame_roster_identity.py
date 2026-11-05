"""Synthetic-only NBA scheduled roster ID crosswalk tests; never certify active players."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_pregame_roster_identity import (
    MAX_BOX_BYTES, MAX_SCHEDULE_BYTES, NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, official_url,
    parse_pregame_nba_box, run, main,
)

NOW = datetime(2026,11,5,14,0,tzinfo=timezone.utc)
START = "2026-11-05T23:00:00Z"


def injury(player="Jayson Tatum", designation="Questionable", club="BOS"):
    return {
        "record_type":"nba_official_pdf_player_status_extracted_for_review_only",
        "game_date_et":"2026-11-05","matchup":"BOS@NYK",
        "team_name":"Boston Celtics" if club=="BOS" else "New York Knicks",
        "nba_team_abbreviation":club,
        "source_player_name_display":player,
        "source_injury_designation":designation,
        "nba_person_id":None,"espn_athlete_id":None,
        "player_current_game_active_status_verified":False,
        "roster_player_id_crosswalk_verified":False,
        "qualified_for_prop_training":False,
        "market_eligibility_verified":False,
        "certified_prediction":False,
        "bet_ready":False,"champion_001_modified":False,
    }


def filing():
    return {
        "record_type":"nba_official_pdf_team_report_not_submitted_research_only",
        "game_date_et":"2026-11-05","matchup":"BOS@NYK",
        "team_name":"New York Knicks","team_abbreviation":"NYK",
        "filing_status":"not_yet_submitted",
        "confirmed_all_players_available":False,
        "player_clearance_count":0,
        "bet_ready":False,"champion_001_modified":False,
    }


def receipt(rows=1, filings=0, pdf_observed="2026-11-05T13:00:00Z", source=True):
    return {
        "stage":"challenger_nba_official_pregame_pdf_player_rows_review_only",
        "original_pdf_source_status":
            "captured_original_index_and_pdf" if source else "blocked_OSError",
        "pdf_extraction_error":None if source else "original_nba_pdf_not_captured",
        "original_pdf_sha256":"a"*64,
        "actual_original_pdf_observed_utc":pdf_observed,
        "player_rows_extracted_from_official_pdf":rows,
        "teams_report_not_yet_submitted":filings,
        "active_player_roster_verified":0,
        "individual_player_id_crosswalk_verified":0,
        "qualified_prop_training_observations":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,
        "champion_001_modified":False,
    }


def official_schedule(status=1, day=START, home="Knicks"):
    return json.dumps({"leagueSchedule":{"leagueId":"00","gameDates":[
        {"games":[{"gameId":"0022600001","gameStatus":status,
                   "gameDateTimeUTC":day,
                   "homeTeam":{"teamCity":"New York","teamName":home},
                   "awayTeam":{"teamCity":"Boston","teamName":"Celtics"}}]}]}}).encode()


def box(status=1, gameid="0022600001", date=START,
        home="Knicks", away_player="Jayson Tatum", duplicate=False,
        empty=False, raw_status="ACTIVE"):
    away={"personId":100,"name":away_player,"status":raw_status,
          "notPlayingReason":None}
    away_list=[] if empty else ([away,deepcopy(away)] if duplicate else [away])
    return json.dumps({"game":{
        "gameId":gameid,"gameStatus":status,"gameTimeUTC":date,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":home,"teamTricode":"NYK",
                    "players":[{"personId":200,"name":"Jalen Brunson",
                                "status":"INACTIVE","notPlayingReason":"Injury"}]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS",
                    "players":away_list}}}).encode()


def event(start=START, snap="2026-11-05T12:30:00Z",
          home="New York Knicks", eid="401999001"):
    return {
        "record_type":"prospective_evidence_snapshot_research_only",
        "league":"nba","espn_schedule_event_id":eid,
        "event_start_utc":start,
        "snapshot_completed_at_utc":snap,
        "home_team":home,"away_team":"Boston Celtics",
        "player_level_status_parsed_and_verified":False,
        "qualified_for_challenger_backtest":False,
        "certified_prediction":False,
        "model_probability":None,"bet_ready":False,
        "champion_001_modified":False,
    }


def reader(rows=None, filings=None, metadata=None):
    if rows is None:rows=[injury()]
    if filings is None:filings=[]
    if metadata is None:metadata=receipt(len(rows),len(filings))
    return lambda folder, events, now:(deepcopy(rows),deepcopy(filings),deepcopy(metadata))


def fetcher(schedule_bytes=None, roster_bytes=None, calls=None):
    schedule_bytes = official_schedule() if schedule_bytes is None else schedule_bytes
    roster_bytes = box() if roster_bytes is None else roster_bytes
    def fetch(url, cap):
        if calls is not None:calls.append(url)
        if url==NBA_SCHEDULE_URL:
            assert cap==MAX_SCHEDULE_BYTES
            return schedule_bytes
        if url==official_url("0022600001"):
            assert cap==MAX_BOX_BYTES
            return roster_bytes
        raise AssertionError("Unexpected unsanctioned external request")
    return fetch


def execute(events=None, rows=None, filings=None, metadata=None,
            schedule_bytes=None, roster_bytes=None, calls=None, now=NOW):
    return run("synthetic-only",
               events=events,now=now,
               fetcher=fetcher(schedule_bytes,roster_bytes,calls),
               clock=lambda:now,
               pdf_reader=reader(rows,filings,metadata))


class PreGameNBAIDTests(unittest.TestCase):
    def test_exact_same_team_game_name_returns_id_candidate_not_active(self):
        out,report,originals=execute()
        self.assertEqual(len(out),1)
        p=out[0]
        self.assertEqual(p["nba_person_id_candidate"],"100")
        self.assertEqual(p["official_nba_team_id_candidate"],"1610612738")
        self.assertEqual(p["nba_game_id_candidate"],"0022600001")
        self.assertEqual(p["crosscheck_status"],
                         "nba_person_id_candidate_from_exact_scheduled_roster_research_only")
        self.assertEqual(p["source_nba_roster_raw_status"],"ACTIVE")
        self.assertFalse(p["roster_status_is_final_active_list"])
        self.assertFalse(p["current_game_active_inactive_verified"])
        self.assertFalse(p["independently_authenticated_player_id_crosswalk"])
        self.assertIsNone(p["espn_event_id_candidate"])
        self.assertEqual(report["nba_person_id_candidates_without_id_cross_source_authentication"],1)
        self.assertEqual(report["independently_confirmed_active_players"],0)
        self.assertFalse(report["champion_001_modified"])
        self.assertEqual(report["original_source_sha256"]["nba_official_schedule.json"],
                         hashlib.sha256(official_schedule()).hexdigest())
        self.assertEqual(originals["nba_pregame_box_0022600001.json"],box())

    def test_explicit_same_run_espn_start_identity_crosswalk(self):
        out,report,_=execute(events=[event()])
        self.assertEqual(out[0]["espn_event_id_candidate"],"401999001")
        self.assertEqual(out[0]["crosscheck_status"],
                         "nba_person_id_candidate_with_espn_game_crosswalk_research_only")
        self.assertEqual(report["matched_espn_game_crosswalk_candidates"],1)
        self.assertEqual(report["verified_nba_to_espn_to_draftkings_player_id_crosswalks"],0)

    def test_espn_clock_disagreement_blocks_entire_game_box_fetch(self):
        calls=[]
        p=event(start="2026-11-05T23:10:00Z")
        out,r,original=execute(events=[p],calls=calls)
        self.assertEqual(out[0]["crosscheck_status"],
                         "missing_exact_espn_official_pregame_crosswalk")
        self.assertIsNone(out[0]["nba_person_id_candidate"])
        self.assertEqual(calls,[NBA_SCHEDULE_URL])
        self.assertEqual(r["official_game_requests_bounded"],0)

    def test_espn_wrong_home_team_prevents_false_game_link(self):
        out,r,_=execute(events=[event(home="Los Angeles Lakers")])
        self.assertIsNone(out[0]["nba_person_id_candidate"])
        self.assertEqual(r["matched_espn_game_crosswalk_candidates"],0)

    def test_official_box_final_state_rejected_as_postgame_evidence(self):
        out,r,original=execute(roster_bytes=box(status=3))
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")
        self.assertIsNone(out[0]["nba_person_id_candidate"])
        self.assertEqual(r["official_game_requests_bounded"],1)
        self.assertEqual(list(original),["nba_official_schedule.json"])

    def test_official_box_live_state_also_rejected(self):
        out,r,_=execute(roster_bytes=box(status=2))
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")

    def test_scheduled_game_no_player_list_cannot_be_treated_as_player_absent(self):
        out,r,_=execute(roster_bytes=box(empty=True))
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")
        self.assertIsNone(out[0]["nba_person_id_candidate"])

    def test_team_name_mismatch_blocks_player_ids(self):
        out,_,_=execute(roster_bytes=box(home="Lakers"))
        self.assertIsNone(out[0]["nba_person_id_candidate"])
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")

    def test_duplicate_official_player_person_id_is_rejected(self):
        out,_,_=execute(roster_bytes=box(duplicate=True))
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")

    def test_box_and_schedule_game_clock_disagreement_blocked(self):
        out,_,_=execute(roster_bytes=box(date="2026-11-05T23:05:00Z"))
        self.assertIsNone(out[0]["nba_person_id_candidate"])

    def test_wrong_game_id_never_links_a_player(self):
        out,_,_=execute(roster_bytes=box(gameid="0022600002"))
        self.assertEqual(out[0]["crosscheck_status"],"pregame_roster_source_blocked_ValueError")

    def test_unmatched_player_name_not_fuzzily_linked_to_another_id(self):
        out,r,_=execute(rows=[injury(player="Jayson S. Tatum")])
        self.assertEqual(out[0]["crosscheck_status"],
                         "player_not_found_with_exact_same_team_name_in_official_pregame_roster")
        self.assertIsNone(out[0]["nba_person_id_candidate"])
        self.assertEqual(r["nba_person_id_candidates_without_id_cross_source_authentication"],0)

    def test_report_available_and_game_roster_active_still_not_clearance(self):
        out,r,_=execute(rows=[injury(designation="Available")])
        self.assertEqual(out[0]["source_nba_roster_raw_status"],"ACTIVE")
        self.assertEqual(out[0]["nba_report_designation"],"Available")
        self.assertFalse(out[0]["current_game_active_inactive_verified"])
        self.assertFalse(out[0]["qualified_for_player_prop_training"])
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_team_unsubmitted_and_player_on_same_club_is_error(self):
        rows=[injury(club="NYK",player="Jalen Brunson")]
        filings=[filing()]
        calls=[]
        with self.assertRaisesRegex(ValueError,"player_listed_on_unsubmitted"):
            execute(rows=rows,filings=filings,calls=calls)
        self.assertFalse(calls)

    def test_duplicate_pdf_players_block_before_network(self):
        calls=[]
        with self.assertRaisesRegex(ValueError,"duplicate_original_pdf_player"):
            execute(rows=[injury(),injury()],calls=calls)
        self.assertFalse(calls)

    def test_promoted_pdf_row_must_not_trigger_network(self):
        row=injury()
        row["bet_ready"]=True
        calls=[]
        with self.assertRaisesRegex(ValueError,"unsafe_nba_injury_player"):
            execute(rows=[row],calls=calls)
        self.assertFalse(calls)

    def test_untrusted_injury_report_status_is_blocked(self):
        row=injury(designation="Definitely Playing")
        calls=[]
        with self.assertRaisesRegex(ValueError,"invalid_pdf_player_name_or_status"):
            execute(rows=[row],calls=calls)
        self.assertFalse(calls)

    def test_missing_original_pdf_source_no_network(self):
        calls=[]
        out,r,original=execute(metadata=receipt(source=False),calls=calls)
        self.assertEqual(out,[])
        self.assertEqual(original,{})
        self.assertEqual(calls,[])
        self.assertEqual(r["status"],"original_injury_source_not_available")

    def test_future_or_stale_injury_snapshot_rejected(self):
        for at in ("2026-11-05T15:00:00Z","2026-11-03T14:00:00Z"):
            with self.assertRaisesRegex(ValueError,"stale_or_future_original"):
                execute(metadata=receipt(pdf_observed=at))

    def test_no_individual_pdf_player_entries_no_nba_network(self):
        calls=[]
        rows,report,original=execute(rows=[],calls=calls)
        self.assertFalse(rows)
        self.assertEqual(report["status"],"no_explicit_pdf_player_entries")
        self.assertEqual(original,{})
        self.assertEqual(calls,[])

    def test_schedule_source_failure_fails_closed_without_player_ids(self):
        def fail(url,cap):
            raise OSError("offline fixture")
        out,report,files=run("fixture",now=NOW,clock=lambda:NOW,
                             fetcher=fail,pdf_reader=reader())
        self.assertEqual(out[0]["crosscheck_status"],"official_nba_future_schedule_unavailable")
        self.assertEqual(report["status"],"official_nba_schedule_and_daily_board_unavailable")
        self.assertEqual(report["official_nba_schedule_source_errors"],{
            NBA_SCHEDULE_URL:"OSError",
            NBA_TODAY_SCOREBOARD_URL:"OSError"
        })
        self.assertEqual(files,{})

    def test_game_already_started_not_reused_as_pregame_roster(self):
        calls=[]
        out,report,files=execute(schedule_bytes=official_schedule(
            day="2026-11-05T13:55:00Z"),calls=calls)
        self.assertEqual(out[0]["crosscheck_status"],"no_unique_future_official_nba_game")
        self.assertEqual(calls,[NBA_SCHEDULE_URL])
        self.assertEqual(report["official_game_requests_bounded"],0)

    def test_cli_missing_original_pdf_writes_empty_research_artifact(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"nba_injury_original_report.json").write_text(
                json.dumps({"stage":"challenger_original_nba_pregame_injury_pdf_archive_research_only",
                            "source_status":"blocked_OSError"}))
            output=folder/"output"
            self.assertEqual(main(["--capture-dir",str(folder),
                                   "--output-dir",str(output)]),0)
            records=(output/"nba_pregame_roster_identity_review.jsonl").read_text()
            report=json.loads((output/"nba_pregame_roster_identity_report.json").read_text())
            self.assertEqual(records,"")
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual(report["independently_confirmed_active_players"],0)
            self.assertFalse((output/"nba_roster_original_source_bytes").exists())


if __name__=="__main__":
    unittest.main()
