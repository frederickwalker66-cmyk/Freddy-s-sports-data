import unittest
from research.challenger_002_nba_schema_profile import profile

class SchemaProfileTests(unittest.TestCase):
    def test_matching_ids(self):
        r=profile([{"GameID":42,"DateTime":"2026-11-21"}],
                  [{"GameID":42,"Sportsbook":"unknown"}])
        self.assertEqual(r["join_candidates"][0]["unique_matching_ids"],1)
        self.assertEqual(r["training_rows_approved"],0)
        self.assertEqual(r["certified_take_count"],0)
    def test_sportsdataio_case_aliases(self):
        r=profile([{"GameID":101,"GlobalGameID":9001}], [{"GameId":101,"GlobalGameId":9001}])
        self.assertEqual(len(r["join_candidates"]),2)
        self.assertTrue(all(item["unique_matching_ids"]==1 for item in r["join_candidates"]))
        self.assertEqual(r["training_rows_approved"],0)
    def test_unknown_schema_never_guesses(self):
        r=profile([{"GameID":42}],[{"Other":42}])
        self.assertEqual(r["join_candidates"],[])
    def test_invalid_inputs_fail_closed(self):
        self.assertEqual(profile({},[])["status"],"BLOCKED")
if __name__=="__main__":
    unittest.main()
