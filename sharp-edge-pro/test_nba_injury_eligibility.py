import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from nba_injury_eligibility import screen,summarize
P={"DraftKingsName":"Example Player","PlayerID":11,"TeamID":4,"Team":"NY","Status":"Active"}
M={"is_player_prop":True,"player_name":"Example Player"}
I={"PlayerID":11,"TeamID":4,"InjuryStatus":"Out"}
class InjuryTests(unittest.TestCase):
    def test_out_holds(self):
        self.assertEqual(screen(M,[P],[I]),"HOLD_REPORTED_UNAVAILABLE")
    def test_questionable_holds(self):
        self.assertEqual(screen(M,[P],[{**I,"InjuryStatus":"Questionable"}]),"HOLD_REPORTED_UNCERTAIN")
    def test_no_injury_record_is_not_clearance(self):
        self.assertEqual(screen(M,[P],[]),"HOLD_NO_INJURY_RECORD_NOT_CLEARANCE")
    def test_duplicate_injury_holds(self):
        self.assertEqual(screen(M,[P],[I,I]),"HOLD_DUPLICATE_INJURY_RECORDS")
    def test_team_conflict_holds(self):
        self.assertEqual(screen(M,[P],[{**I,"TeamID":7}]),"HOLD_INJURY_TEAM_CONFLICT")
    def test_ambiguous_identity_holds(self):
        self.assertEqual(screen(M,[P,P],[I]),"HOLD_PLAYER_IDENTITY_MISSING_OR_AMBIGUOUS")
    def test_active_provider_only_holds(self):
        self.assertEqual(screen(M,[P],[{**I,"InjuryStatus":None}]),"HOLD_PROVIDER_ONLY_NOT_OFFICIAL_ELIGIBILITY")
    def test_summary_never_certifies(self):
        self.assertEqual(summarize([M],[P],[I])["certified_take"],0)
if __name__=="__main__":
    unittest.main()
