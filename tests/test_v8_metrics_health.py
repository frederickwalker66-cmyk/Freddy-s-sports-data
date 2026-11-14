"""Evidence-gated metrics upgrade: never imply 14 games certify predictive skill."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_forward_calibration import calibrate
from v8_forward_calibration_view import read_calibration
from v8_metrics_health import build_metrics_health
from v8_one_command import execute


def source_calibration(n, pending=0):
    # Deterministic genuine-schema fixture; synthetic rows, not real matches.
    pairs = [{
        "version": "nba-synthetic-test-only",
        "p": 0.55 if i % 2 else 0.64,
        "y": i % 3 == 0 and 1 or 0,
        "date_et": f"2026-10-{(i % 24)+1:02d}",
    } for i in range(n)]
    return calibrate(pairs, {
        "archived": n + pending,
        "completed": n,
        "pending_ungraded": pending,
        "quarantined": 0,
    })


class MetricsHealthTests(unittest.TestCase):
    def test_no_saved_evidence_does_not_invent_counts(self):
        r = build_metrics_health(calibration_file=None)
        self.assertIsNone(r["nba_grade_coverage_percent"])
        self.assertIsNone(r["additional_nba_grades_to_50"])
        self.assertEqual(r["model_reliability_diagnostics"], [])
        self.assertIsNone(r["nba_graded_research_games"])
        self.assertFalse(r["bet_ready"])
        self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_14_grades_show_coverage_and_base_rate_not_false_accuracy(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Path(directory) / "CALIBRATION.json"
            f.write_text(json.dumps(source_calibration(14, pending=28)))
            r = build_metrics_health(calibration_file=f,
                market_evidence={"nba": {
                    "archived_provider_quote_rows": 5624,
                    "fresh_paired_game_boards": 0,
                    "fresh_paired_player_prop_markets": 0,
                    "primary_source_blocker": "NO_FRESH_EXACT_PAIRED_MARKETS",
                }})
            self.assertEqual(r["nba_archived_original_forward_forecasts"], 42)
            self.assertEqual(r["nba_graded_research_games"], 14)
            self.assertEqual(r["nba_grade_coverage_percent"], 33.3)
            self.assertEqual(r["additional_nba_grades_to_50"], 36)
            self.assertEqual(r["additional_nba_grades_to_100"], 86)
            self.assertEqual(r["source_market_diagnostics_by_league"]["nba"]
                             ["archived_quote_rows"], 5624)
            self.assertEqual(r["source_market_diagnostics_by_league"]["nba"]
                             ["fresh_paired_prop_markets"], 0)
            m = r["model_reliability_diagnostics"][0]
            self.assertEqual(m["graded_forecasts"], 14)
            self.assertEqual(sum(x["observations"] for x in
                                 m["observed_bin_distribution"]), 14)
            lo, hi = m["home_win_base_rate_Wilson_95pct_NOT_MODEL_ACCURACY"]
            self.assertLess(lo, hi)
            self.assertIsNone(m["research_directional_accuracy"])
            self.assertIsNone(m["research_Brier"])
            self.assertIsNone(m["research_Brier_skill_vs_fixed_50_50_NOT_sportsbook"])
            self.assertIsNone(m["exploratory_expected_calibration_error"])
            self.assertFalse(r["native_calibrator_fitted"])
            self.assertEqual(r["money_wagered_usd"], 0)

    def test_50_graded_reports_new_metrics_but_no_certification(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Path(directory) / "CALIBRATION.json"
            f.write_text(json.dumps(source_calibration(50)))
            d = read_calibration(f)
            m = d["models"][0]
            self.assertEqual(m["research_directional_decisions"], 50)
            self.assertIsInstance(m["research_directional_accuracy"], float)
            self.assertEqual(len(m["research_directional_accuracy_wilson_95pct"]), 2)
            self.assertIsInstance(
                m["research_Brier_skill_vs_fixed_50_50_NOT_sportsbook"], float)
            self.assertIsInstance(
                m["research_log_loss_skill_vs_fixed_50_50_NOT_sportsbook"], float)
            self.assertIsNone(m["exploratory_expected_calibration_error"])
            h = build_metrics_health(calibration_file=f)
            self.assertEqual(h["additional_nba_grades_to_50"], 0)
            self.assertEqual(h["additional_nba_grades_to_100"], 50)
            self.assertFalse(h["bet_ready"])

    def test_cannot_release_new_skill_metrics_early(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Path(directory) / "CALIBRATION.json"
            d = source_calibration(14)
            d["models"][0]["research_directional_accuracy"] = .99
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, "premature_small_sample_skill_claim"):
                read_calibration(f)
            d = source_calibration(50)
            d["models"][0]["research_directional_correct"] = 51
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, "invalid_research_directional_counts"):
                read_calibration(f)

    def test_direct_run_calibration_writes_metrics_health_json(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Path(directory) / "CALIBRATION.json"
            f.write_text(json.dumps(source_calibration(14, pending=28)))
            out = Path(directory) / "out"
            r = execute("run_calibration", calibration_file=str(f),
                        output_dir=out, now=datetime(2026,11,14,tzinfo=timezone.utc))
            self.assertEqual(r["metrics_health"]["nba_grade_coverage_percent"], 33.3)
            saved = json.loads((out / "METRICS_HEALTH.json").read_text())
            self.assertEqual(saved["additional_nba_grades_to_50"], 36)
            self.assertFalse(saved["champion_001_modified"])

    def test_market_evidence_bad_counts_do_not_claim_data_quality(self):
        with self.assertRaisesRegex(ValueError, "invalid_market_evidence_counts"):
            build_metrics_health(market_evidence={"nba": {
                "archived_provider_quote_rows": -12,
                "fresh_paired_game_boards": 0,
                "fresh_paired_player_prop_markets": 0,
            }})


if __name__ == "__main__":
    unittest.main()
