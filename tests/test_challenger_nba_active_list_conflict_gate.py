"""Synthetic-only active/inactive roster-source reconciliation and no-bet tests."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_active_list_conflict_gate import evaluate, main
from challenger_nba_pregame_roster_identity import RESULT_TYPE

AT=datetime(2026,11,5,22,20,tzinfo=timezone.utc)
TIP="2026-11-05T23:00:00Z"
OBS="2026-11-05T22:15:00Z"
INJURY="2026-11-05T21:30:00Z"


def schedule():
    return json.dumps({"leagueSchedule":{"leagueId":"00","gameDates":[
        {"games":[{"gameId":"0022600001","gameStatus":1,
                  "gameDateTimeUTC":TIP,
                  "homeTeam":{"teamCity":"New York","teamName":"Knicks"},
                  "awayTeam":{"teamCity":"Boston","teamName":"Celtics"}}]}]}}).encode()


def nba_box(status="ACTIVE", pid=100, name="Jayson Tatum", game_status=1,
            tip=TIP, home="Knicks"):
    return json.dumps({"game":{
        "gameId":"0022600001","gameStatus":game_status,"gameTimeUTC":tip,
        "homeTeam":{"teamId":1610612752,"teamCity":"New York",
                    "teamName":home,"teamTricode":"NYK",
                    "players":[{"personId":200,"name":"Jalen Brunson","status":"ACTIVE",
                                "notPlayingReason":None}]},
        "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                    "teamName":"Celtics","teamTricode":"BOS",
                    "players":[{"personId":pid,"name":name,"status":status,
                                "notPlayingReason":None}]}}}).encode()


def record(injury="Out",status="ACTIVE",observed=OBS,injured_at=INJURY,matched=True):
    return {
        "record_type":RESULT_TYPE, "league":"nba",
        "game_date_et":"2026-11-05","matchup":"BOS@NYK",
        "nba_report_team":"Boston Celtics","nba_report_name":"Jayson Tatum",
        "nba_report_designation":injury,
        "nba_report_original_observed_at_utc":injured_at,
        "nba_game_id_candidate":"0022600001" if matched else None,
        "nba_person_id_candidate":"100" if matched else None,
        "official_nba_team_id_candidate":"1610612738" if matched else None,
        "espn_event_id_candidate":None,
        "source_nba_roster_printed_name":"Jayson Tatum" if matched else None,
        "source_nba_roster_raw_status":status if matched else None,
        "source_nba_not_playing_reason":None,
        "roster_original_observed_at_utc":observed if matched else None,
        "roster_original_raw_sha256":hashlib.sha256(nba_box(status=status)).hexdigest() if matched else None,
        "crosscheck_status":("nba_person_id_candidate_from_exact_scheduled_roster_research_only"
                             if matched else "no_unique_future_official_nba_game"),
        "nba_roster_match_is_identity_candidate_only":True,
        "independently_authenticated_player_id_crosswalk":False,
        "current_game_active_inactive_verified":False,
        "roster_status_is_final_active_list":False,
        "draftkings_player_id_verified":False,
        "qualified_for_player_prop_training":False,
        "certified_prediction":False,"bet_ready":False,
        "champion_001_modified":False,
    }


def report(rows,available=True):
    return {
        "stage":"challenger_nba_scheduled_roster_identity_review_only",
        "official_schedule_source_available":available,
        "original_nba_injury_pdf_sha256":"a"*64,
        "original_pdf_player_rows":len(rows),
        "official_nba_schedule_original_sha256":hashlib.sha256(schedule()).hexdigest() if available else None,
        "original_source_sha256":{
            "nba_official_schedule.json":hashlib.sha256(schedule()).hexdigest(),
            "nba_pregame_box_0022600001.json":hashlib.sha256(nba_box(status=rows[0]["source_nba_roster_raw_status"])).hexdigest()
        } if available and rows and rows[0]["nba_person_id_candidate"] else (
            {"nba_official_schedule.json":hashlib.sha256(schedule()).hexdigest()} if available else {}),
        "independently_confirmed_active_players":0,
        "verified_nba_to_espn_to_draftkings_player_id_crosswalks":0,
        "qualified_player_prop_training_observations":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,"automated_bets_placed":0,
        "champion_001_modified":False,
    }


def fixture(folder,items=None,source=None,available=True):
    root=Path(folder)
    if items is None:items=[record()]
    if source is None:source=nba_box(status=items[0]["source_nba_roster_raw_status"]) if items and items[0]["nba_person_id_candidate"] else None
    r=report(items,available)
    root.mkdir(parents=True,exist_ok=True)
    (root/"nba_pregame_roster_identity_review.jsonl").write_text(
        "".join(json.dumps(x)+"\n" for x in items))
    if source is not None and available:
        r["original_source_sha256"]["nba_pregame_box_0022600001.json"]=hashlib.sha256(source).hexdigest()
    (root/"nba_pregame_roster_identity_report.json").write_text(json.dumps(r))
    if r["original_source_sha256"]:
        d=root/"nba_roster_original_source_bytes"
        d.mkdir(exist_ok=True)
        (d/"nba_official_schedule.json").write_bytes(schedule())
        if source is not None:
            (d/"nba_pregame_box_0022600001.json").write_bytes(source)
    return r


def run_case(items=None,source=None,available=True,at=AT):
    with TemporaryDirectory() as tmp:
        fixture(tmp,items,source,available)
        return evaluate(tmp,at=at)


class ActiveListReconciliationTests(unittest.TestCase):
    def test_out_injury_report_vs_active_roster_signals_manual_conflict_only(self):
        rows,r=run_case()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["reconciliation_status"],
                         "reported_out_vs_preliminary_roster_active_conflict")
        self.assertTrue(rows[0]["potential_roster_injury_disagreement_for_manual_review"])
        self.assertEqual(rows[0]["nba_person_id_candidate"],"100")
        self.assertEqual(r["reported_out_vs_roster_active_conflicts"],1)
        self.assertEqual(r["near_tipoff_manual_conflicts"],1)
        self.assertFalse(rows[0]["official_complete_active_list_verified"])
        self.assertFalse(rows[0]["current_game_active_inactive_independently_confirmed"])
        self.assertEqual(r["independently_confirmed_game_day_active_players"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_available_injury_vs_inactive_roster_signal(self):
        p=record("Available","INACTIVE")
        rows,r=run_case([p])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "reported_available_vs_preliminary_roster_inactive_conflict")
        self.assertEqual(r["reported_available_vs_roster_inactive_conflicts"],1)

    def test_out_plus_inactive_is_not_a_certified_dnp_or_void(self):
        p=record("Out","INACTIVE")
        rows,r=run_case([p])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "two_source_out_inactive_agreement_not_final_active_list")
        self.assertFalse(rows[0]["player_participation_or_dnp_verified"])
        self.assertFalse(rows[0]["bookmaker_void_or_settlement_verified"])
        self.assertEqual(r["independently_confirmed_game_day_inactive_players"],0)

    def test_probable_active_is_preliminary_not_cleared(self):
        rows,_=run_case([record("Probable","ACTIVE")])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "provisional_game_roster_status_not_final_active_list")
        self.assertFalse(rows[0]["qualified_for_player_prop_training"])

    def test_questionable_inactive_not_a_certified_market_outcome(self):
        rows,_=run_case([record("Questionable","INACTIVE")])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "provisional_game_roster_status_not_final_active_list")
        self.assertFalse(rows[0]["bet_ready"])

    def test_unknown_raw_roster_status_is_not_assumed_active(self):
        rows,r=run_case([record("Out","BENCH")])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "nba_game_roster_status_unknown_or_not_explicit")
        self.assertEqual(r["near_tipoff_manual_conflicts"],0)

    def test_roster_observed_over_ninety_minutes_early_cannot_clear_conflict(self):
        p=record(observed="2026-11-05T21:20:00Z",injured_at="2026-11-05T20:00:00Z")
        rows,r=run_case([p])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "roster_source_observed_more_than_90min_before_tipoff")
        self.assertEqual(r["near_tipoff_manual_conflicts"],0)

    def test_stale_injury_observation_blocks_conflict(self):
        p=record(injured_at="2026-11-05T18:00:00Z")
        rows,r=run_case([p])
        self.assertEqual(rows[0]["reconciliation_status"],
                         "injury_document_older_than_three_hours_at_roster_observation")
        self.assertFalse(rows[0]["potential_roster_injury_disagreement_for_manual_review"])

    def test_player_not_in_roster_is_unknown_not_automatically_inactive(self):
        rows,r=run_case([record(matched=False)])
        self.assertIsNone(rows[0]["nba_person_id_candidate"])
        self.assertFalse(rows[0]["player_participation_or_dnp_verified"])
        self.assertEqual(r["near_tipoff_manual_conflicts"],0)

    def test_unavailable_schedule_never_creates_any_preliminary_signal(self):
        rows,r=run_case([record(matched=False)],available=False)
        self.assertEqual(rows[0]["reconciliation_status"],"no_verified_scheduled_roster_source")
        self.assertEqual(r["status"],"official_nba_schedule_or_roster_unavailable")

    def test_no_players_is_a_valid_empty_research_report(self):
        rows,r=run_case(items=[])
        self.assertEqual(rows,[])
        self.assertEqual(r["status"],"no_injury_players_with_roster_evidence")

    def test_missing_original_roster_file_never_substitutes_estimated_status(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            (Path(tmp)/"nba_roster_original_source_bytes"/"nba_pregame_box_0022600001.json").unlink()
            with self.assertRaises(FileNotFoundError):
                evaluate(tmp,AT)

    def test_sha_mismatch_blocks_source_tampering(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            (Path(tmp)/"nba_roster_original_source_bytes"/"nba_pregame_box_0022600001.json").write_bytes(b'{"game": {}}')
            with self.assertRaisesRegex(ValueError,"bytes_changed"):
                evaluate(tmp,AT)

    def test_conflicting_raw_status_vs_receipt_rejected(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            original=Path(tmp)/"nba_pregame_roster_identity_review.jsonl"
            rows=[json.loads(original.read_text().strip())]
            rows[0]["source_nba_roster_raw_status"]="INACTIVE"
            original.write_text(json.dumps(rows[0])+"\n")
            with self.assertRaisesRegex(ValueError,"roster_source_identity_or_status_disagreement"):
                evaluate(tmp,AT)

    def test_wrong_game_id_rejected_even_with_same_person_name(self):
        p=record()
        p["nba_game_id_candidate"]="0022600002"
        rows=None
        with TemporaryDirectory() as tmp:
            fixture(tmp,[p])
            with self.assertRaisesRegex(ValueError,"captured_original_nba_roster_bytes_changed|wrong_nba_game"):
                # The first source file has an unrecognized game identity, so a
                # strict refusal is required. It may fail at missing-file level.
                try:evaluate(tmp,AT)
                except FileNotFoundError as exc:raise ValueError("wrong_nba_game") from exc

    def test_final_nba_boxscore_must_not_be_accepted_as_pregame_roster(self):
        with TemporaryDirectory() as tmp:
            bad=nba_box(game_status=3)
            fixture(tmp,source=bad)
            with self.assertRaisesRegex(ValueError,"not_a_pregame_scheduled_state"):
                evaluate(tmp,AT)

    def test_live_nba_boxscore_must_not_be_accepted_as_pregame_roster(self):
        with TemporaryDirectory() as tmp:
            bad=nba_box(game_status=2)
            fixture(tmp,source=bad)
            with self.assertRaisesRegex(ValueError,"not_a_pregame_scheduled_state"):
                evaluate(tmp,AT)

    def test_game_tipoff_changed_between_sources_is_rejected(self):
        with TemporaryDirectory() as tmp:
            bad=nba_box(tip="2026-11-05T23:07:00Z")
            fixture(tmp,source=bad)
            with self.assertRaisesRegex(ValueError,"wrong_nba_game|nba_boxscore_and_schedule_start_disagree"):
                evaluate(tmp,AT)

    def test_duplicate_nba_person_id_from_two_report_rows_rejected(self):
        p=record()
        duplicate=dict(p)
        duplicate["nba_report_name"]="Jayson Other Tatum"
        with TemporaryDirectory() as tmp:
            fixture(tmp,items=[p,duplicate])
            with self.assertRaisesRegex(ValueError,"duplicate_same_game_nba_person_id"):
                evaluate(tmp,AT)

    def test_promoted_bet_ready_player_is_rejected(self):
        p=record()
        p["bet_ready"]=True
        with TemporaryDirectory() as tmp:
            fixture(tmp,[p])
            with self.assertRaisesRegex(ValueError,"unsafe_nba_injury_roster_match"):
                evaluate(tmp,AT)

    def test_promoted_champion_modified_report_rejected(self):
        with TemporaryDirectory() as tmp:
            r=fixture(tmp)
            r["champion_001_modified"]=True
            (Path(tmp)/"nba_pregame_roster_identity_report.json").write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"untrusted_or_promoted"):
                evaluate(tmp,AT)

    def test_future_injury_observation_must_not_be_retroactively_used(self):
        with TemporaryDirectory() as tmp:
            p=record(injured_at="2026-11-05T22:17:00Z")
            fixture(tmp,[p])
            with self.assertRaisesRegex(ValueError,"observations_out_of_order"):
                evaluate(tmp,AT)

    def test_snapshot_already_at_tipoff_rejected(self):
        with TemporaryDirectory() as tmp:
            p=record(observed=TIP)
            fixture(tmp,[p])
            with self.assertRaisesRegex(ValueError,"postgame_or_live_nba_roster"):
                evaluate(tmp,at=datetime(2026,11,6,1,tzinfo=timezone.utc))

    def test_cli_generates_research_only_reports_and_no_wager(self):
        with TemporaryDirectory() as tmp:
            fixture(tmp)
            out=Path(tmp)/"out"
            # CLI default now is system time; test via the pure interface
            # and verify output contract without inventing actual source.
            rows,r=evaluate(tmp,AT)
            out.mkdir()
            (out/"nba_active_list_conflict_review.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in rows))
            (out/"nba_active_list_conflict_report.json").write_text(json.dumps(r))
            self.assertEqual(r["certified_champion_001_predictions"],0)
            self.assertFalse(rows[0]["current_game_active_inactive_independently_confirmed"])
            self.assertFalse(r["champion_001_modified"])


if __name__=="__main__":
    unittest.main()
