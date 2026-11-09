"""Durable forward ledger: verify original probability never overwritten, no false grades."""
import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta, datetime, timezone
from pathlib import Path

from tests.test_v8_nba_forward_grade import (
    write_run, results_collector, FORECAST, START, AFTER, RUN,
)
from v8_durable_forward_ledger import sync, GRADED_STATUS


class DurableForwardTests(unittest.TestCase):
    def test_first_archive_persists_original_but_pending_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            archives=Path(folder)/"input"
            archives.mkdir()
            saved=Path(folder)/"persistent"
            src,first=write_run(archives)
            first_bytes=(src/"nba_forward/NBA_FORWARD_FORECASTS.jsonl").read_bytes()
            def cannot_call_before_result_matures(*args):
                raise AssertionError("should not retrieve a future result")
            report,rows=sync(archives,saved,now=FORECAST,
                             collector=cannot_call_before_result_matures)
            self.assertEqual(report["nba_unique_original_forecasts_archived"],1)
            self.assertEqual(report["nba_forecasts_pending_48h"],1)
            self.assertEqual(report["nba_forward_forecasts_graded_research_only"],0)
            self.assertEqual(len(rows),1)
            self.assertFalse(rows[0]["certified_prediction"])
            self.assertEqual(rows[0]["original_model_home_win_probability"],.6)
            self.assertEqual(report["certified_champion_001_shadows"],0)
            self.assertEqual(report["certified_positive_ev_bets"],0)
            self.assertEqual(report["research_only_ranked_models"],[])
            copied=saved/"original_run_receipts"/str(RUN)/"nba_forward/NBA_FORWARD_FORECASTS.jsonl"
            self.assertEqual(copied.read_bytes(),first_bytes)
            report2,rows2=sync(archives,saved,now=FORECAST,
                               collector=cannot_call_before_result_matures)
            self.assertEqual(report2["new_forecast_sync"]["new_forecasts_inserted"],0)
            self.assertEqual(report2["new_forecast_sync"]["existing_or_later_forecasts_ignored"],1)
            self.assertEqual(report2["new_forecast_sync"]["original_receipt_files_added"],0)
            self.assertEqual(copied.read_bytes(),first_bytes)

    def test_graded_earliest_forecast_stays_locked_after_reforecast_and_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            archives=Path(folder)/"original"
            archives.mkdir()
            saved=Path(folder)/"permanent"
            write_run(archives)
            report,rows=sync(archives,saved,now=AFTER,collector=results_collector)
            self.assertEqual(report["nba_forward_forecasts_graded_research_only"],1)
            self.assertEqual(report["nba_forecasts_due_without_published_grade"],0)
            self.assertAlmostEqual(report["research_model_scorecards_including_small_samples"][0]["mean_Brier_lower_is_better"],.16)
            self.assertEqual(report["ranking_status"],"NO_MODEL_WITH_50_AUTHENTIC_FORWARD_GRADED_GAMES")
            self.assertEqual(rows[0]["grade_status"],GRADED_STATUS)
            self.assertEqual(rows[0]["home_won_published_final_research_only"],1)
            def forbidden(*args):
                raise AssertionError("already graded results must never be re-fetched")
            again,history=sync(archives,saved,now=AFTER+timedelta(days=1),collector=forbidden)
            self.assertEqual(again["nba_forward_forecasts_graded_research_only"],1)
            self.assertEqual(again["new_forecast_sync"]["new_ESPN_published_outcomes_recorded"],0)
            write_run(archives,RUN+1,p=.8,recorded=FORECAST+timedelta(minutes=10))
            later,history=sync(archives,saved,now=AFTER+timedelta(days=2),collector=forbidden)
            self.assertEqual(history[0]["original_model_home_win_probability"],.6)
            self.assertEqual(later["nba_unique_original_forecasts_archived"],1)
            self.assertEqual(later["nba_forward_forecasts_graded_research_only"],1)
            self.assertEqual(later["new_forecast_sync"]["existing_or_later_forecasts_ignored"],1)

    def test_invalid_or_corrupted_receipt_detected_even_after_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            archives=Path(folder)/"input"
            archives.mkdir()
            saved=Path(folder)/"archive"
            write_run(archives)
            sync(archives,saved,now=FORECAST)
            receipt=saved/"original_run_receipts"/str(RUN)/"github_run.json"
            receipt.write_text('{"id":0}\n')
            with self.assertRaisesRegex(ValueError,"original_forecast_receipt_cannot_be_changed"):
                sync(archives,saved,now=FORECAST)

    def test_sqlite_existing_probability_cannot_be_updated_via_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            archives=Path(folder)/"input"
            archives.mkdir()
            saved=Path(folder)/"archive"
            write_run(archives)
            sync(archives,saved,now=FORECAST)
            db=saved/"NBA_FORWARD_RESEARCH.sqlite"
            with sqlite3.connect(db) as handle:
                original=handle.execute("SELECT original_p_home FROM nba_forward_forecasts").fetchone()[0]
            self.assertAlmostEqual(original,.6)
            self.assertTrue((saved/"LEADERBOARD.json").exists())
            self.assertTrue((saved/"FORECAST_HISTORY.jsonl").exists())
            report,_=sync(archives,saved,now=FORECAST)
            self.assertEqual(report["new_forecast_sync"]["new_forecasts_inserted"],0)

    def test_empty_original_archive_keeps_stated_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            archives=Path(folder)/"input"
            archives.mkdir()
            saved=Path(folder)/"archive"
            report,rows=sync(archives,saved,now=FORECAST)
            self.assertEqual(report["nba_unique_original_forecasts_archived"],0)
            self.assertEqual(report["nba_forward_forecasts_graded_research_only"],0)
            self.assertEqual(report["research_only_ranked_models"],[])
            self.assertEqual(rows,[])
            self.assertFalse(report["bet_ready"])


if __name__=="__main__":
    unittest.main()
