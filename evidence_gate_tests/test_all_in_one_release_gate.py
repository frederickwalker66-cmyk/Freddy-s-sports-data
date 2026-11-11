"""Synthetic-only integration tests for Freddy's all-in-one HOLD release runner."""
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from freddys_all_in_one_release_gate import (
    _nba_market_side_research, _copy_ledger, build_release)

NOW=datetime(2026,11,11,12,0,tzinfo=timezone.utc)


class AllInOneSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_all_in_one_with_no_external_records_never_certifies(self):
        out=self.root/"report"
        r=build_release(output_dir=out,now=NOW)
        self.assertEqual(r["counts"]["nba_original_research_games_reviewed"],0)
        self.assertEqual(r["counts"]["nba_chronological_training_games_externally_witnessed"],0)
        self.assertEqual(r["counts"]["nba_untouched_later_holdout_games_externally_witnessed"],0)
        self.assertEqual(r["counts"]["direct_executable_DraftKings_quotes_certified"],0)
        self.assertEqual(r["counts"]["automated_wagers_placed"],0)
        self.assertFalse(r["bet_ready"])
        self.assertFalse(r["champion_001_modified"])
        self.assertIn("HOLD",r["status"])
        self.assertIsNone if False else None
        self.assertFalse((out/"historical"/"nba"/"UNVERIFIED_RESEARCH_MODEL.json").exists())
        self.assertFalse((out/"historical"/"other_leagues"/"UNVERIFIED_MODELS").exists())
        self.assertTrue((out/"ALL_IN_ONE_STATUS.md").is_file())
        self.assertEqual(json.loads((out/"ALL_IN_ONE_RELEASE_READINESS.json").read_text())["status"],
                         r["status"])

    def test_self_attested_rows_with_no_external_keys_do_not_enter(self):
        bogus={
            "event_id":"401999999","league":"nba","record_type":"nba_original_pregame_and_outcome_witness_v1",
            "qualified_for_challenger_backtest":True,"independent_asof_review":True,
            "independent_outcome_review":True,"champion_001_modified":False,
        }
        src=self.root/"unsigned.jsonl"
        src.write_text(json.dumps(bogus)+"\n")
        out=self.root/"out"
        r=build_release(nba_candidates=src,output_dir=out,now=NOW)
        self.assertEqual(r["counts"]["nba_chronological_training_games_externally_witnessed"],0)
        self.assertEqual(r["nba_admission_status"],"HOLD_MISSING_EXTERNAL_NBA_TRUST_ANCHORS")
        self.assertFalse((out/"historical"/"nba"/"UNVERIFIED_RESEARCH_MODEL.json").exists())

    def test_existing_output_must_not_be_overwritten(self):
        out=self.root/"out"
        out.mkdir()
        (out/"existing.json").write_text("preserve")
        with self.assertRaisesRegex(ValueError,"new_or_empty"):
            build_release(output_dir=out,now=NOW)
        self.assertEqual((out/"existing.json").read_text(),"preserve")

    def test_no_forward_refresh_when_archives_unavailable(self):
        r=build_release(output_dir=self.root/"out",now=NOW,refresh_forward=True)
        self.assertEqual(r["forward_research_by_league"]["nba"]["original_forecasts"],0)
        self.assertEqual(r["forward_research_by_league"]["nfl"]["graded"],0)
        self.assertEqual(r["forward_research_by_league"]["nhl"]["graded"],0)
        self.assertEqual(r["counts"]["certified_positive_EV_bets"],0)

    def test_original_first_forecast_price_observations_remain_research(self):
        base=self.root/"originals"
        p=base/"123456"/"nba_forward"
        p.mkdir(parents=True)
        rec={
            "espn_event_id":"401999999",
            "forecast_recorded_utc":"2026-11-09T20:00:00+00:00",
            "start_utc":"2026-11-10T00:00:00+00:00",
            "model_version":"v8-nba-elo-forward-research-test",
            "schedule_original_sha256_local_receipt":"a"*64,
            "model_probability_home_win_research_only":0.62,
        }
        (p/"NBA_FORWARD_FORECASTS.jsonl").write_text(json.dumps(rec)+"\n")
        vetted=[{
            "espn_event_id":"401999999","original_github_run_id":123456,
            "first_observed_forecast_utc":rec["forecast_recorded_utc"],
            "event_start_utc":rec["start_utc"],
            "model_version":rec["model_version"],
            "original_schedule_sha256":rec["schedule_original_sha256_local_receipt"],
        }]
        rows=_nba_market_side_research(base,vetted)
        self.assertEqual(len(rows),2)
        self.assertAlmostEqual(sum(r["model_probability"] for r in rows),1.0)
        self.assertTrue(all(r["research_only"] is True for r in rows))
        self.assertTrue(all(r["certified_prediction"] is False for r in rows))

    def test_saved_branch_must_not_be_written_or_copied_into_itself(self):
        src=self.root/"persisted"
        src.mkdir()
        (src/"LEADERBOARD.json").write_text("{}")
        with self.assertRaisesRegex(ValueError,"disjoint"):
            _copy_ledger(src,src/"scratch")
        target=self.root/"output"
        _copy_ledger(src,target)
        self.assertEqual((target/"LEADERBOARD.json").read_text(),"{}")
        self.assertEqual((src/"LEADERBOARD.json").read_text(),"{}")


if __name__=="__main__":
    unittest.main()
