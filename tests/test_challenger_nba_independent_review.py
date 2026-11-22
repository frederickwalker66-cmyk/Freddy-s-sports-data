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

    def test_late_snapshot_rejected(self):
        row = {"event_id": "789", "league": "nba",
               "champion_001_modified": False,
               "certified_prediction": False, "bet_ready": False,
               "snapshot_completed_at_utc": "2026-10-02T00:00:00Z",
               "start_utc": "2026-10-01T23:00:00Z",
               "outcome_observed_at_utc": "2026-10-02T03:00:00Z",
               "independent_checks": {}}
        result = assess([row])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["not_point_in_time"], 1)

    def test_conflicting_sources_rejected(self):
        row = {"event_id": "790", "league": "nba",
               "champion_001_modified": False,
               "certified_prediction": False, "bet_ready": False,
               "snapshot_completed_at_utc": "2026-10-01T18:00:00Z",
               "start_utc": "2026-10-01T23:00:00Z",
               "outcome_observed_at_utc": "2026-10-02T03:00:00Z",
               "independent_checks": {"schedule": {
                   "reviewer_verified": True, "upstream_independence_verified": True,
                   "values_agree": False,
                   "sources": [
                       {"origin_provider": provider, "url": "https://"+provider+".example.org",
                        "observed_at_utc": "2026-10-01T17:00:00Z", "sha256": "a"*64}
                       for provider in ("sourceone", "sourcetwo")]}}}
        result = assess([row])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["schedule_source_disagreement"], 1)


    def _complete_row(self):
        return {
            "event_id": "9001", "league": "nba",
            "champion_001_modified": False, "certified_prediction": False,
            "bet_ready": False,
            "snapshot_completed_at_utc": "2026-10-01T18:00:00Z",
            "start_utc": "2026-10-01T23:00:00Z",
            "outcome_observed_at_utc": "2026-10-02T03:00:00Z",
            "independent_checks": {
                kind: {
                    "reviewer_verified": True,
                    "upstream_independence_verified": True,
                    "values_agree": True,
                    "sources": [
                        {"origin_provider": provider,
                         "url": "https://" + host,
                         "observed_at_utc": ("2026-10-02T02:00:00Z"
                                             if kind == "final_outcome"
                                             else "2026-10-01T17:00:00Z"),
                         "sha256": "a" * 64}
                        for provider, host in
                        (("one", "first.example.org"),
                         ("two", "second.example.org"))
                    ]
                }
                for kind in ("schedule", "pregame_features", "final_outcome")
            }
        }

    def test_distinct_provider_labels_same_host_rejected(self):
        row = self._complete_row()
        row["independent_checks"]["schedule"]["sources"][1]["url"] = "https://first.example.org/other"
        result = assess([row])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["schedule_same_source_host"], 1)

    def test_outcome_observed_after_report_timestamp_rejected(self):
        row = self._complete_row()
        row["independent_checks"]["final_outcome"]["sources"][1]["observed_at_utc"] = "2026-10-02T04:00:00Z"
        result = assess([row])
        self.assertEqual(result["reviewed_candidates"], 0)
        self.assertEqual(result["rejection_reasons"]["outcome_outside_observation_window"], 1)

    def test_complete_assertions_still_not_training_qualified(self):
        result = assess([self._complete_row()])
        self.assertEqual(result["reviewed_candidates"], 1)
        self.assertEqual(result["qualified_training_examples"], 0)
        self.assertEqual(result["certified_predictions"], 0)

if __name__ == "__main__":
    unittest.main()
