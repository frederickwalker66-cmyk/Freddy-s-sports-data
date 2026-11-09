"""Research command, no-evidence and indicative EV integration tests."""
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from v8_one_command import COMMANDS, default_end_date, execute, selected
from v8_edge_value import research_edge, rank_research_edges


def quote():
    return {
        "league": "nba", "market": "moneyline", "selection": "home",
        "event_id": "12345", "bookmaker": "SampleBook",
        "champion_001_modified": False, "model_version": "synthetic_test",
        "model_probability_source": "native_independent_pregame",
        "independent_model_review": True, "independent_price_review": True,
        "model_probability": .58, "american_odds": -110,
        "start_utc": "2026-11-08T00:00:00Z",
        "model_forecast_recorded_utc": "2026-11-07T22:00:00Z",
        "price_recorded_utc": "2026-11-07T22:02:00Z",
    }


class OneCommandTests(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(selected("run_nba"), ("nba",))
        self.assertEqual(len(selected("run_sports")), 8)
        self.assertEqual(selected("run_edge"), ())
        with self.assertRaises(ValueError):
            selected("bet_now")

    def test_date_uses_new_york(self):
        now = datetime(2026, 11, 6, 4, tzinfo=timezone.utc)
        self.assertEqual(default_end_date(now), date(2026, 11, 4))

    def test_health_command_uses_actual_workflow_metadata(self):
        now = datetime(2026, 11, 9, 17, tzinfo=timezone.utc)
        stamp = (now - timedelta(minutes=40)).isoformat()
        rows = {"workflow_runs": [{
            "id": 121, "event": "schedule", "head_branch": "main",
            "created_at": stamp, "updated_at": stamp,
            "status": "completed", "conclusion": "success",
        }]}
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_health", now=now, source_run_metadata=rows, output_dir=folder)
            health = result["source_collection_health"]
            self.assertEqual(health["reason"], "recent_successful_source_workflow")
            self.assertEqual(health["latest_successful_workflow_run_id"], 121)
            self.assertFalse(health["dispatch_attempted"])
            self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_health_without_github_metadata_remains_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_health", output_dir=folder)
            self.assertEqual(result["source_collection_health"]["reason"], "metadata_unavailable")
            self.assertFalse(result["source_collection_health"]["dispatch_attempted"])

    def test_run_certify_returns_real_evidence_inventory_not_picks(self):
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_certify", output_dir=folder)
            audit = result["certification_review"]
            self.assertEqual(audit["status"], "HOLD_MISSING_INDEPENDENT_MODEL_AND_PRICE_PROOF")
            self.assertEqual(audit["certified_v8_predictions"], 0)
            self.assertIsNone(audit["source_games_archived"])
            self.assertEqual(result["certified_positive_ev_bets"], 0)
            self.assertTrue((Path(folder) / "CERTIFICATION_AUDIT.json").is_file())

    def test_nba_training_command_with_no_review_qualified_data_fails_closed(self):
        self.assertEqual(selected("run_nba_train"), ())
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_nba_train", output_dir=folder)
            intake = result["nba_training_intake"]
            self.assertEqual(intake["nba_unique_original_capture_events"], 0)
            self.assertFalse(intake["native_research_model_fitted"])
            self.assertEqual(intake["independently_qualified_training_games"], 0)
            self.assertEqual(result["certified_positive_ev_bets"], 0)
            self.assertTrue((Path(folder) / "NBA_RESEARCH_INTAKE.json").is_file())
            self.assertTrue((Path(folder) / "NBA_ORIGINAL_REVIEW_WORKLIST.jsonl").is_file())
            self.assertFalse((Path(folder) / "NBA_UNVERIFIED_RESEARCH_MODEL.json").exists())

    def test_nba_research_backtest_command_graceful_empty_source(self):
        self.assertEqual(selected("run_nba_oos"), ())
        def empty_public_collector(leagues, days, end_date):
            self.assertEqual(leagues, ("nba",))
            return [], {
                "leagues": ["nba"], "total_completed_results": 0,
                "by_league": {"nba": {
                    "days_attempted": days, "days_ok": days,
                    "days_failed": 0, "completed_games": 0, "draws": 0,
                    "error_types": {},
                }}
            }
        with tempfile.TemporaryDirectory() as folder:
            report = execute(
                "run_nba_oos", days=2, end_date=date(2026, 2, 15),
                now=datetime(2026, 11, 9, tzinfo=timezone.utc),
                collector=empty_public_collector, output_dir=folder)
            oos = report["nba_oos_research"]
            self.assertEqual(oos["status"], "HOLD_INSUFFICIENT_RESEARCH_HISTORY")
            self.assertIsNone(oos["brier_score_retrospective_research_only"])
            self.assertEqual(oos["certified_positive_ev_bets"], 0)
            self.assertEqual(report["certified_positive_ev_bets"], 0)
            self.assertTrue((Path(folder) / "NBA_ELO_RETROSPECTIVE_REPORT.json").is_file())
            self.assertTrue((Path(folder) / "NBA_ELO_RETROSPECTIVE_LEDGER.jsonl").is_file())

    def test_empty_model_status(self):
        with tempfile.TemporaryDirectory() as folder:
            result = execute("model_status", output_dir=folder)
            self.assertEqual(result["model_status"]["research_models_fitted_this_run"], [])
            self.assertEqual(result["certified_positive_ev_bets"], 0)
            self.assertTrue((Path(folder) / "ONE_COMMAND_REPORT.json").exists())

    def test_inactive_public_source_does_not_invent_games(self):
        def mock_collector(leagues, days, end_date):
            league = leagues[0]
            return [], {
                "leagues": [league], "total_completed_results": 0,
                "by_league": {league: {"days_attempted": days, "days_ok": days,
                    "days_failed": 0, "completed_games": 0}}
            }
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_nba", days=2, end_date=date(2026, 11, 4),
                             collector=mock_collector, output_dir=folder)
            self.assertEqual(result["by_league"]["nba"]["completed_published_games"], 0)
            self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_edge_math_is_research_only(self):
        candidate = research_edge(quote())
        self.assertGreater(candidate["indicative_ev_roi_percent"], 0)
        self.assertFalse(candidate["certified_prediction"])
        self.assertFalse(candidate["verified_executable_checkout_price"])
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_edge", edge_rows=[quote()], output_dir=folder)
            self.assertEqual(len(result["research_edge_candidates"]), 1)
            self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_no_implied_probability_substitution(self):
        bad = quote()
        bad["model_probability_source"] = "sportsbook_implied"
        with self.assertRaisesRegex(ValueError, "market_implied_probability_not_allowed"):
            rank_research_edges([bad])

    def test_future_or_stale_price_rejected(self):
        bad = quote()
        bad["price_recorded_utc"] = "2026-11-08T00:01:00Z"
        with self.assertRaisesRegex(ValueError, "not_pregame"):
            research_edge(bad)
        bad = quote()
        bad["price_recorded_utc"] = "2026-11-07T20:00:00Z"
        with self.assertRaisesRegex(ValueError, "not_near_in_time"):
            research_edge(bad)


if __name__ == "__main__":
    unittest.main()
