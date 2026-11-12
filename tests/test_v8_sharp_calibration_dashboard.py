"""No fake calibration: only saved original research paired with mature finals."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_forward_calibration import calibrate
from v8_sharp_calibration_dashboard import MARKET_KEYS, dashboard
from v8_one_command import execute


def saved_zero_grades():
    return {
        "version": "v8-nba-forward-calibration-v1",
        "stage": "genuinely_forward_recorded_NBA_research_calibration_only",
        "status": "HOLD_WAITING_FOR_100_FORWARD_GRADED_AND_WELL_POPULATED_BINS",
        "archived_original_forward_forecasts": 28,
        "graded_research_NBA_games": 0, "pending_ungraded": 28, "quarantined": 0,
        "models": [], "champion_001_modified": False, "bet_ready": False,
        "data_is_independently_publisher_authenticated": False,
        "original_Champion_001_certified_shadows": 0,
        "certified_positive_ev_bets": 0, "independently_certified_models": 0,
        "independently_verified_sportsbook_checkout_quotes": 0,
    }


def synthetic_forward_report(n):
    # SYNTHETIC OFFLINE TEST-ONLY future support. No test pairs in saved production.
    pairs = [
        {"version":"v8-nba-elo-forward-research-v0-fixed-k20-ha60",
         "p":0.56,"y":i % 2,"date_et":f"2026-01-{1+i%5:02d}",
         "start":datetime(2026,1,1,tzinfo=timezone.utc)}
        for i in range(n)
    ]
    totals = {"archived":n, "completed":n,
              "pending_ungraded":0, "quarantined":0}
    return calibrate(pairs,totals)


class SharpCalibrationDashboardTests(unittest.TestCase):
    def test_absent_calibration_never_invents_zero_grades(self):
        r=dashboard(None)
        self.assertEqual(set(r["market_calibration"]),set(MARKET_KEYS))
        self.assertEqual(r["persisted_nba_original_forward_calibration_status"],
                         "NOT_YET_PERSISTED")
        self.assertIsNone(r["nba_original_archived_forecasts"])
        self.assertIsNone(r["nba_original_graded_outcomes"])
        self.assertIsNone(r["market_calibration"]["nba_moneyline"]
                          ["research_brier_score"])
        for item in r["market_calibration"].values():
            self.assertIsNone(item["calibration_adjusted_probability"])
            self.assertIsNone(item["research_expected_calibration_error"])
            self.assertFalse(item["independently_certified"])
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertFalse(r["champion_001_modified"])

    def test_valid_saved_28_zero_grade_is_explicitly_held(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"CALIBRATION.json"
            path.write_text(json.dumps(saved_zero_grades()))
            r=dashboard(path)
        self.assertEqual(r["nba_original_archived_forecasts"],28)
        self.assertEqual(r["nba_original_graded_outcomes"],0)
        self.assertEqual(r["nba_original_pending_grading"],28)
        self.assertEqual(r["market_calibration"]["nba_moneyline"]
                         ["eligible_original_model_forecasts_graded"],0)
        self.assertIsNone(r["market_calibration"]["nba_moneyline"]
                          ["research_brier_score"])
        self.assertEqual(r["minimum_exploratory_brier_graded_games"],50)
        self.assertEqual(r["minimum_exploratory_ece_graded_games"],100)
        self.assertEqual(r["decision"],
                         "HOLD_NO_INDEPENDENTLY_CERTIFIED_EXACT_MARKET_CALIBRATION")

    def test_exact_market_boundaries_no_transferring_nba_to_nfl_or_props(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"CALIBRATION.json"
            p.write_text(json.dumps(synthetic_forward_report(100)))
            report=dashboard(p)
        nba=report["market_calibration"]["nba_moneyline"]
        self.assertEqual(nba["eligible_original_model_forecasts_graded"],100)
        self.assertIsNotNone(nba["research_brier_score"])
        self.assertIsNotNone(nba["research_expected_calibration_error"])
        self.assertEqual(len(nba["calibration_probability_bin_diagnostics"]),5)
        self.assertIsNone(nba["calibration_adjusted_probability"])
        for key in MARKET_KEYS:
            if key == "nba_moneyline":
                continue
            item=report["market_calibration"][key]
            self.assertIsNone(item["eligible_original_model_forecasts_graded"])
            self.assertIsNone(item["research_brier_score"])
            self.assertIsNone(item["research_expected_calibration_error"])
            self.assertEqual(item["status"],
                             "NOT_AVAILABLE_NO_VERIFIED_PREGAME_FORECAST_OUTCOME_PAIRS")
        self.assertFalse(report["calibration_certified"])
        self.assertFalse(report["native_calibration_applied_to_current_sharp_edge_quotes"])

    def test_brier_only_at_50_ece_not_before_100(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"CALIBRATION.json"
            p.write_text(json.dumps(synthetic_forward_report(50)))
            report=dashboard(p)
        nba=report["market_calibration"]["nba_moneyline"]
        self.assertIsNotNone(nba["research_brier_score"])
        self.assertIsNotNone(nba["research_log_loss"])
        self.assertIsNone(nba["research_expected_calibration_error"])
        self.assertFalse(nba["bet_ready"])

    def test_forged_certification_or_inconsistent_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"CALIBRATION.json"
            data=saved_zero_grades()
            for change in (
                {"certified_positive_ev_bets":4},
                {"champion_001_modified":True},
                {"graded_research_NBA_games":2},
                {"data_is_independently_publisher_authenticated":True},
            ):
                with self.subTest(change=change):
                    modified=dict(data,**change)
                    p.write_text(json.dumps(modified))
                    r=dashboard(p)
                    self.assertEqual(r["persisted_nba_original_forward_calibration_status"],
                                     "REJECTED_INCONSISTENT_OR_UNTRUSTED_CALIBRATION_EVIDENCE")
                    self.assertIsNone(r["nba_original_graded_outcomes"])
                    self.assertFalse(r["calibration_certified"])
                    self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_garbage_calibration_does_not_break_historical_price_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"CALIBRATION.json"
            f.write_text("{not-json")
            o=Path(folder)/"results"
            r=execute("run_nfl_props_edge",sharp_rows=[],
                      calibration_file=f,output_dir=o)
            self.assertEqual(r["sharp_edge_calibration"]
                             ["persisted_nba_original_forward_calibration_status"],
                             "REJECTED_INCONSISTENT_OR_UNTRUSTED_CALIBRATION_EVIDENCE")
            self.assertTrue((o/"NBA_NFL_SHARP_EDGE_CALIBRATION.json").is_file())
            self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_sharp_edge_report_and_json_expose_source_provenance_only(self):
        with tempfile.TemporaryDirectory() as folder:
            c=Path(folder)/"CALIBRATION.json"
            c.write_text(json.dumps(saved_zero_grades()))
            o=Path(folder)/"output"
            result=execute("run_nfl_props_edge",sharp_rows=[],
                           calibration_file=c,output_dir=o)
            status=result["sharp_edge_calibration"]
            self.assertEqual(status["nba_original_graded_outcomes"],0)
            self.assertEqual(result["nfl_and_player_props_edge_research"]
                             ["nba_original_forward_games_graded_for_calibration"],0)
            self.assertTrue((o/"NBA_NFL_SHARP_EDGE_CALIBRATION.json").is_file())
            saved=json.loads((o/"NBA_NFL_SHARP_EDGE_CALIBRATION.json").read_text())
            self.assertEqual(saved,status)
            self.assertTrue(saved["sportsbook_implied_probabilities_are_not_calibration_data"])
            self.assertEqual(saved["automated_wagers"],0)
            self.assertFalse(saved["champion_001_modified"])

    def test_original_run_calibration_remains_separate_and_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            c=Path(folder)/"CALIBRATION.json"
            c.write_text(json.dumps(saved_zero_grades()))
            r=execute("run_calibration",calibration_file=c,
                      output_dir=Path(folder)/"research")
            self.assertEqual(r["forward_calibration"]["graded_research_NBA_games"],0)
            self.assertIsNone(r["sharp_edge_calibration"])
            self.assertEqual(r["certified_positive_ev_bets"],0)


if __name__=="__main__":
    unittest.main()
