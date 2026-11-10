"""Read-only full audit integration and contradictory report quarantine."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_audit_reconciliation import inspect_full
from v8_one_command import execute, selected


class FullAuditTests(unittest.TestCase):
    def test_new_phone_command_and_empty_receipts_fail_closed(self):
        self.assertEqual(selected("run_audit"), ())
        with tempfile.TemporaryDirectory() as root:
            r = execute("run_audit", output_dir=root)
            a = r["comprehensive_audit"]
            self.assertEqual(a["status"], "HOLD_MISSING_INDEPENDENT_MODEL_AND_PRICE_PROOF")
            self.assertIsNone(a["source_pregame_events_archived"])
            self.assertIsNone(a["nba_independently_qualified_training_games"])
            self.assertEqual(a["certified_champion_001_shadow_predictions"], 0)
            self.assertTrue((Path(root) / "FULL_AUDIT_REPORT.json").is_file())

    def _fixture(self, root):
        outcome = Path(root) / "outcome/prospective_validation"
        calibrate = Path(root) / "calibration/challenger_results"
        outcome.mkdir(parents=True)
        (calibrate / "calibration_evidence").mkdir(parents=True)
        (calibrate / "isotonic_recalibration").mkdir(parents=True)
        release = {
            "release_decision": "HOLD_NO_CERTIFIED_MODEL_NO_WAGERS",
            "champion_001_modified": False,
            "nba_structurally_valid_research_candidates": 76,
            "nba_directional_untrained_heuristic_research_picks": 76,
            "nba_independently_qualified_training_games": 0,
            "nba_independently_qualified_later_holdout_games": 0,
            "suspected_provider_scrambled_score_pattern_days": 4,
            "native_trained_probability_models_created": 0,
            "certified_champion_001_predictions": 0,
            "certified_challenger_001_predictions": 0,
            "certified_positive_ev_selections": 0,
            "automatic_wagers_placed": 0,
            "independently_verified_draftkings_checkout_prices": 0,
        }
        integrity = {
            "stage": "challenger_110_nba_provider_original_score_scramble_integrity",
            "champion_001_modified": False,
            "suspected_scrambled_score_pattern_days": 4,
            "dates_with_strong_suspected_transformed_score_pattern": [
                "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"],
            "licensed_provider_scores_accepted_for_training": 0,
            "licensed_provider_odds_accepted_for_positive_ev": 0,
            "untrusted_provider_scores_auto_corrected": 0,
        }
        ledger = {
            "champion_001_modified": False, "directional_nba_research_selections": 76,
            "certified_champion_001_predictions": 0, "certified_challenger_001_predictions": 0,
            "certified_positive_ev_selections": 0,
        }
        bridge = {
            "stage": "challenger_native_calibration_evidence_bridge_research_only",
            "champion_001_modified": False, "eligible_for_isotonic_fit": False,
            "independently_qualified_calibration_rows": 0,
            "certified_champion_001_predictions": 0,
            "certified_challenger_001_predictions": 0,
        }
        iso = {
            "stage": "challenger_001_daily_isotonic_recalibration_research_only",
            "status": "blocked_missing_prediction_evidence_file",
            "champion_001_modified": False, "research_artifacts_written": 0,
            "certified_champion_001_predictions": 0,
            "certified_challenger_001_predictions": 0,
            "certified_positive_ev_bets": 0,
        }
        for file, value in [
            (outcome / "challenger_model_master_diagnostic.json", release),
            (outcome / "nba_provider_score_integrity_diagnostic.json", integrity),
            (outcome / "nba_untrained_moneyline_shadow_ledger_report.json", ledger),
            (calibrate / "calibration_evidence/report.json", bridge),
            (calibrate / "isotonic_recalibration/report.json", iso),
        ]:
            file.write_text(json.dumps(value))
        return outcome.parent, calibrate.parent, outcome

    def test_reconciles_actual_report_shapes_without_certifying(self):
        with tempfile.TemporaryDirectory() as root:
            outcome, calibration, _ = self._fixture(root)
            r = inspect_full(outcome_dir=outcome, calibration_dir=calibration,
                             outcome_run_id=123, calibration_run_id=456)
            self.assertEqual(r["nba_original_research_candidates"], 76)
            self.assertEqual(r["nba_untrained_directional_research_selections"], 76)
            self.assertEqual(r["suspected_sportsdataio_scrambled_score_dates"], 4)
            self.assertEqual(r["training_shortfall_to_200"], 200)
            self.assertEqual(r["holdout_shortfall_to_50"], 50)
            self.assertEqual(r["calibration_status"], "blocked_missing_prediction_evidence_file")
            self.assertEqual(r["upstream_conflicts"], [])
            self.assertEqual(r["certified_positive_ev_bets"], 0)
            self.assertEqual(r["run_ids"]["outcome"], 123)

    def test_upstream_nonzero_certification_conflict_never_promoted(self):
        with tempfile.TemporaryDirectory() as root:
            outcome, calibration, base = self._fixture(root)
            p = base / "challenger_model_master_diagnostic.json"
            v = json.loads(p.read_text())
            v["certified_champion_001_predictions"] = 5
            p.write_text(json.dumps(v))
            r = inspect_full(outcome_dir=outcome, calibration_dir=calibration)
            self.assertEqual(r["status"], "HOLD_UPSTREAM_EVIDENCE_CONFLICTS")
            self.assertIn("release_untrusted_release_claim_certified_champion_001_predictions",
                          r["upstream_conflicts"])
            self.assertEqual(r["certified_champion_001_shadow_predictions"], 0)

    def test_inconsistent_score_pattern_count_quarantined(self):
        with tempfile.TemporaryDirectory() as root:
            outcome, calibration, base = self._fixture(root)
            p = base / "nba_provider_score_integrity_diagnostic.json"
            v = json.loads(p.read_text())
            v["dates_with_strong_suspected_transformed_score_pattern"].pop()
            p.write_text(json.dumps(v))
            a = inspect_full(outcome_dir=outcome, calibration_dir=calibration)
            self.assertIn("suspected_score_day_count_mismatch", a["upstream_conflicts"])
            self.assertEqual(a["certified_positive_ev_bets"], 0)

    def test_missing_outcome_is_unknown_not_zero_training(self):
        with tempfile.TemporaryDirectory() as root:
            a = inspect_full(outcome_dir=root)
            self.assertIsNone(a["nba_original_research_candidates"])
            self.assertIsNone(a["training_shortfall_to_200"])
            self.assertFalse(a["upstream_reports_found"]["release"])


if __name__ == "__main__":
    unittest.main()
