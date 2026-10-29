"""Synthetic-only safety tests; they cannot establish real-world accuracy."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from challenger_research_shadow_baseline import build_forecasts

NOW = datetime(2026, 10, 29, 21, 50, tzinfo=timezone.utc)


def fixture():
    def form(rate):
        return {
            "last_games": 5,
            "win_rate": rate,
            "margin_average": 2.0,
            "prior_espn_event_ids": ["1", "2", "3", "4", "5"],
            "retrieval_asof_utc": "2026-10-29T21:40:00Z",
            "result_start_embargo_hours": 48,
            "historical_original_publication_times_verified": False,
        }
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": "401001",
        "home_team": "Atlanta Hawks", "away_team": "Cleveland Cavaliers",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "snapshot_completed_at_utc": "2026-10-29T21:45:00Z",
        "schedule_observed_at_utc": "2026-10-29T21:44:00Z",
        "schedule_source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "home_team_form": form(0.8), "away_team_form": form(0.4),
        "odds_observations": [],
        "certified_prediction": False, "model_probability": None,
        "qualified_for_challenger_backtest": False, "bet_ready": False,
        "champion_001_modified": False,
    }


class ResearchBaselineTests(unittest.TestCase):
    def test_real_pregame_baseline_never_certified(self):
        forecasts, report = build_forecasts([fixture()], NOW)
        self.assertEqual(len(forecasts), 1)
        f = forecasts[0]
        self.assertAlmostEqual(f["baseline_home_win_probability"], 0.62)
        self.assertEqual(f["shadow_stake_usd"], 0)
        self.assertFalse(f["trained_challenger_001_model"])
        self.assertFalse(f["calibrated_model_probability"])
        self.assertFalse(f["certified_prediction"])
        self.assertFalse(f["bet_ready"])
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_odds_do_not_affect_forecast(self):
        original = fixture()
        other = fixture()
        other["odds_observations"] = [
            {"received_at_utc": "2026-10-29T21:44:00Z",
             "direct_draftkings_checkout_verified": False,
             "odds_american": 900, "market_type": "moneyline"}]
        a, _ = build_forecasts([original], NOW)
        b, _ = build_forecasts([other], NOW)
        self.assertEqual(a[0]["baseline_home_win_probability"],
                         b[0]["baseline_home_win_probability"])

    def test_no_retrospective_prediction_after_tipoff(self):
        forecasts, rep = build_forecasts([fixture()],
                       datetime(2026, 10, 30, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(forecasts, [])
        self.assertEqual(rep["skipped"]["game_already_started"], 1)

    def test_future_form_retrieval_is_rejected(self):
        s = fixture()
        s["home_team_form"]["retrieval_asof_utc"] = "2026-10-30T00:01:00Z"
        forecasts, _ = build_forecasts([s], NOW)
        self.assertEqual(forecasts, [])

    def test_incomplete_prior_data_is_rejected(self):
        s = fixture()
        s["home_team_form"]["last_games"] = 2
        forecasts, _ = build_forecasts([s], NOW)
        self.assertEqual(forecasts, [])

    def test_markets_with_draws_excluded(self):
        s = fixture()
        s["league"] = "mls"
        forecasts, rep = build_forecasts([s], NOW)
        self.assertEqual(forecasts, [])
        self.assertEqual(rep["skipped"]["unsupported_market"], 1)

    def test_duplicate_event_fails_closed(self):
        with self.assertRaises(ValueError):
            build_forecasts([fixture(), deepcopy(fixture())], NOW)

    def test_frozen_champion_violation_rejected(self):
        s = fixture()
        s["champion_001_modified"] = True
        forecasts, _ = build_forecasts([s], NOW)
        self.assertEqual(forecasts, [])

    def test_prior_embargo_below_48h_rejected(self):
        s = fixture()
        s["away_team_form"]["result_start_embargo_hours"] = 24
        forecasts, _ = build_forecasts([s], NOW)
        self.assertEqual(forecasts, [])


if __name__ == "__main__":
    unittest.main()
