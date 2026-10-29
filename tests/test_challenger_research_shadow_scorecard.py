"""Offline synthetic outcome fixtures only: descriptive scorecard tests."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from challenger_research_shadow_baseline import build_forecasts
from challenger_research_shadow_scorecard import evaluate
from test_challenger_research_shadow_baseline import fixture, NOW


def linked():
    return {
        "league": "nba", "espn_event_id": "401001",
        "status": "linked_to_espn_published_final_only",
        "home_team": "Atlanta Hawks", "away_team": "Cleveland Cavaliers",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "published_outcome": {
            "result": "home",
            "published_retrieved_at_utc": "2026-10-30T05:00:00Z",
        },
        "independent_league_outcome_verified": False,
        "qualified_for_challenger_backtest": False,
        "bet_ready": False,
        "champion_001_modified": False,
    }


class ScorecardTests(unittest.TestCase):
    def forecasts(self):
        return build_forecasts([fixture()], NOW)[0]

    def test_scorecard_reports_only_descriptive_results(self):
        report = evaluate(self.forecasts(), [linked()],
                          datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 1)
        self.assertAlmostEqual(report["by_league"]["nba"]["exploratory_brier_score"], 0.1444)
        self.assertEqual(report["independent_league_outcomes_verified"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["validated_positive_ev_bets"], 0)
        self.assertFalse(report["by_league"]["nba"]["out_of_sample_calibration_validated"])

    def test_missing_outcome_not_scored(self):
        r = linked()
        r["status"] = "awaiting_published_final"
        r["published_outcome"] = None
        report = evaluate(self.forecasts(), [r],
                          datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 0)

    def test_duplicate_outcome_quarantined(self):
        r = linked()
        report = evaluate(self.forecasts(), [r, deepcopy(r)],
                          datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 0)

    def test_after_start_forecast_not_scored(self):
        f = self.forecasts()
        f[0]["forecast_created_at_utc"] = "2026-10-30T01:00:00Z"
        report = evaluate(f, [linked()], datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 0)
        self.assertEqual(report["rejected_forecasts"]["invalid_or_nonprospective_forecast"], 1)

    def test_mismatched_teams_quarantined(self):
        r = linked()
        r["away_team"] = "Boston Celtics"
        report = evaluate(self.forecasts(), [r], datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 0)

    def test_invalid_betting_flag_quarantined(self):
        f = self.forecasts()
        f[0]["bet_ready"] = True
        report = evaluate(f, [linked()], datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 0)

    def test_forecast_duplicates_choose_earliest(self):
        one = self.forecasts()[0]
        second = deepcopy(one)
        second["forecast_created_at_utc"] = "2026-10-29T22:00:00+00:00"
        report = evaluate([second, one], [linked()], datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(report["scored_espn_published_games"], 1)
        self.assertEqual(report["unique_valid_forecasts"], 1)


if __name__ == "__main__":
    unittest.main()
