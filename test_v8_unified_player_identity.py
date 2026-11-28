import unittest
from v8_unified_player_identity import match_player
class IdentityTests(unittest.TestCase):
    def test_fail_closed(self):
        q=dict(league="nba",player_id="p",provider_event_id="g",player_identity_independently_verified=True)
        h=dict(historical_espn_player_id="e",scheduled_event_id="n",current_roster_status_verified=True)
        x=dict(independently_verified=True,league="nba",provider_player_id="p",espn_player_id="e",provider_event_id="g",espn_event_id="n")
        self.assertFalse(match_player(q,h,{} )["identity_verified"])
        self.assertFalse(match_player({**q,"player_id":None},h,x)["identity_verified"])
        self.assertFalse(match_player(q,{**h,"current_roster_status_verified":False},x)["identity_verified"])
        good=match_player(q,h,x)
        self.assertTrue(good["identity_verified"])
        self.assertEqual(good["decision"],"HOLD")
        self.assertIsNone(good["ev"])
if __name__=="__main__": unittest.main()
