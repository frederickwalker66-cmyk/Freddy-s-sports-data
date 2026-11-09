"""Phone calibration reporting uses persistent evidence, not model-generated guesses."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_forward_calibration_view import read_calibration


def sample():
    return {
        "version":"v8-nba-forward-calibration-v1",
        "stage":"genuinely_forward_recorded_NBA_research_calibration_only",
        "status":"HOLD_WAITING_FOR_100_FORWARD_GRADED_AND_WELL_POPULATED_BINS",
        "archived_original_forward_forecasts":14,
        "graded_research_NBA_games":0,"pending_ungraded":14,"quarantined":0,
        "models":[],"champion_001_modified":False,"bet_ready":False,
        "data_is_independently_publisher_authenticated":False,
        "original_Champion_001_certified_shadows":0,
        "certified_positive_ev_bets":0,"independently_certified_models":0,
        "independently_verified_sportsbook_checkout_quotes":0,
    }


class CalibrationViewTests(unittest.TestCase):
    def test_unavailable_branch_does_not_invent_known_counts(self):
        result=read_calibration(None)
        self.assertEqual(result["status"],"NOT_YET_PERSISTED")
        self.assertIsNone(result["graded_research_NBA_games"])
        self.assertEqual(result["certified_positive_ev_bets"],0)

    def test_saved_zero_score_is_not_certified(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"CALIBRATION.json"
            f.write_text(json.dumps(sample()))
            result=read_calibration(f)
            self.assertEqual(result["archived_original_forward_forecasts"],14)
            self.assertEqual(result["pending_ungraded"],14)
            self.assertEqual(result["models"],[])
            self.assertEqual(result["original_Champion_001_certified_shadows"],0)
            self.assertFalse(result["bet_ready"])

    def test_false_certification_and_inconsistent_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"CALIBRATION.json"
            raw=sample()
            raw["certified_positive_ev_bets"]=10
            f.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,"must_be_original_untested_research"):
                read_calibration(f)
            raw=sample()
            raw["pending_ungraded"]=13
            f.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,"counts_do_not_reconcile"):
                read_calibration(f)


if __name__=="__main__":
    unittest.main()
