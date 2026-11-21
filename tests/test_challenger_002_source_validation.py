"""Offline metadata validation; no live data or provider access."""
import unittest
from research.challenger_002_source_validation import inspect

BASE = {
    "event_id":"example-1", "league":"NBA", "market":"moneyline",
    "event_start_at":"2025-01-02T19:00:00+00:00",
    "observed_at":"2025-01-02T18:00:00+00:00",
    "source_observed_at":"2025-01-02T17:59:00+00:00",
    "outcome_observed_at":"2025-01-02T23:00:00+00:00",
    "source_provider":"SportsDataIO", "source_record_id":"example",
    "source_payload_sha256":"a"*64, "outcome":1, "features":{"home_elo":1500.0}
}

class SourceValidationTests(unittest.TestCase):
    def test_schema_only_never_certifies(self):
        r = inspect([dict(BASE)])
        self.assertEqual(r["status"],"SCHEMA_VALID_ONLY_NOT_SOURCE_AUTHENTICATED")
        self.assertFalse(r["provenance_independently_verified"])
        self.assertEqual(r["certified_take_count"],0)
    def test_rejects_future_source(self):
        row = dict(BASE, source_observed_at="2025-01-02T19:30:00+00:00")
        self.assertEqual(inspect([row])["status"],"BLOCKED")
    def test_rejects_duplicate(self):
        self.assertEqual(inspect([dict(BASE),dict(BASE)])["status"],"BLOCKED")
    def test_rejects_missing_hash(self):
        row = dict(BASE); del row["source_payload_sha256"]
        self.assertEqual(inspect([row])["status"],"BLOCKED")
    def test_rejects_market_without_league(self):
        row = dict(BASE, league="")
        self.assertEqual(inspect([row])["status"],"BLOCKED")

if __name__ == "__main__":
    unittest.main()
