"""Regression contract for fail-closed calibration artifact recovery.

These tests enforce software guardrails only. They do not authenticate a
forecast, certify a sportsbook price, or demonstrate prediction accuracy.
"""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/challenger-isotonic-calibration.yml"


class CalibrationArchiveWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_search_does_not_stop_on_code_only_or_empty_artifact(self):
        script = self.workflow.split("name: Recover recent available pregame/outcome artifacts", 1)[1].split(
            "name: Crosslink native Challenger receipts", 1
        )[0]
        self.assertIn("prospective_pregame/native_challenger_forecasts.jsonl", script)
        self.assertIn("prospective_validation/linked_pregame_outcomes.jsonl", script)
        self.assertIn('if [[ ! -s "$required" ]]', script)
        self.assertIn('rm -rf "calibration_sources/$kind/$run_id"', script)
        self.assertLess(script.index('if [[ ! -s "$required" ]]'), script.index("found=true"))
        self.assertIn("continue", script.split('if [[ ! -s "$required" ]]', 1)[1].split("found=true")[0])
        self.assertIn("--limit 75", script)

    def test_successful_ci_is_not_reported_as_calibration(self):
        self.assertIn("Display actual calibration readiness (not CI job status)", self.workflow)
        self.assertIn("GITHUB_STEP_SUMMARY", self.workflow)
        self.assertIn("cal.get('status', 'not_executed')", self.workflow)
        self.assertIn("unqualified_native_forecast_outcome_pairs_staged", self.workflow)
        self.assertIn("independently_qualified_calibration_rows", self.workflow)
        self.assertIn("research_artifacts_written", self.workflow)

    def test_root_cause_diagnostics_do_not_create_evidence(self):
        self.assertIn("test_challenger_calibration_readiness.py", self.workflow)
        self.assertIn("name: Explain missing native forecast evidence", self.workflow)
        self.assertIn("python challenger_calibration_readiness.py", self.workflow)
        self.assertIn("--bridge-report challenger_results/calibration_evidence/report.json", self.workflow)
        self.assertIn("--calibration-report challenger_results/isotonic_recalibration/report.json", self.workflow)
        self.assertIn("DEPENDENCY_STATUS.md", self.workflow)
        self.assertIn(
            "test ! -e challenger_results/calibration_evidence/challenger_oos_probabilities.jsonl",
            self.workflow,
        )

    def test_frozen_champion_and_no_synthetic_data_promotion(self):
        self.assertIn("assert r['champion_001_modified'] is False", self.workflow)
        self.assertIn("assert r['independently_qualified_calibration_rows'] == 0", self.workflow)
        self.assertIn("assert r['certified_champion_001_predictions'] == 0", self.workflow)
        self.assertIn("assert r['calibration_evidence_file_created'] is False", self.workflow)
        self.assertIn("--allow-missing-evidence", self.workflow)


if __name__ == "__main__":
    unittest.main()
