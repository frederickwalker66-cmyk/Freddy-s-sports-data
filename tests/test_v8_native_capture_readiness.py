"""Synthetic safety tests for the read-only V8 native capture readiness gate."""
from copy import deepcopy
import unittest

from v8_native_capture_readiness import LEAGUES, assess


def sample():
    nba = {
        "status": "blocked_missing_or_invalid_research_model",
        "model_path_exists": False,
        "research_model_artifact_present_and_format_valid": False,
        "candidate_rows_supplied": 0,
        "actual_native_research_forecasts_written": 0,
        "champion_001_modified": False,
    }
    multi = {
        "per_league_model_gate": {
            k: ("delegated_to_existing_nba_specialist_recorder" if k == "nba"
                else "blocked_model_missing") for k in LEAGUES
        },
        "models_present": [],
        "candidate_rows_received": 0,
        "market_selections_captured_uncertified": 0,
        "champion_001_modified": False,
    }
    for report in (nba, multi):
        for key in ("certified_champion_001_predictions",
                    "certified_challenger_001_predictions",
                    "certified_positive_ev_bets",
                    "bet_ready_selections", "automated_bets_placed"):
            report[key] = 0
    snap = [{"league": "nba", "bet_ready": False,
             "champion_001_modified": False}]
    return snap, nba, multi, [], []


class NativeReadinessTests(unittest.TestCase):
    def test_missing_native_model_does_not_certify_predictions(self):
        r = assess(*sample())
        self.assertEqual(r["status"], "blocked_missing_or_invalid_native_model_artifacts")
        self.assertEqual(set(r["missing_or_invalid_model_leagues"]), set(LEAGUES))
        self.assertEqual(r["by_league"]["nba"]["original_pregame_source_snapshots"], 1)
        self.assertFalse(r["calibration_qualified"])
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertFalse(r["champion_001_modified"])

    def test_model_file_alone_does_not_count_as_usable(self):
        args = sample()
        args[1]["model_path_exists"] = True
        r = assess(*args)
        self.assertTrue(r["by_league"]["nba"]["model_file_present"])
        self.assertFalse(r["by_league"]["nba"]["native_model_artifact_usable_for_research"])
        self.assertIn("nba", r["missing_or_invalid_model_leagues"])

    def test_rejects_false_certification_in_report(self):
        args = sample()
        args[1]["certified_challenger_001_predictions"] = 1
        with self.assertRaisesRegex(ValueError, "unverified_promotion"):
            assess(*args)

    def test_rejects_count_mismatch_and_implied_probabilities(self):
        args = sample()
        args[1]["actual_native_research_forecasts_written"] = 1
        with self.assertRaisesRegex(ValueError, "forecast_report_does_not_match"):
            assess(*args)
        args = sample()
        args[1]["actual_native_research_forecasts_written"] = 1
        args[3].append({"certified_prediction": False, "bet_ready": False,
                        "champion_001_modified": False,
                        "market_implied_probability_used_as_model": True})
        with self.assertRaisesRegex(ValueError, "unsafe_or_implied"):
            assess(*args)

    def test_rejects_unsupported_or_duplicate_model_inventory(self):
        args = sample()
        args[2]["models_present"] = ["nfl", "nfl"]
        with self.assertRaisesRegex(ValueError, "incomplete_or_conflicting"):
            assess(*args)
        args = sample()
        del args[2]["per_league_model_gate"]["ncaab"]
        with self.assertRaisesRegex(ValueError, "incomplete_or_conflicting"):
            assess(*args)

    def test_model_format_gate_still_uncertified(self):
        args = sample()
        args[1]["model_path_exists"] = True
        args[1]["research_model_artifact_present_and_format_valid"] = True
        args[2]["models_present"] = list(LEAGUES[1:])
        for sport in LEAGUES[1:]:
            args[2]["per_league_model_gate"][sport] = "unverified_research_model_format_passed"
        result = assess(*args)
        self.assertEqual(result["status"], "research_native_capture_uncertified")
        self.assertEqual(result["missing_or_invalid_model_leagues"], [])
        self.assertEqual(result["certified_challenger_001_predictions"], 0)
        self.assertFalse(result["calibration_qualified"])


if __name__ == "__main__":
    unittest.main()
