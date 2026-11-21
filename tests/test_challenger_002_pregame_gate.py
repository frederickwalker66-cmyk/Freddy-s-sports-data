import unittest
from research.challenger_002_pregame_gate import inspect_pregame_snapshot

class PregameGateTests(unittest.TestCase):
    def test_future_game_is_candidate_only(self):
        result=inspect_pregame_snapshot([{"GameID":1,"DateTime":"2026-11-22T19:00:00+00:00"}],"2026-11-21T12:00:00+00:00")
        self.assertEqual(result["status"],"PREGAME_CANDIDATES_NOT_AUTHENTICATED")
        self.assertFalse(result["independently_verified"])
        self.assertEqual(result["certified_take_count"],0)
    def test_past_game_rejected(self):
        result=inspect_pregame_snapshot([{"GameID":1,"DateTime":"2026-11-20T19:00:00+00:00"}],"2026-11-21T12:00:00+00:00")
        self.assertEqual(result["status"],"BLOCKED")
    def test_naive_start_rejected(self):
        result=inspect_pregame_snapshot([{"GameID":1,"DateTime":"2026-11-22T19:00:00"}],"2026-11-21T12:00:00+00:00")
        self.assertEqual(result["status"],"BLOCKED")
    def test_missing_id_rejected(self):
        result=inspect_pregame_snapshot([{"DateTime":"2026-11-22T19:00:00+00:00"}],"2026-11-21T12:00:00+00:00")
        self.assertEqual(result["status"],"BLOCKED")
    def test_mixed_games_no_false_certification(self):
        result=inspect_pregame_snapshot([{"GameID":1,"DateTime":"2026-11-22T19:00:00+00:00"},{"GameID":2,"DateTime":"2026-11-20T19:00:00+00:00"}],"2026-11-21T12:00:00+00:00")
        self.assertEqual(result["eligible_count"],1)
        self.assertEqual(len(result["rejected"]),1)
        self.assertEqual(result["certified_take_count"],0)

if __name__ == "__main__":
    unittest.main()
