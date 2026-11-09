"""Phone research leaderboard tests: validate real persisted read-only data."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_forward_leaderboard_view import VERSION, read_leaderboard


def report():
    return {
        "version": VERSION,
        "ranking_status": "NO_MODEL_WITH_50_AUTHENTIC_FORWARD_GRADED_GAMES",
        "generated_at_utc": "2026-11-09T20:00:00+00:00",
        "champion_001_modified": False,
        "bet_ready": False,
        "certified_champion_001_shadows": 0,
        "certified_v8_probabilities": 0,
        "certified_positive_ev_bets": 0,
        "independently_verified_checkout_odds": 0,
        "nba_unique_original_forecasts_archived": 14,
        "nba_forward_forecasts_graded_research_only": 0,
        "nba_forecasts_pending_48h": 14,
        "nba_forecasts_due_without_published_grade": 0,
        "nba_original_forecasts_quarantined": 0,
        "research_only_ranked_models": [],
    }


class ForwardLeaderboardViewTests(unittest.TestCase):
    def test_uninitialized_durable_store_is_not_fabricated(self):
        x = read_leaderboard(None)
        self.assertEqual(x["status"], "NOT_YET_PERSISTED")
        self.assertEqual(x["graded_forward_research_games"], 0)
        self.assertEqual(x["certified_positive_ev_bets"], 0)

    def test_pending_14_real_research_forecasts_not_a_certified_win_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "LEADERBOARD.json"
            path.write_text(json.dumps(report()), encoding="utf-8")
            x = read_leaderboard(path)
            self.assertEqual(x["original_archived_forecasts"], 14)
            self.assertEqual(x["pending_48h"], 14)
            self.assertEqual(x["research_ranked_models"], [])
            self.assertFalse(x["git_branch_is_externally_immutable"])
            self.assertFalse(x["bet_ready"])

    def test_fake_certification_or_unreconciled_counts_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "LEADERBOARD.json"
            row = report()
            row["certified_positive_ev_bets"] = 1
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "persisted_research_cannot_be_certified"):
                read_leaderboard(path)
            row = report()
            row["nba_forward_forecasts_graded_research_only"] = 2
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "persistent_forecast_counts_do_not_reconcile"):
                read_leaderboard(path)

    def test_reject_ranked_model_with_less_than_50_games(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "LEADERBOARD.json"
            row = report()
            row["nba_unique_original_forecasts_archived"] = 20
            row["nba_forecasts_pending_48h"] = 0
            row["nba_forward_forecasts_graded_research_only"] = 20
            row["research_only_ranked_models"] = [{
                "sport": "nba",
                "model_version": "test",
                "graded_forward_research_games": 20,
                "mean_Brier_lower_is_better": .24,
                "research_only_not_certified": True,
                "ranking_eligible": True,
                "positive_ev_certified": 0,
            }]
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_research_model_certification_or_score"):
                read_leaderboard(path)


if __name__ == "__main__":
    unittest.main()
