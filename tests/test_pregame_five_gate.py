import unittest
from datetime import datetime, timezone
from research.pregame_five_gate import run


class FiveGateTests(unittest.TestCase):
    def test_empty_slate(self):
        result = run({"sport": "nba", "selections": []},
                     now=datetime(2026, 11, 20, 22, 0, tzinfo=timezone.utc))
        self.assertEqual(result["counts"]["TAKE"], 0)

    def test_untrusted_claims_never_take(self):
        now = datetime(2026, 11, 20, 22, 0, tzinfo=timezone.utc)
        item = {"sport": "nba", "selection": "over",
                "injury_and_roster_evidence": {"verified": True},
                "quote": {"event_id": "e", "market": "points", "selection_id": "p",
                          "sportsbook": "DraftKings", "provider_record_id": "x",
                          "american_odds": -110, "observed_at": "2026-11-20T21:59:00Z",
                          "event_start_at": "2026-11-20T23:00:00Z",
                          "source_signature": "self-attested"},
                "forecast": {"event_id": "e", "market": "points", "selection_id": "p",
                             "model_id": "Champion-001", "model_probability": 0.7,
                             "predicted_at": "2026-11-20T21:59:00Z",
                             "forecast_run_id": "r", "model_artifact_sha256": "x",
                             "source_signature": "self-attested"}}
        result = run({"selections": [item]}, now=now)
        row = result["rows"][0]
        self.assertEqual(row["decision"], "HOLD")
        self.assertIsNone(row["verified_ev_percent"])
        self.assertIsNone(row["champion_001_probability_percent"])
        self.assertEqual(row["break_even_probability_percent"], 52.38)

    def test_invalid_snapshot(self):
        with self.assertRaises(ValueError):
            run({"selections": "not-a-list"})
