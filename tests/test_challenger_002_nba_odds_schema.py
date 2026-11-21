import unittest
from research.challenger_002_nba_odds_schema import profile
class OddsSchemaTests(unittest.TestCase):
    def test_nested_market_names_not_values(self):
        r=profile([{"PregameOdds":[{"Sportsbook":"DraftKings","Markets":[{"Price":-110}]}],"LiveOdds":[]}])
        self.assertEqual(r["markets"]["PregameOdds"]["item_field_names"],["Markets","Sportsbook"])
        self.assertIn("Price",r["markets"]["PregameOdds"]["nested_field_names"])
        self.assertNotIn("DraftKings",str(r))
        self.assertNotIn("-110",str(r))
        self.assertFalse(r["draftkings_identity_verified"])
        self.assertEqual(r["certified_take_count"],0)
    def test_invalid_input(self):
        self.assertEqual(profile({})["status"],"BLOCKED_INVALID_INPUT")
if __name__=="__main__":unittest.main()
