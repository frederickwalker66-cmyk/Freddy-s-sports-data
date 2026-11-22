import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from official_nba_injury_gate import check,summary
R={"source":"NBA_OFFICIAL_INJURY_REPORT","source_url":"https://ak-static.cms.nba.com/wp-content/uploads/report.pdf",
   "player_id":"123","game_date":"2026-11-22","published_at":"2026-11-22T19:00:00Z","status":"Available"}
ARGS={"expected_player_id":"123","expected_game_date":"2026-11-22","as_of":"2026-11-22T20:00:00Z"}
class InjuryGateTests(unittest.TestCase):
    def test_available_still_holds(self):
        self.assertEqual(check(R,**ARGS),"HOLD_REPORT_EVIDENCE_REQUIRES_FINAL_LINEUP_CHECK")
    def test_missing_evidence_holds(self):
        self.assertEqual(check(None,**ARGS),"HOLD_NO_OFFICIAL_REPORT_EVIDENCE")
    def test_wrong_source_holds(self):
        self.assertEqual(check({**R,"source":"other"},**ARGS),"HOLD_UNTRUSTED_REPORT_SOURCE")
    def test_wrong_player_holds(self):
        self.assertEqual(check({**R,"player_id":"999"},**ARGS),"HOLD_PLAYER_ID_NOT_VERIFIED")
    def test_wrong_date_holds(self):
        self.assertEqual(check({**R,"game_date":"2026-11-21"},**ARGS),"HOLD_GAME_DATE_MISMATCH")
    def test_stale_holds(self):
        self.assertEqual(check(R,**{**ARGS,"as_of":"2026-11-23T02:00:00Z"}),"HOLD_REPORT_STALE")
    def test_questionable_holds(self):
        self.assertEqual(check({**R,"status":"Questionable"},**ARGS),"HOLD_OFFICIAL_STATUS_QUESTIONABLE")
    def test_no_certification(self):
        self.assertEqual(summary([R])["certified_take"],0)
if __name__=="__main__":
    unittest.main()
