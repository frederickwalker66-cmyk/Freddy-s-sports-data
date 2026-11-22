import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from nba_name_candidates import candidate_index,assess_candidate,summary
class CandidateTests(unittest.TestCase):
    def test_unique_match_is_only_candidate(self):
        idx=candidate_index([{"DraftKingsName":"Test Player","PlayerID":1,"TeamID":2}])
        self.assertEqual(assess_candidate({"is_player_prop":True,"player_name":"Test Player"},idx)["status"],"CANDIDATE_ONLY")
    def test_ambiguous_holds(self):
        p={"DraftKingsName":"Test Player","PlayerID":1,"TeamID":2}
        idx=candidate_index([p,p])
        self.assertEqual(assess_candidate({"is_player_prop":True,"player_name":"Test Player"},idx)["status"],"HOLD")
    def test_missing_id_holds(self):
        idx=candidate_index([{"DraftKingsName":"Test Player","TeamID":2}])
        self.assertEqual(assess_candidate({"is_player_prop":True,"player_name":"Test Player"},idx)["status"],"HOLD")
    def test_missing_name_holds(self):
        self.assertEqual(assess_candidate({"is_player_prop":True},candidate_index([]))["status"],"HOLD")
    def test_no_certified_picks(self):
        p=[{"DraftKingsName":"Test Player","PlayerID":1,"TeamID":2}]
        m=[{"is_player_prop":True,"player_name":"Test Player"}]
        self.assertEqual(summary(m,p)["certified_take"],0)
if __name__=="__main__":
    unittest.main()
