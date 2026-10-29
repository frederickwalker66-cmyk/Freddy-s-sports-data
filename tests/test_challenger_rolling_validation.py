"""Synthetic-only rolling-origin tests; no live model grade or wagers."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from challenger_rolling_validation import BLOCKED, EXPLORATORY, rolling_validate
from test_challenger_backtest import sample


def example(i, league="nba"):
    # Deterministic invented fixtures, with outcomes timestamped one day
    # after the invented event and features recorded two days beforehand.
    r = sample(i, league=league)
    start = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
    def iso(t):
        return t.isoformat().replace("+00:00", "Z")
    r["snapshot_utc"] = iso(start - timedelta(days=1))
    r["features_asof_utc"] = iso(start - timedelta(days=2))
    r["start_utc"] = iso(start)
    r["outcome_verified_at_utc"] = iso(start + timedelta(days=1))
    return r


AS_OF = datetime(2026, 10, 29, tzinfo=timezone.utc)


class RollingValidationTests(unittest.TestCase):
    def test_absent_historical_dataset_blocks_training(self):
        report = rolling_validate([], as_of=AS_OF)
        self.assertEqual(report["result"], BLOCKED)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["certified_challenger_001_predictions"], 0)
        self.assertEqual(report["automated_bets_placed"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_three_disjoint_expanding_folds_remain_research_only(self):
        rows = [example(i) for i in range(390)]
        report = rolling_validate(rows, as_of=AS_OF)
        n = report["leagues"]["nba"]
        self.assertEqual(n["status"], EXPLORATORY)
        self.assertEqual(n["fold_count"], 3)
        self.assertEqual(n["disjoint_test_examples"], 150)
        self.assertEqual(
            [f["test_examples"] for f in n["folds"]], [50, 50, 50])
        self.assertTrue(all(f["training_examples"] >= 200 for f in n["folds"]))
        dates = set()
        for f in n["folds"]:
            self.assertNotIn(f["first_test_event_date"], dates)
            for i in range(
                (datetime.fromisoformat(f["last_test_event_date"]) -
                 datetime.fromisoformat(f["first_test_event_date"])).days + 1
            ):
                d = (datetime.fromisoformat(f["first_test_event_date"])
                     + timedelta(days=i)).date().isoformat()
                self.assertNotIn(d, dates)
                dates.add(d)
            self.assertGreaterEqual(f["metrics"]["test_brier"], 0)
            self.assertLessEqual(f["metrics"]["test_brier"], 1)
        self.assertFalse(n["eligible_for_model_promotion"])
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_training_excludes_outcomes_not_known_by_cutoff(self):
        rows = [example(i) for i in range(390)]
        rows[200]["outcome_verified_at_utc"] = (
            datetime(2021, 1, 1, tzinfo=timezone.utc)).isoformat()
        report = rolling_validate(rows, as_of=AS_OF)
        self.assertTrue(any(f["excluded_prior_results_not_known_at_cutoff"] >= 1
                            for f in report["leagues"]["nba"]["folds"]))

    def test_future_or_not_yet_verified_rows_are_held_out(self):
        rows = [example(i) for i in range(390)]
        rows[20]["outcome_verified_at_utc"] = "2027-01-01T00:00:00Z"
        report = rolling_validate(rows, as_of=AS_OF)
        self.assertEqual(report["withheld_future_or_not_yet_settled_rows"], 1)
        self.assertEqual(report["leagues"]["nba"]["rows"], 389)

    def test_duplicate_event_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate game"):
            rolling_validate([example(1), example(1)], as_of=AS_OF)

    def test_explicit_quarantined_research_never_trains(self):
        row = example(1)
        row["qualified_for_challenger_backtest"] = False
        with self.assertRaisesRegex(ValueError, "quarantined"):
            rolling_validate([row], as_of=AS_OF)

    def test_nonhome_labels_block_unknown_feature_orientation(self):
        rows = [example(i) for i in range(390)]
        rows[1]["selection_type"] = "away"
        report = rolling_validate(rows, as_of=AS_OF)
        self.assertEqual(report["leagues"]["nba"]["status"],
                         "blocked_requires_home_perspective_labels")

    def test_mismatched_feature_schema_rejected(self):
        rows = [example(i) for i in range(390)]
        rows[1]["features"] = {"pregame_other_team_form": 0.3}
        report = rolling_validate(rows, as_of=AS_OF)
        self.assertEqual(report["leagues"]["nba"]["status"],
                         "blocked_inconsistent_pregame_feature_schema")

    def test_separate_league_models_not_pooled(self):
        rows = [example(i, "nba") for i in range(390)]
        rows.extend(example(i, "nfl") for i in range(390))
        report = rolling_validate(rows, as_of=AS_OF)
        self.assertEqual(report["leagues_with_exploratory_folds"], 2)
        self.assertEqual(set(report["leagues"]), {"nba", "nfl"})
        self.assertFalse(report["historical_sources_independently_audited"])

    def test_same_day_events_must_not_cross_train_test_split(self):
        rows = [example(i) for i in range(390)]
        same_day = deepcopy(example(240))
        same_day["event_id"] = "same-day-extra-event"
        rows.append(same_day)
        result = rolling_validate(rows, as_of=AS_OF)["leagues"]["nba"]
        date_windows = [
            (f["first_test_event_date"], f["last_test_event_date"])
            for f in result["folds"]]
        for (s1, e1), (s2, e2) in zip(date_windows, date_windows[1:]):
            self.assertLess(e1, s2)

    def test_small_sample_or_insufficient_folds_remains_blocked(self):
        report = rolling_validate([example(i) for i in range(290)], as_of=AS_OF)
        self.assertEqual(report["result"], BLOCKED)
        self.assertLess(report["leagues"]["nba"]["fold_count"], 3)

    def test_bad_thresholds_rejected(self):
        with self.assertRaises(ValueError):
            rolling_validate([], minimum_train=1)
        with self.assertRaises(ValueError):
            rolling_validate([], minimum_folds=5, maximum_folds=4)
        with self.assertRaises(ValueError):
            rolling_validate([], as_of=datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
