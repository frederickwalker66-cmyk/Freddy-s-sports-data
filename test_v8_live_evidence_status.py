"""Offline smoke tests: report uses observed counts without certifying wagers."""
import unittest
from v8_live_evidence_status import summarize

class LiveEvidenceStatusTests(unittest.TestCase):
    def test_observed_candidate_count_is_not_certification(self):
        status=summarize({"command":"run_nba_best_bets",
            "nba_live_price_research_gate":{"candidate_count":17,
                "verified_player_crosswalks_loaded":0}})
        self.assertEqual(status["nba_price_candidates_examined"],17)
        self.assertTrue(status["nba_price_gate_present"])
        self.assertEqual(status["decision"],"HOLD")
        self.assertFalse(status["live_draftkings_checkout_verified"])
        self.assertEqual(status["native_champion_001_probabilities_verified"],0)

    def test_missing_report_fails_closed(self):
        status=summarize({})
        self.assertFalse(status["nba_price_gate_present"])
        self.assertEqual(status["nba_price_candidates_examined"],0)
        self.assertEqual(status["decision"],"HOLD")

if __name__ == "__main__":
    unittest.main()
