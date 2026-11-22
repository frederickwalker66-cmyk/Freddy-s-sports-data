import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
spec = importlib.util.spec_from_file_location("player_identity", Path(__file__).with_name("player_identity.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW = datetime(2026,11,22,15,0,tzinfo=timezone.utc)
def market():
    return {"is_player_prop":True,"event_id":"event1","player_name":"Example Player"}
def evidence():
    return {"player_id":"p1","team_id":"t1","event_id":"event1","event_team_ids":["t1","t2"],
            "roster_confirmed":True,"player_name_matched":True,
            "injury_status_verified":True,"eligible_to_play":True,
            "source":"verified-provider","verified_at":NOW.isoformat()}
class PlayerIdentityTests(unittest.TestCase):
    def test_complete_identity_not_bet_certification(self):
        self.assertEqual(mod.verify_player_prop(market(),evidence(),NOW)["status"],"IDENTITY_CHECK_PASS")
    def test_missing_evidence_holds(self):
        self.assertEqual(mod.verify_player_prop(market(),None,NOW)["status"],"HOLD")
    def test_missing_player_id_holds(self):
        e=evidence();e["player_id"]=""
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_wrong_event_holds(self):
        e=evidence();e["event_id"]="other"
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_wrong_team_holds(self):
        e=evidence();e["team_id"]="t3"
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_unverified_roster_holds(self):
        e=evidence();e["roster_confirmed"]=False
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_unverified_injury_holds(self):
        e=evidence();e["injury_status_verified"]=False
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_ineligible_player_holds(self):
        e=evidence();e["eligible_to_play"]=False
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_stale_evidence_holds(self):
        e=evidence();e["verified_at"]=(NOW-timedelta(hours=2)).isoformat()
        self.assertEqual(mod.verify_player_prop(market(),e,NOW)["status"],"HOLD")
    def test_not_player_prop_is_not_applicable(self):
        m=market();m["is_player_prop"]=False
        self.assertEqual(mod.verify_player_prop(m,evidence(),NOW)["status"],"NOT_APPLICABLE")
if __name__=="__main__":
    unittest.main()
