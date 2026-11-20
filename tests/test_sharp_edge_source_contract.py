import unittest
from datetime import datetime, timezone
from research.sharp_edge_source_contract import validate_pair


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 22, 0, tzinfo=timezone.utc)
        self.quote = {
            "event_id": "event1", "market": "assists", "selection_id": "p1_over",
            "sportsbook": "DraftKings", "provider_record_id": "q1",
            "american_odds": -110, "observed_at": "2026-11-20T21:59:00Z",
            "event_start_at": "2026-11-20T23:00:00Z", "source_signature": "unverified-claim",
        }
        self.forecast = {
            "event_id": "event1", "market": "assists", "selection_id": "p1_over",
            "model_id": "Champion-001", "model_probability": 0.6,
            "predicted_at": "2026-11-20T21:58:00Z",
            "forecast_run_id": "r1", "model_artifact_sha256": "claim",
            "source_signature": "unverified-claim",
        }

    def test_complete_claims_are_still_hold(self):
        result = validate_pair(self.quote, self.forecast, now=self.now)
        self.assertTrue(result["ready_for_authentication"])
        self.assertFalse(result["certified"])
        self.assertEqual(result["decision"], "HOLD")

    def test_mismatched_selection_rejected(self):
        forecast = dict(self.forecast, selection_id="other")
        self.assertIn("market_identity_mismatch:selection_id",
                      validate_pair(self.quote, forecast, now=self.now)["issues"])

    def test_stale_quote_rejected(self):
        quote = dict(self.quote, observed_at="2026-11-20T21:30:00Z")
        self.assertIn("stale_future_or_missing_quote",
                      validate_pair(quote, self.forecast, now=self.now)["issues"])

    def test_started_game_rejected(self):
        quote = dict(self.quote, event_start_at="2026-11-20T21:00:00Z")
        self.assertIn("event_already_started_or_unknown",
                      validate_pair(quote, self.forecast, now=self.now)["issues"])

    def test_implied_probability_not_native(self):
        forecast = dict(self.forecast, model_id="market_implied")
        self.assertIn("not_frozen_champion_001",
                      validate_pair(self.quote, forecast, now=self.now)["issues"])
