"""Regression tests for the NBA independent-evidence quarantine gate."""
import unittest
from challenger_nba_independent_review import assess

class ReviewGateTests(unittest.TestCase):
    def test_empty_input_fails_closed(self):
        result = assess([])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["qualified_training_examples"], 0)
        self.assertFalse(result["champion_001_modified"])

    def test_duplicate_event_quarantined(self):
        row = {"event_id": "123", "league": "nba"}
        result = assess([row, dict(row)])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["duplicate_event_quarantined"], 2)

    def test_missing_sources_rejected(self):
        row = {"event_id": "456", "league": "nba",
               "champion_001_modified": False,
               "certified_prediction": False, "bet_ready": False,
               "snapshot_completed_at_utc": "2026-10-01T18:00:00Z",
               "start_utc": "2026-10-01T23:00:00Z",
               "outcome_observed_at_utc": "2026-10-02T02:00:00Z"}
        result = assess([row])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["independent_checks_missing"], 1)

if __name__ == "__main__":
    unittest.main()
