"""Offline regression tests for V8 NBA chronological ensemble."""
import unittest
from datetime import datetime, timedelta, timezone

from v8_nba_ensemble_research import evaluate


def row(index):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    winner = index % 2 == 0
    return {
        "league": "nba", "market": "home_moneyline", "season_type": 2,
        "champion_001_modified": False,
        "independent_pregame_review": True, "independent_outcome_review": True,
        "event_id": str(100000 + index),
        "start_utc": start.isoformat(),
        "forecast_recorded_utc": (start - timedelta(hours=1)).isoformat(),
        "outcome_verified_utc": (start + timedelta(hours=3)).isoformat(),
        "probabilities": {"elo": .58 if winner else .42,
                          "logistic": .55 if winner else .45,
                          "tree": .54 if winner else .46},
        "component_provenance": {
            component: {
                "model_version": f"v8-{component}-research-test",
                "training_data_cutoff_utc": (start - timedelta(days=3)).isoformat(),
                "model_trained_utc": (start - timedelta(days=2)).isoformat(),
                "forecast_recorded_utc": (start - timedelta(hours=2)).isoformat(),
            }
            for component in ("elo", "logistic", "tree")
        },
        "home_won": winner,
    }


class V8NBAEnsembleTests(unittest.TestCase):
    def test_empty_is_blocked(self):
        result = evaluate([])
        self.assertEqual(result["status"], "blocked_insufficient_independent_evidence")
        self.assertFalse(result["bet_ready"])

    def test_chronological_holdout(self):
        result = evaluate([row(i) for i in range(120)])
        self.assertEqual(result["status"], "evaluated_research_only")
        self.assertGreaterEqual(result["holdout_games"], 50)
        self.assertGreaterEqual(result["calibration_games"], 50)
        self.assertEqual(sum(result["ensemble_weights"].values()), 1.0)
        self.assertEqual(result["certified_predictions"], 0)
        self.assertFalse(result["externally_certified"])

    def test_future_forecast_rejected(self):
        records = [row(i) for i in range(120)]
        records[0]["forecast_recorded_utc"] = records[0]["start_utc"]
        with self.assertRaisesRegex(ValueError, "temporal_leakage"):
            evaluate(records)

    def test_duplicate_rejected(self):
        records = [row(0), row(0)]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(records)

    def test_missing_review_rejected(self):
        record = row(0)
        record["independent_outcome_review"] = False
        with self.assertRaisesRegex(ValueError, "independent_reviews_missing"):
            evaluate([record])

    def test_draw_and_soccer_not_accepted(self):
        record = row(0)
        record["league"] = "mls"
        with self.assertRaisesRegex(ValueError, "nba_only"):
            evaluate([record])

    def test_future_trained_tree_rejected(self):
        record = row(0)
        record["component_provenance"]["tree"]["model_trained_utc"] = record["start_utc"]
        with self.assertRaisesRegex(ValueError, "component_training_or_forecast_leakage"):
            evaluate([record])

    def test_missing_component_provenance_rejected(self):
        record = row(0)
        del record["component_provenance"]["logistic"]
        with self.assertRaisesRegex(ValueError, "component_provenance_missing"):
            evaluate([record])

    def test_postgame_component_prediction_rejected(self):
        record = row(0)
        record["component_provenance"]["elo"]["forecast_recorded_utc"] = record["outcome_verified_utc"]
        with self.assertRaisesRegex(ValueError, "component_training_or_forecast_leakage"):
            evaluate([record])

    def test_same_day_not_split(self):
        records = [row(i) for i in range(120)]
        # Force a batch of same-day games at holdout threshold.
        for i in (68, 69, 70):
            records[i]["start_utc"] = records[70]["start_utc"]
            records[i]["forecast_recorded_utc"] = records[70]["forecast_recorded_utc"]
            records[i]["outcome_verified_utc"] = records[70]["outcome_verified_utc"]
        result = evaluate(records)
        self.assertFalse(result["bet_ready"])
        self.assertGreaterEqual(result["holdout_games"], 50)


if __name__ == "__main__":
    unittest.main()
