"""NFL/NHL persistent research store: no overwrite, missing outcomes, NFL ties."""
import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from test_v8_nfl_nhl_forward_grade import (
    RUN,RECORDED,MATURE,write_original,collector,
)
from v8_nfl_nhl_durable_ledger import sync
from v8_nfl_nhl_forward_grade import GRADED,NFL_TIE


class DurableLeagueTests(unittest.TestCase):
    def test_persist_actual_forecasts_both_sports_pending_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"original"
            saved=Path(folder)/"saved"
            for sport in ("nfl","nhl"):
                src,row=write_original(incoming,sport)
                root=saved/sport
                before=(src/(sport.upper()+"_FORWARD_RESEARCH_FORECASTS.jsonl")).read_bytes()
                def no_final(*args):
                    raise AssertionError("cannot_grade_pregame")
                report,history=sync(sport,incoming,root,now=RECORDED,
                                    collector=no_final)
                self.assertEqual(report["original_saved_forecasts"],1)
                self.assertEqual(report["graded_research_games"],0)
                self.assertEqual(report["pending_48h"],1)
                self.assertEqual(report["certified_positive_ev_bets"],0)
                self.assertEqual(report["research_ranked_models_after_50"],[])
                self.assertTrue((root/"FIRST_FORECASTS.sqlite").exists())
                self.assertTrue((root/"FORWARD_RESEARCH_LEADERBOARD.json").exists())
                stored=(root/"original_source_receipts"/str(RUN)
                        /(sport.upper()+"_FORWARD_RESEARCH_FORECASTS.jsonl"))
                self.assertEqual(stored.read_bytes(),before)
                second,_=sync(sport,incoming,root,now=RECORDED,collector=no_final)
                self.assertEqual(second["last_synchronization"]["new_original_forecasts"],0)
                self.assertEqual(second["last_synchronization"]["original_source_receipt_files_saved"],0)

    def test_nfl_published_tie_excluded_and_not_refetched(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"original"
            saved=Path(folder)/"nfl"
            write_original(incoming,"nfl")
            first,history=sync("nfl",incoming,saved,now=MATURE,
                               collector=collector("nfl",tie=True))
            self.assertEqual(first["graded_research_games"],0)
            self.assertEqual(first["published_NFL_ties_excluded"],1)
            self.assertEqual(history[0]["status"],NFL_TIE)
            def forbidden(*args):
                raise AssertionError("already_resolved_NFL_tie_should_not_requery")
            again,history=sync("nfl",incoming,saved,
                               now=MATURE+timedelta(days=1),collector=forbidden)
            self.assertEqual(again["last_synchronization"]["new_NFL_ties_excluded_from_binary_grading"],0)
            self.assertEqual(again["published_NFL_ties_excluded"],1)

    def test_nhl_grade_keeps_first_probability_on_later_forecast(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"input"
            saved=Path(folder)/"nhl"
            write_original(incoming,"nhl")
            report,history=sync("nhl",incoming,saved,now=MATURE,collector=collector("nhl"))
            self.assertEqual(report["graded_research_games"],1)
            self.assertIsNone(report["research_model_scorecards_including_insufficient_samples"][0]["research_Brier"])
            self.assertEqual(history[0]["status"],GRADED)
            self.assertAlmostEqual(history[0]["original_probability_home_research_only"],.63)
            write_original(incoming,"nhl",run=RUN+1,
                           recorded=RECORDED+timedelta(minutes=5),probability=.82)
            def forbidden(*args):
                raise AssertionError("previously graded outcome must not be overwritten")
            again,history=sync("nhl",incoming,saved,now=MATURE+timedelta(days=1),
                               collector=forbidden)
            self.assertEqual(again["graded_research_games"],1)
            self.assertEqual(again["original_saved_forecasts"],1)
            self.assertAlmostEqual(history[0]["original_probability_home_research_only"],.63)

    def test_original_saved_receipt_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"source"
            saved=Path(folder)/"record"
            write_original(incoming,"nfl")
            sync("nfl",incoming,saved,now=RECORDED)
            source=saved/"original_source_receipts"/str(RUN)/"github_run.json"
            source.write_text('{"tampered":true}')
            with self.assertRaisesRegex(ValueError,"source_original_forecast_receipt_changed"):
                sync("nfl",incoming,saved,now=RECORDED)

    def test_persistent_archive_preserves_games_when_temporary_artifacts_expire(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"source"
            saved=Path(folder)/"record"
            write_original(incoming,"nfl")
            sync("nfl",incoming,saved,now=RECORDED)
            for p in (incoming/"nfl"/str(RUN)).iterdir():
                p.unlink()
            (incoming/"nfl"/str(RUN)).rmdir()
            status,history=sync("nfl",incoming,saved,now=RECORDED)
            self.assertEqual(status["original_saved_forecasts"],1)
            self.assertEqual(status["pending_48h"],1)

    def test_persistent_store_empty_is_zero_not_spurious_score(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming=Path(folder)/"source"
            (incoming/"nfl").mkdir(parents=True)
            board,rows=sync("nfl",incoming,Path(folder)/"persistent",now=RECORDED)
            self.assertEqual(board["original_saved_forecasts"],0)
            self.assertEqual(board["graded_research_games"],0)
            self.assertFalse(board["bet_ready"])
            self.assertEqual(rows,[])


if __name__=="__main__":
    unittest.main()
