"""Synthetic readiness regression tests; never evidence of actual NBA model training."""
from datetime import datetime, timedelta, timezone
import unittest

from challenger_training_readiness import assess
from challenger_nba_probability import train_engine

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def game(index, same_day_group=1):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=2 * (index // same_day_group), hours=(index % same_day_group))
    return {
        "event_id": "synthetic-only-" + str(index),
        "league": "nba", "selection_type": "home", "market_type": "moneyline",
        "snapshot_utc": stamp(start - timedelta(hours=3)),
        "features_asof_utc": stamp(start - timedelta(hours=5)),
        "start_utc": stamp(start),
        "outcome_verified_at_utc": stamp(start + timedelta(hours=2)),
        "event_source_url": "https://testing.invalid/schedule",
        "feature_source_url": "https://testing.invalid/features",
        "outcome_source_url": "https://testing.invalid/result",
        "features": {"pregame_home_form": (index % 9) / 9.0},
        "outcome": (index // 3) % 2,
        "qualified_for_challenger_backtest": True,
        "independent_pregame_source_audit": True,
        "independent_outcome_adjudication": True,
        "independent_asof_review": True,
        "independent_outcome_review": True,
        "feature_snapshot_sha256": "a" * 64,
        "outcome_snapshot_sha256": "b" * 64,
    }


class TrainingReadinessConsistencyTests(unittest.TestCase):
    def test_no_qualified_history_blocks(self):
        result = assess([])
        self.assertFalse(result["by_league"]["nba"]["research_training_ready"])
        self.assertEqual(result["qualified_training_examples"], 0)
        self.assertEqual(result["certified_predictions"], 0)
        self.assertFalse(result["champion_001_modified"])

    def test_review_only_flags_cannot_sneak_into_readiness(self):
        for key, replacement in (
            ("independent_asof_review", False),
            ("independent_outcome_review", False),
            ("feature_snapshot_sha256", "self-attested"),
            ("selection_type", "away"),
            ("independent_pregame_source_audit", False),
        ):
            row = game(1)
            row[key] = replacement
            with self.subTest(field=key):
                report = assess([row])
                self.assertEqual(report["by_league"]["nba"]["accepted_independently_audited_records"], 0)
                self.assertTrue(report["rejected"])

    def test_day_disjoint_training_agrees_with_nba_engine(self):
        rows = [game(i, same_day_group=3) for i in range(260)]
        readiness = assess(rows)["by_league"]["nba"]
        model_report, model = train_engine(rows, as_of=NOW)
        self.assertTrue(readiness["whole_day_holdout_split"])
        self.assertEqual(readiness["eligible_chronological_training_records"], 207)
        self.assertEqual(readiness["later_holdout_records"], 53)
        self.assertEqual(readiness["eligible_chronological_training_records"],
                         model_report["chronological_train_games"])
        self.assertEqual(readiness["later_holdout_records"],
                         model_report["chronological_holdout_games"])
        self.assertTrue(readiness["research_training_ready"])
        self.assertIsNotNone(model)
        self.assertEqual(model["status"], "unverified_research_model_not_deployed")
        self.assertFalse(model["qualified_for_real_money_wagers"])

    def test_late_outcome_excluded_from_training_partition(self):
        rows = [game(i, same_day_group=3) for i in range(260)]
        rows[100]["outcome_verified_at_utc"] = "2026-10-01T00:00:00Z"
        report = assess(rows)["by_league"]["nba"]
        self.assertEqual(report["eligible_chronological_training_records"], 206)
        self.assertEqual(report["later_holdout_records"], 53)

    def test_outcome_in_future_cannot_be_accepted(self):
        row = game(1)
        row["outcome_verified_at_utc"] = "2030-01-01T00:00:00Z"
        report = assess([row])
        self.assertEqual(report["by_league"]["nba"]["accepted_independently_audited_records"], 0)
        self.assertIn("future_or_unsettled_at_readiness_check", report["rejected"])

    def test_synthetic_attestations_are_not_external_certification(self):
        report = assess([game(i) for i in range(260)])
        self.assertTrue(report["by_league"]["nba"]["research_training_ready"])
        self.assertEqual(report["certified_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertIn("NOT independent proof", report["warning"])


if __name__ == "__main__":
    unittest.main()
