import unittest
from research.challenger_002_nba_research_join import build

S={"kind":"nba_scores","date":"2026-11-21","retrieved_at":"2026-11-21T17:45:00Z","canonical_payload_sha256":"scores"}
O={"kind":"nba_odds","date":"2026-11-21","retrieved_at":"2026-11-21T17:48:00Z","canonical_payload_sha256":"odds"}

class NBAResearchJoinTests(unittest.TestCase):
    def test_valid_link_is_research_only(self):
        r=build([{"GameID":1,"GlobalGameID":99}], [{"GameId":1,"GlobalGameId":99,"PregameOdds":[]}], S,O)
        self.assertEqual(r["joined_game_count"],1)
        self.assertEqual(r["training_rows_approved"],0)
        self.assertEqual(r["certified_take_count"],0)
        self.assertFalse(r["research_join_rows"][0]["certified"])
    def test_global_id_conflict_rejected(self):
        r=build([{"GameID":1,"GlobalGameID":99}], [{"GameId":1,"GlobalGameId":100}], S,O)
        self.assertEqual(r["joined_game_count"],0)
        self.assertEqual(r["rejected_count"],1)
    def test_duplicate_game_id_rejected(self):
        r=build([{"GameID":1,"GlobalGameID":99},{"GameID":1,"GlobalGameID":99}],
                [{"GameId":1,"GlobalGameId":99}],S,O)
        self.assertEqual(r["joined_game_count"],0)
    def test_date_mismatch_blocked(self):
        r=build([],[],S,{**O,"date":"2026-11-20"})
        self.assertEqual(r["status"],"BLOCKED_DATE_MISMATCH")
    def test_missing_source_kind_blocked(self):
        r=build([],[],S,{**O,"kind":"nba_scores"})
        self.assertEqual(r["status"],"BLOCKED_SOURCE_KIND")

if __name__=="__main__":
    unittest.main()
