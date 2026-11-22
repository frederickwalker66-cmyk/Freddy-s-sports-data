import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from roster_bridge import verify_sharpapi_player_prop

class RosterBridgeTests(unittest.TestCase):
    def test_no_evidence_holds(self):
        result=verify_sharpapi_player_prop({"is_player_prop":True,"player_name":"Example","event_id":"e"})
        self.assertEqual(result["status"],"HOLD")
        self.assertIn("provider_player_id_crosswalk_missing",result["reasons"])
    def test_wrong_name_holds(self):
        m={"is_player_prop":True,"player_name":"Example","event_id":"e"}
        e={"sharpapi_player_name":"Other","sharpapi_event_id":"e","provider_player_id_crosswalk_verified":True}
        self.assertIn("player_name_crosswalk_mismatch",verify_sharpapi_player_prop(m,e)["reasons"])
    def test_wrong_event_holds(self):
        m={"is_player_prop":True,"player_name":"Example","event_id":"e"}
        e={"sharpapi_player_name":"Example","sharpapi_event_id":"other","provider_player_id_crosswalk_verified":True}
        self.assertIn("event_crosswalk_mismatch",verify_sharpapi_player_prop(m,e)["reasons"])
    def test_unverified_crosswalk_holds(self):
        m={"is_player_prop":True,"player_name":"Example","event_id":"e"}
        e={"sharpapi_player_name":"Example","sharpapi_event_id":"e","provider_player_id_crosswalk_verified":False}
        self.assertIn("provider_player_id_crosswalk_unverified",verify_sharpapi_player_prop(m,e)["reasons"])
    def test_non_prop_not_applicable(self):
        self.assertEqual(verify_sharpapi_player_prop({"is_player_prop":False})["status"],"NOT_APPLICABLE")
if __name__=="__main__":
    unittest.main()
