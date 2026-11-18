"""Offline fixture and veto tests. No external services."""
import unittest
from datetime import datetime,timezone
from v9_pregame_staff_meeting import analyze,markdown

NOW=datetime(2026,11,18,10,30,tzinfo=timezone.utc)


def board(stamp="2026-11-18T10:00:00Z"):
    return {"source_manifest":{"schedule":{
        "status":"READ_EXISTING_ARCHIVE_ONLY",
        "run_created_at_utc":stamp,"run_id":333,
        "run_url":"https://github.com/example/test/actions/runs/333"}},
        "certified_positive_ev_count_by_this_board":0,
        "certified_native_model_probability_count_by_this_board":0,
        "verified_executable_draftkings_quote_count_by_this_board":0}


def game(start="2026-11-18T11:00:00Z",eid="1234",league="nba"):
    return {"league":league,"status":"scheduled","away_team":"Visiting Club",
            "home_team":"Home Club","provider_game_id":eid,
            "start_utc":start,"observed_at_utc":"2026-11-18T10:02:00Z"}


class PregameMeetingTests(unittest.TestCase):
    def test_six_role_meeting_and_unreleased_prediction(self):
        report=analyze(board(),{"events":[game()]},clock=NOW)
        self.assertEqual(report["status"],"PREGAME_MEETING_RESEARCH_HOLD")
        self.assertEqual(len(report["six_staff"]),6)
        self.assertEqual(len(report["pregame_games"]),1)
        self.assertEqual(report["pregame_games"][0]["minutes_to_start"],30)
        self.assertEqual(report["final_team_decision"],"HOLD")
        self.assertIsNone(report["final_prediction"])
        self.assertEqual(report["certified_bets_or_parlays"],0)
        self.assertEqual(report["paid_api_calls"],0)
        self.assertEqual(report["automated_bets"],0)
        self.assertFalse(report["champion_001_modified"])
        self.assertIn("Final decision: HOLD",markdown(report))

    def test_stale_source_is_not_empty_slate_claim(self):
        report=analyze(board("2026-11-18T04:00:00Z"),
                       {"events":[game()]},clock=NOW)
        self.assertEqual(report["status"],"SOURCE_UNAVAILABLE_OR_STALE_HOLD")
        self.assertEqual(report["source_status"],"STALE_SOURCE_ARCHIVE")
        self.assertEqual(report["pregame_games"],[])

    def test_unavailable_source_does_not_forge_game(self):
        report=analyze(board(),None,clock=NOW)
        self.assertEqual(report["status"],"SOURCE_UNAVAILABLE_OR_STALE_HOLD")
        self.assertEqual(report["pregame_games"],[])

    def test_window_and_prestart_capture_enforced(self):
        invalid=game(eid="888")
        invalid["observed_at_utc"]="2026-11-18T12:00:00Z"
        old=game(start="2026-11-18T09:00:00Z",eid="889")
        late=game(start="2026-11-18T14:00:00Z",eid="890")
        report=analyze(board(),{"events":[game(),game(),invalid,old,late]},clock=NOW)
        self.assertEqual(len(report["pregame_games"]),1)
        self.assertGreaterEqual(report["rejected_source_rows"],2)

    def test_full_evening_nba_slate_and_hard_no_lock(self):
        late=game(start="2026-11-18T21:45:00Z",eid="7788")
        report=analyze(board(),{"events":[game(),late]},
                       clock=NOW,lookahead_minutes=720)
        self.assertEqual(report["nba_full_slate_games_displayed"],2)
        self.assertEqual(report["eight_leg_required_certified_legs"],8)
        self.assertEqual(report["eight_leg_certified_legs"],0)
        self.assertEqual(report["eight_leg_lock_decision"],"NO_LOCK_HOLD")
        self.assertFalse(report["nba_injuries_and_final_lineups_verified_here"])
        self.assertIn("NO LOCK",markdown(report))
        self.assertIn("PRA",markdown(report))

    def test_no_fabricated_selection_on_claim_of_upstream_ev(self):
        b=board()
        b["certified_positive_ev_count_by_this_board"]=999
        report=analyze(b,{"events":[game()]},clock=NOW)
        self.assertEqual(report["final_team_decision"],"HOLD")
        self.assertIsNone(report["pregame_games"][0]["proposed_prediction"])
        self.assertIsNone(report["pregame_games"][0]["certified_ev"])

    def test_fail_closed_invalid_clock_or_window(self):
        with self.assertRaises(ValueError):
            analyze(board(),{"events":[]},clock=datetime(2026,11,18,10,30))
        with self.assertRaises(ValueError):
            analyze(board(),{"events":[]},clock=NOW,lookahead_minutes=999)


if __name__=="__main__":
    unittest.main()
