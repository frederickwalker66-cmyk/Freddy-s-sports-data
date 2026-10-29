"""Synthetic-only tests. They are not real sports predictions."""
import unittest
from datetime import datetime, timedelta, timezone
from challenger_backtest import BLOCKED, backtest, validate_record


def sample(i, league="nba"):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i*3)
    def iso(dt):
        return dt.isoformat().replace("+00:00", "Z")
    return {
        "event_id": "fake-game-" + str(i), "league": league, "market_type": "moneyline",
        "selection_type": "home", "snapshot_utc": iso(start-timedelta(days=1)),
        "features_asof_utc": iso(start-timedelta(days=2)),
        "start_utc": iso(start), "outcome_verified_at_utc": iso(start+timedelta(days=1)),
        "event_source_url": "https://testing.invalid/schedule",
        "outcome_source_url": "https://testing.invalid/results",
        "feature_source_url": "https://testing.invalid/features",
        "outcome": i % 2,
        "features": {"pregame_team_form": (i % 7) / 7.0},
    }


class HistoricalBacktestTests(unittest.TestCase):
    def test_no_data_stays_blocked(self):
        report = backtest([])
        self.assertEqual(report["result"], BLOCKED)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["certified_challenger_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_synthetic_holdout_never_certifies_bets(self):
        rows = [sample(i) for i in range(60)]
        report = backtest(rows, min_train=40, min_test=12)
        nba = report["leagues"]["nba"]
        self.assertEqual(nba["eligible_train"], 48)
        self.assertEqual(nba["holdout"], 12)
        self.assertEqual(nba["status"], "uncertified_offline_backtest_only")
        self.assertTrue(0 <= nba["metrics"]["test_brier"] <= 1)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertFalse(report["historical_sources_independently_audited"])

    def test_future_known_results_cannot_enter_training(self):
        rows = [sample(i) for i in range(60)]
        rows[47]["outcome_verified_at_utc"] = "2025-01-01T00:00:00Z"
        report = backtest(rows, min_train=40, min_test=12)
        self.assertEqual(report["leagues"]["nba"]["eligible_train"], 47)
        self.assertEqual(report["leagues"]["nba"]["excluded_train_outcomes_not_known_at_cutoff"], 1)

    def test_missing_examples_not_a_fabricated_model(self):
        report = backtest([sample(i) for i in range(15)])
        self.assertEqual(report["result"], BLOCKED)
        self.assertEqual(report["leagues"]["nba"]["status"],
                         "blocked_insufficient_chronological_settled_examples")

    def test_features_postgame_or_sportsbook_derived_rejected(self):
        for field in ("pregame_implied_probability", "pregame_final_score", "odds_open"):
            row = sample(1)
            row["features"] = {field: 0.65}
            with self.assertRaises(ValueError):
                validate_record(row)

    def test_time_leak_and_unsettled_rejected(self):
        row = sample(3)
        row["features_asof_utc"] = row["start_utc"]
        with self.assertRaises(ValueError):
            validate_record(row)
        row = sample(3)
        row["outcome_verified_at_utc"] = row["snapshot_utc"]
        with self.assertRaises(ValueError):
            validate_record(row)

    def test_duplicate_events_cannot_cross_holdout(self):
        with self.assertRaises(ValueError):
            backtest([sample(0), sample(0)])

    def test_no_mixed_market_three_way_soccer(self):
        row = sample(3)
        row["league"] = "mls"
        with self.assertRaises(ValueError):
            validate_record(row)
        row = sample(3)
        row["market_type"] = "player_points"
        with self.assertRaises(ValueError):
            validate_record(row)

    def test_separate_per_league_backtests(self):
        rows = [sample(i) for i in range(60)] + [sample(i, league="nfl") for i in range(60)]
        report = backtest(rows, min_train=40, min_test=12)
        self.assertEqual(set(report["leagues"]), {"nba", "nfl"})
        self.assertEqual(report["historical_examples"], 120)
        self.assertEqual(report["certified_champion_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
