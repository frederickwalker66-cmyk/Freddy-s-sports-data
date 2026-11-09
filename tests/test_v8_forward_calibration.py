"""Synthetic original-forward-score fixtures; tests never invent production accuracy."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v8_durable_forward_ledger import _init_db
from v8_forward_calibration import (
    load_original_pairs, calibrate, build_from_database, VERSION,
)

MODEL = "v8-nba-elo-forward-research-v0-fixed-k20-ha60"
TIME = datetime(2026,11,1,15,tzinfo=timezone.utc)


def fixture_database(path, size=0, grades=None, corrupt=False):
    grades = size if grades is None else grades
    with sqlite3.connect(path) as db:
        _init_db(db)
        for k in range(size):
            event=str(90000000+k)
            start=TIME+timedelta(days=k//8,minutes=k%8)
            prior=start-timedelta(hours=5)
            p=(0.1,0.3,0.5,0.7,0.9)[k%5]
            raw={
                "record_type":"v8_genuine_forward_clocktime_NBA_Elo_research_only",
                "espn_event_id":event,"model_version":MODEL,"league":"nba",
                "start_utc":start.isoformat(),"forecast_recorded_utc":prior.isoformat(),
                "model_probability_home_win_research_only":p,
                "champion_001_modified":False,"certified_prediction":False,
                "qualifies_for_original_champion_shadow_quota":False,
                "stake_usd":0,
            }
            db.execute("""INSERT INTO nba_forward_forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                       (event,MODEL,prior.isoformat(),start.isoformat(),"161","162",
                        p,123456,"a"*64,json.dumps(raw),0))
            if k < grades:
                y=int(k%3 != 0)
                h,a=(110,100) if y else (90,101)
                observed=start+timedelta(hours=55)
                reviewed=start+timedelta(hours=56)
                if corrupt and k==0:
                    reviewed=start+timedelta(hours=2)
                db.execute("INSERT INTO nba_published_outcomes VALUES (?,?,?,?,?,?,?)",
                           (event,y,h,a,"https://site.api.espn.com/example",
                            observed.isoformat(),reviewed.isoformat()))
        db.commit()


class ForwardCalibrationTests(unittest.TestCase):
    def test_nothing_certified_without_forward_graded_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,14,grades=0)
            pairs,counts=load_original_pairs(path)
            result=calibrate(pairs,counts)
            self.assertEqual(result["archived_original_forward_forecasts"],14)
            self.assertEqual(result["pending_ungraded"],14)
            self.assertEqual(result["graded_research_NBA_games"],0)
            self.assertEqual(result["models"],[])
            self.assertEqual(result["certified_positive_ev_bets"],0)
            self.assertFalse(result["bet_ready"])
            self.assertTrue(result["status"].startswith("HOLD_"))

    def test_49_true_forward_results_do_not_publish_brier_or_frequency(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,49)
            rows,total=load_original_pairs(path)
            result=calibrate(rows,total)
            self.assertEqual(total["completed"],49)
            info=result["models"][0]
            self.assertIsNone(info["research_Brier"])
            self.assertIsNone(info["research_log_loss"])
            self.assertIsNone(info["exploratory_expected_calibration_error"])
            self.assertTrue(all(b["observed_home_win_frequency"] is None
                                for b in info["fixed_predeclared_probability_bins"]))
            self.assertEqual(result["original_Champion_001_certified_shadows"],0)

    def test_50_forward_results_enable_only_provisional_score_not_ece(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,50)
            rows,total=load_original_pairs(path)
            result=calibrate(rows,total)
            info=result["models"][0]
            self.assertEqual(info["original_forward_pregame_games_graded"],50)
            self.assertIsInstance(info["research_Brier"],float)
            self.assertIsInstance(info["research_log_loss"],float)
            self.assertEqual(info["neutral_50_50_Brier_NOT_sportsbook"],.25)
            self.assertIsNone(info["exploratory_expected_calibration_error"])
            self.assertEqual(result["certified_positive_ev_bets"],0)

    def test_100_forward_results_predeclared_bins_and_uncertainty(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,100)
            out=Path(folder)/"CALIBRATION.json"
            report=build_from_database(path,out)
            self.assertTrue(out.is_file())
            self.assertEqual(json.loads(out.read_text())["version"],VERSION)
            self.assertEqual(report["graded_research_NBA_games"],100)
            model=report["models"][0]
            self.assertEqual([b["observations"] for b in model["fixed_predeclared_probability_bins"]],
                             [20,20,20,20,20])
            self.assertEqual(sum(b["home_wins"] for b in model["fixed_predeclared_probability_bins"]),66)
            self.assertIsInstance(model["exploratory_expected_calibration_error"],float)
            self.assertIsInstance(model["day_cluster_bootstrap_approximate_Brier_95pct_CI"],list)
            self.assertLessEqual(*model["day_cluster_bootstrap_approximate_Brier_95pct_CI"])
            self.assertTrue(all(b["wilson_95pct_descriptive_interval"] is not None
                                for b in model["fixed_predeclared_probability_bins"]))
            self.assertFalse(report["data_is_independently_publisher_authenticated"])
            self.assertFalse(report["bet_ready"])

    def test_too_early_outcome_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,1,corrupt=True)
            with self.assertRaisesRegex(ValueError,"outcome_published_or_graded_before_allowed_maturity"):
                load_original_pairs(path)

    def test_original_probability_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,1)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE nba_forward_forecasts SET original_p_home=0.9")
                db.commit()
            with self.assertRaisesRegex(ValueError,"lost_first_original_research_provenance"):
                load_original_pairs(path)

    def test_bad_published_result_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"source.sqlite"
            fixture_database(path,1)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE nba_published_outcomes SET home_won=1")
                db.commit()
            with self.assertRaisesRegex(ValueError,"contradictory_published_outcome"):
                load_original_pairs(path)


if __name__ == "__main__":
    unittest.main()
