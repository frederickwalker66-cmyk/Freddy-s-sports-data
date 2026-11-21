import unittest
from research.challenger_002_nba_sportsbook_audit import audit
class SportsbookAuditTests(unittest.TestCase):
    def test_draftkings_name_does_not_certify(self):
        r=audit([{"GameId":42,"PregameOdds":[{"Sportsbook":"DraftKings","SportsbookId":12,
                 "Created":"2026-11-21T16:00:00Z","Updated":"2026-11-21T16:30:00Z",
                 "HomeMoneyLine":-110,"AwayMoneyLine":100}]}])
        self.assertEqual(r["draftkings_name_matches"],1)
        self.assertEqual(r["draftkings_named_game_count"],1)
        self.assertEqual(r["moneyline_pair_present"],1)
        self.assertFalse(r["draftkings_identity_verified"])
        self.assertEqual(r["certified_take_count"],0)
        self.assertNotIn("-110",str(r))
    def test_invalid_input(self):
        self.assertEqual(audit({})["status"],"BLOCKED_INVALID_INPUT")
if __name__=="__main__":unittest.main()
