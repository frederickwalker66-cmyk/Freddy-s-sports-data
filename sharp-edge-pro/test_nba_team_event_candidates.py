import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from nba_team_event_candidates import inspect_market,aggregate
PLAYER={"DraftKingsName":"Sample Athlete","PlayerID":10,"TeamID":5,"Team":"NY"}
MARKET={"is_player_prop":True,"player_name":"Sample Athlete",
        "home":{"abbreviation":"NY"},"away":{"abbreviation":"LA"},
        "event_id":"e1","event_start_time":"2026-11-22T19:00:00Z"}
class TeamEventTests(unittest.TestCase):
    def test_team_event_candidate_not_certified(self):
        r=inspect_market(MARKET,[PLAYER])
        self.assertEqual(r["status"],"TEAM_EVENT_CANDIDATE_ONLY")
        self.assertFalse(r["certified_take"])
    def test_wrong_team_holds(self):
        self.assertEqual(inspect_market(MARKET,[{**PLAYER,"Team":"BOS"}])["status"],"HOLD")
    def test_missing_event_holds(self):
        self.assertEqual(inspect_market({**MARKET,"event_id":None},[PLAYER])["status"],"HOLD")
    def test_duplicate_players_hold(self):
        self.assertEqual(inspect_market(MARKET,[PLAYER,PLAYER])["status"],"HOLD")
    def test_missing_team_holds(self):
        self.assertEqual(inspect_market({**MARKET,"home":{}},[PLAYER])["status"],"HOLD")
    def test_aggregate_always_hold(self):
        self.assertEqual(aggregate([MARKET],[PLAYER])["certified_take"],0)
if __name__=="__main__":
    unittest.main()
