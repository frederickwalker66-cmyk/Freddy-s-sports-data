import unittest

from research.independent_champion_calibration import evaluate


def row(event, p, outcome):
    return {"model_id": "Champion-001", "event_id": str(event),
            "selection_id": "home", "model_probability": p,
            "outcome": outcome, "model_artifact_sha256": "a"*64,
            "predicted_at": "2026-11-20T18:00:00Z",
            "event_start_at": "2026-11-20T19:00:00Z"}


class CalibrationTests(unittest.TestCase):
    def test_calibration_metrics_do_not_certify(self):
        result = evaluate([row(1, .8, 1), row(2, .2, 0)], minimum=2)
        self.assertAlmostEqual(result["brier_score"], .04)
        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(result["certified_take_count"], 0)
        self.assertEqual(result["certification"], "HOLD")

    def test_reject_leakage_and_duplicate(self):
        later = row(2, .5, 1)
        later["predicted_at"] = later["event_start_at"]
        result = evaluate([row(1, .7, 1), row(1, .7, 1), later])
        self.assertEqual(result["sample_size"], 1)
        self.assertEqual(len(result["rejected"]), 2)

    def test_empty_records(self):
        result = evaluate([])
        self.assertIsNone(result["brier_score"])
        self.assertEqual(result["certified_take_count"], 0)
