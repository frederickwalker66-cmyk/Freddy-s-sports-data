"""Synthetic-only tests of chronological research calibration, never wagers."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_isotonic_recalibration import recalibrate, apply_research_calibrator, main

UTC = timezone.utc


def synthetic(n=360):
    base = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        d = base + timedelta(days=i)
        frac = (i % 20) / 19
        raw = 0.1 + 0.8 * frac
        outcome = int(((i * 47 + 13) % 101) / 101 < 0.35 + 0.3 * frac)
        rows.append({
            "league": "nba", "market_type": "moneyline", "selection_key": "home",
            "model_version": "challenger-001-nba-home-moneyline-v1",
            "event_id": f"synthetic_{i:04}",
            "probability_source": "native_challenger_model",
            "prediction_timestamp_utc": (d - timedelta(hours=2)).isoformat(),
            "event_start_utc": d.isoformat(),
            "outcome_verified_at_utc": (d + timedelta(hours=4)).isoformat(),
            "model_probability": raw,
            "settlement": "WIN" if outcome else "LOSS",
            "outcome": outcome,
            "independent_outcome_verified": True,
            "historical_pregame_features_verified": True,
            "model_output_before_event_verified": True,
            "chronological_holdout": True,
            "model_training_excludes_holdout": True,
            "independent_pregame_receipt_verified": True,
            "champion_001_modified": False,
        })
    return rows


class TestResearchIsotonic(unittest.TestCase):
    def setUp(self):
        self.as_of = datetime(2026, 11, 5, tzinfo=UTC)

    def test_empty_fails_closed(self):
        report, artifacts = recalibrate([], as_of=self.as_of)
        self.assertEqual(report["research_artifacts_written"], 0)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(artifacts)

    def test_chronological_holdout_and_artifact_remain_research(self):
        report, artifacts = recalibrate(synthetic(), as_of=self.as_of)
        group = report["groups"][0]
        self.assertGreaterEqual(group["calibration_rows"], 200)
        self.assertGreaterEqual(group["evaluation_rows"], 50)
        self.assertIn("raw_holdout", group)
        self.assertIn("isotonic_holdout", group)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertTrue(artifacts, "Synthetic fixture should exercise saved artifact")
        artifact = next(iter(artifacts.values()))
        p = apply_research_calibrator(
            artifact, 0.3, league="nba", market_type="moneyline",
            selection_key="home", model_version="challenger-001-nba-home-moneyline-v1"
        )
        self.assertGreaterEqual(p, 0)
        self.assertLessEqual(p, 1)
        self.assertFalse(artifact["bet_ready"])
        with self.assertRaises(ValueError):
            apply_research_calibrator(
                artifact, 0.3, league="nba", market_type="player_points",
                selection_key="over", model_version="challenger-001-nba-home-moneyline-v1"
            )

    def test_rejects_sportsbook_break_even_and_frozen_champion(self):
        rows = synthetic(1)
        rows[0]["probability_source"] = "sportsbook_implied"
        report, artifacts = recalibrate(rows, as_of=self.as_of)
        self.assertIn("not_a_native_challenger_probability", report["excluded"])
        self.assertFalse(artifacts)
        rows = synthetic(1)
        rows[0]["model_version"] = "champion-001"
        report, artifacts = recalibrate(rows, as_of=self.as_of)
        self.assertIn("not_a_challenger_model_version", report["excluded"])
        self.assertFalse(artifacts)

    def test_excludes_future_or_unsettled_results(self):
        rows = synthetic(1)
        rows[0]["outcome_verified_at_utc"] = "2030-01-01T00:00:00+00:00"
        report, _ = recalibrate(rows, as_of=self.as_of)
        self.assertIn("not_valid_pregame_or_settled_timing", report["excluded"])

    def test_past_outcomes_not_known_at_holdout_capture_are_ineligible(self):
        rows = synthetic()
        for row in rows[:288]:
            row["outcome_verified_at_utc"] = "2026-10-20T00:00:00+00:00"
        report, artifacts = recalibrate(rows, as_of=self.as_of)
        self.assertEqual(report["groups"][0]["status"],
                         "blocked_insufficient_chronological_split_or_classes")
        self.assertFalse(artifacts)

    def test_duplicate_forecasts_fail_closed(self):
        rows = synthetic()
        rows[1]["event_id"] = rows[0]["event_id"]
        report, artifacts = recalibrate(rows, as_of=self.as_of)
        self.assertEqual(report["groups"][0]["status"], "blocked_duplicate_event_or_forecast")
        self.assertFalse(artifacts)

    def test_missing_file_writes_blocked_report(self):
        with TemporaryDirectory() as folder:
            output = Path(folder) / "out"
            rc = main(["--evidence", str(Path(folder) / "missing.jsonl"),
                       "--output-dir", str(output), "--allow-missing-evidence"])
            self.assertEqual(rc, 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "blocked_missing_prediction_evidence_file")
            self.assertEqual(report["research_artifacts_written"], 0)
            self.assertEqual([p.name for p in output.iterdir()], ["report.json"])
            self.assertFalse(report["champion_001_modified"])

    def test_artifact_integrity_check_fails_closed(self):
        report, artifacts = recalibrate(synthetic(), as_of=self.as_of)
        self.assertTrue(artifacts)
        damaged = dict(next(iter(artifacts.values())), bet_ready=True)
        with self.assertRaisesRegex(ValueError, "integrity"):
            apply_research_calibrator(
                damaged, 0.55, league="nba", market_type="moneyline",
                selection_key="home", model_version="challenger-001-nba-home-moneyline-v1"
            )


if __name__ == "__main__":
    unittest.main()
