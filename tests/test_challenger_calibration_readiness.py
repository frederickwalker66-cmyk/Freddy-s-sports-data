"""Offline regression tests for calibration dependency diagnostics; no live sports data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_calibration_readiness import diagnose, main


def bridge(native=0, linked=0, staged=0):
    return {
        "stage": "challenger_native_calibration_evidence_bridge_research_only",
        "status": "blocked_no_native_challenger_forecasts",
        "native_forecast_rows_seen": native,
        "linked_rows_seen": linked,
        "unqualified_native_forecast_outcome_pairs_staged": staged,
        "independently_qualified_calibration_rows": 0,
        "calibration_evidence_file_created": False,
        "review_flags_automatically_promoted": False,
        "champion_001_modified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers_placed": 0,
    }


def isotonic(status="blocked_missing_prediction_evidence_file"):
    return {
        "stage": "challenger_001_daily_isotonic_recalibration_research_only",
        "status": status,
        "research_artifacts_written": 0,
        "champion_001_modified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers_placed": 0,
    }


class DiagnosticTests(unittest.TestCase):
    def test_original_missing_native_rows_identified_not_faked(self):
        result = diagnose(bridge(linked=4), isotonic())
        self.assertEqual(result["primary_blocker"], "missing_native_challenger_pregame_forecasts")
        self.assertEqual(result["linked_published_outcomes_found"], 4)
        self.assertEqual(result["native_pregame_forecasts_found"], 0)
        self.assertEqual(result["status"], "HOLD_RESEARCH_ONLY")
        self.assertFalse(result["calibration_input_created"])
        self.assertFalse(result["review_queue_promoted"])
        self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_other_gaps_are_distinguished(self):
        self.assertEqual(diagnose(bridge(native=3), isotonic())["primary_blocker"],
                         "missing_linked_published_outcomes")
        self.assertEqual(diagnose(bridge(native=3, linked=2), isotonic())["primary_blocker"],
                         "no_valid_native_forecast_outcome_matches")
        self.assertEqual(diagnose(bridge(native=3, linked=2, staged=1), isotonic())["primary_blocker"],
                         "missing_independently_reviewed_calibration_input")

    def test_file_presence_cannot_certify_or_promote(self):
        result = diagnose(bridge(native=250, linked=250, staged=250),
                          isotonic(), evidence_exists=True)
        self.assertEqual(result["primary_blocker"], "independent_input_and_fit_require_manual_review")
        self.assertTrue(result["separate_calibration_input_present_not_authenticated"])
        self.assertFalse(result["independently_authenticated_by_this_diagnostic"])
        self.assertFalse(result["verified_betting_edge"])
        self.assertFalse(result["champion_001_modified"])
        self.assertEqual(result["certified_champion_001_predictions"], 0)

    def test_fail_closed_on_untrusted_bridge_promotion(self):
        changed = bridge(native=250, linked=250, staged=250)
        changed["independently_qualified_calibration_rows"] = 250
        with self.assertRaisesRegex(ValueError, "no authority"):
            diagnose(changed, isotonic())
        changed = bridge()
        changed["calibration_evidence_file_created"] = True
        with self.assertRaisesRegex(ValueError, "trusted calibration input"):
            diagnose(changed, isotonic())

    def test_fail_closed_on_champion_or_wager_modification(self):
        modified = isotonic()
        modified["champion_001_modified"] = True
        with self.assertRaisesRegex(ValueError, "Champion safety"):
            diagnose(bridge(), modified)
        modified = isotonic()
        modified["automated_wagers_placed"] = 1
        with self.assertRaisesRegex(ValueError, "betting/certification"):
            diagnose(bridge(), modified)

    def test_rejects_forged_or_malformed_counts(self):
        for value in (-1, True, "25", None):
            modified = bridge()
            modified["native_forecast_rows_seen"] = value
            with self.assertRaises(ValueError):
                diagnose(modified, isotonic())
        with self.assertRaises(ValueError):
            diagnose({}, isotonic())

    def test_cli_outputs_diagnostics_only_and_never_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge_report = root / "bridge.json"
            calibration_report = root / "calibration.json"
            out = root / "output"
            bridge_report.write_text(json.dumps(bridge(linked=7)))
            calibration_report.write_text(json.dumps(isotonic()))
            evidence = root / "challenger_oos_probabilities.jsonl"
            self.assertEqual(main([
                "--bridge-report", str(bridge_report),
                "--calibration-report", str(calibration_report),
                "--evidence", str(evidence),
                "--output-dir", str(out),
            ]), 0)
            self.assertEqual(sorted(path.name for path in out.iterdir()),
                             ["DEPENDENCY_STATUS.md", "dependency_diagnostic.json"])
            self.assertFalse(evidence.exists())
            status = json.loads((out / "dependency_diagnostic.json").read_text())
            self.assertEqual(status["primary_blocker"],
                             "missing_native_challenger_pregame_forecasts")
            self.assertIn("HOLD", (out / "DEPENDENCY_STATUS.md").read_text())

    def test_cli_existing_local_file_never_claims_authentication(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.json").write_text(json.dumps(bridge(native=2, linked=2, staged=1)))
            (root / "c.json").write_text(json.dumps(isotonic()))
            path = root / "unreviewed.jsonl"
            path.write_text('{"model_probability":0.99}\n')
            out = root / "out"
            self.assertEqual(main([
                "--bridge-report", str(root / "b.json"),
                "--calibration-report", str(root / "c.json"),
                "--evidence", str(path),
                "--output-dir", str(out),
            ]), 0)
            r = json.loads((out / "dependency_diagnostic.json").read_text())
            self.assertFalse(r["independently_authenticated_by_this_diagnostic"])
            self.assertEqual(r["certified_challenger_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
