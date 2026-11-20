import unittest
from datetime import datetime, timezone
from research.sharp_edge_source_readiness import audit


class SourceReadinessTests(unittest.TestCase):
    def test_missing_evidence_holds(self):
        result = audit({"markets": [{"selection_id": "a"}]})
        self.assertEqual(result["certified_takes"], 0)
        self.assertEqual(result["markets"][0]["decision"], "HOLD")
        self.assertIn("missing_native_champion_receipt", result["markets"][0]["issues"])

    def test_forged_complete_evidence_still_holds(self):
        row = dict(source="SportsGameOdds", source_record_id="fake-1",
                   observed_at="2026-11-20T19:00:00+00:00", event_id="game",
                   market="moneyline", selection_id="home", sportsbook="DraftKings",
                   american_odds=-110, champion_model_id="Champion-001",
                   champion_forecast_receipt="claimed", independent_verification_receipt="claimed")
        result = audit({"markets": [row]}, now=datetime(2026, 11, 20, 19, 1, tzinfo=timezone.utc))
        self.assertEqual(result["certified_takes"], 0)
        self.assertIn("source_receipts_not_cryptographically_authenticated",
                      result["markets"][0]["issues"])

    def test_empty_market_set_is_not_certified(self):
        self.assertEqual(audit({"markets": []})["certified_takes"], 0)

    def test_invalid_market_structure_rejected(self):
        with self.assertRaises(ValueError):
            audit({"markets": {}})
