"""Offline regression tests for Challenger-002; no network or sportsbook access."""
import unittest
from datetime import datetime, timedelta, timezone
from research.challenger_002_baseline import evaluate

BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)

def dataset(n=360, late_labels=False):
    rows = []
    for i in range(n):
        start = BASE + timedelta(days=i)
        label_time = start + timedelta(hours=3)
        if late_labels and i == 0:
            label_time = BASE + timedelta(days=500)
        rows.append({
            "event_id": "game-" + str(i),
            "event_start_at": start.isoformat(),
            "observed_at": (start - timedelta(hours=2)).isoformat(),
            "outcome_observed_at": label_time.isoformat(),
            "features": {"home_strength": float(i % 5), "away_strength": float(i % 7)},
            "outcome": int((i % 3) == 0),
        })
    return rows

class Challenger002Tests(unittest.TestCase):
    def test_research_never_certifies(self):
        report = evaluate(dataset())
        self.assertEqual(report["status"], "RESEARCH_EVALUATED_NOT_CERTIFIED")
        self.assertEqual(report["certified_take_count"], 0)
        self.assertGreaterEqual(report["test_brier"], 0)
        self.assertIn("SIGNED_ODDS_AND_RELEASE_EVIDENCE_REQUIRED", report["blockers"])

    def test_insufficient_data_fails_closed(self):
        report = evaluate(dataset(12))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["certified_take_count"], 0)

    def test_train_label_leakage_blocks(self):
        report = evaluate(dataset(late_labels=True))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("TRAIN_FEATURES_OR_LABELS_OVERLAP_TEST_PERIOD", report["blockers"])

    def test_missing_outcome_timestamp_rejected(self):
        rows = dataset(12)
        del rows[0]["outcome_observed_at"]
        report = evaluate(rows)
        self.assertEqual(report["valid_rows"], 11)
        self.assertEqual(report["status"], "BLOCKED")

    def test_duplicate_event_rejected(self):
        rows = dataset(12)
        rows[1]["event_id"] = rows[0]["event_id"]
        report = evaluate(rows)
        self.assertEqual(report["valid_rows"], 11)

if __name__ == "__main__":
    unittest.main()
