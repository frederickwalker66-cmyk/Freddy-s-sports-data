import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from nba_schedule_crosscheck import assess,summarize
M={"home":{"abbreviation":"NY"},"away":{"abbreviation":"LA"},"event_start_time":"2026-11-22T19:00:00Z"}
G={"HomeTeam":"NY","AwayTeam":"LA","DateTimeUTC":"2026-11-22T19:00:00Z","GameID":123}
class ScheduleTests(unittest.TestCase):
    def test_match_is_corroboration_only(self):
        self.assertEqual(assess(M,[G]),"SCHEDULE_CORROBORATED_ONLY")
    def test_wrong_teams_hold(self):
        self.assertTrue(assess(M,[{**G,"HomeTeam":"BOS"}]).startswith("HOLD"))
    def test_wrong_time_holds(self):
        self.assertTrue(assess(M,[{**G,"DateTimeUTC":"2026-11-22T22:00:00Z"}]).startswith("HOLD"))
    def test_missing_game_id_holds(self):
        self.assertEqual(assess(M,[{**G,"GameID":None}]),"HOLD_SCHEDULE_GAME_ID_MISSING")
    def test_ambiguous_holds(self):
        self.assertTrue(assess(M,[G,G]).startswith("HOLD"))
    def test_missing_timezone_holds(self):
        self.assertTrue(assess({**M,"event_start_time":"2026-11-22T19:00:00"},[G]).startswith("HOLD"))
    def test_never_certifies(self):
        self.assertEqual(summarize([M],[G])["certified_take"],0)
if __name__=="__main__":
    unittest.main()
