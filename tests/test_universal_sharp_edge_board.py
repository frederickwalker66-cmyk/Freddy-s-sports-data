import unittest
from research.universal_sharp_edge_board import break_even_percent, build_universal_board


class UniversalBoardTests(unittest.TestCase):
    def test_break_even_is_market_not_model(self):
        self.assertEqual(break_even_percent(-110), 52.38)
        self.assertEqual(break_even_percent(150), 40.0)
        self.assertIsNone(break_even_percent(None))

    def test_every_command_has_board_even_without_rows(self):
        board = build_universal_board({"command": "run_nba", "requested_leagues": ["nba"]})
        self.assertEqual(board["decision_counts"]["TAKE"], 0)
        self.assertEqual(board["rows"], [])
        self.assertIsNotNone(board["no_candidates_reason"])

    def test_spoofed_certification_never_take(self):
        candidate = {"selection": "home", "sport": "nba", "american_odds": -110,
                     "decision": "TAKE", "certified": True, "authenticated_source": True,
                     "native_champion_probability_verified": True, "positive_ev_verified": True}
        board = build_universal_board({"command": "run", "research_edge_candidates": [candidate]})
        row = board["rows"][0]
        self.assertEqual(row["decision"], "HOLD")
        self.assertIsNone(row["champion_001_probability_percent"])
        self.assertIsNone(row["verified_ev_percent"])
        self.assertEqual(row["break_even_probability_percent"], 52.38)

    def test_pass_is_preserved(self):
        board = build_universal_board({"research_edge_candidates": [{"decision": "PASS"}]})
        self.assertEqual(board["rows"][0]["decision"], "PASS")
