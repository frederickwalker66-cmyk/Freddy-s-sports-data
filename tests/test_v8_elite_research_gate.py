"""Tests for V8 research math and fail-closed release boundary."""
import math
import unittest

from v8_elite_research_gate import (
    breakeven_probability, decimal_odds, expected_roi,
    release_gate, research_price_comparison,
)


class V8ResearchGateTests(unittest.TestCase):
    def test_american_odds(self):
        self.assertAlmostEqual(decimal_odds(-110), 1 + 100 / 110)
        self.assertAlmostEqual(decimal_odds(150), 2.5)
        self.assertAlmostEqual(breakeven_probability(-110), 110 / 210)

    def test_expected_value(self):
        self.assertAlmostEqual(expected_roi(.58, -110), .58 * (1 + 100 / 110) - 1)
        self.assertAlmostEqual(expected_roi(0, 150), -1)
        self.assertAlmostEqual(expected_roi(1, 150), 1.5)

    def test_reject_invalid_odds_and_probabilities(self):
        for odds in (0, 99, -99, 101.0, True, "-110"):
            with self.subTest(odds=odds), self.assertRaises(ValueError):
                decimal_odds(odds)
        for probability in (-.1, 1.1, math.nan, math.inf, "0.58", True):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                expected_roi(probability, -110)

    def test_gate_blocks_empty_evidence(self):
        result = release_gate({"league": "nba", "champion_001_modified": False})
        self.assertFalse(result["release_review_complete"])
        self.assertFalse(result["bet_ready"])
        self.assertEqual(result["certified_predictions"], 0)
        self.assertIn("pregame_asof_proof_missing", result["blockers"])

    def test_gate_never_auto_certifies_even_if_flags_pass(self):
        evidence = {
            "league": "nba",
            "champion_001_modified": False,
            "independent_source_authentication": True,
            "original_pregame_asof_authenticated": True,
            "independent_result_adjudication": True,
            "verified_market_settlement_rules": True,
            "untouched_chronological_holdout": True,
            "qualified_training_games": 200,
            "qualified_holdout_games": 50,
            "calibrated_out_of_sample": True,
            "independently_verified_executable_odds": True,
            "reproduced_model_artifact": True,
        }
        result = release_gate(evidence)
        self.assertTrue(result["release_review_complete"])
        self.assertFalse(result["bet_ready"])
        self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_all_eight_league_ids_are_supported_without_self_certifying(self):
        from v8_milestone_tracker import LEAGUES
        for league in LEAGUES:
            with self.subTest(league=league):
                result = release_gate({"league": league, "champion_001_modified": False})
                self.assertNotIn("unsupported_league", result["blockers"])
                self.assertEqual(result["certified_predictions"], 0)
                self.assertFalse(result["bet_ready"])
        invalid = release_gate({"league": "uefa", "champion_001_modified": False})
        self.assertIn("unsupported_league", invalid["blockers"])

    def test_research_comparison_is_never_certified(self):
        result = research_price_comparison(.58, -110)
        self.assertFalse(result["certified_prediction"])


if __name__ == "__main__":
    unittest.main()
