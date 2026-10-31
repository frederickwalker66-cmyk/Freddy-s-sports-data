"""Synthetic fixtures only: no real NBA scores, sportsbook data or certified picks."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_probability import (
    BLOCKED, VERSION, digest, main, predict_probability, score_future_event,
    train_engine,
)

AS_OF = datetime(2027, 1, 1, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def synthetic_game(i):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=2 * i)
    return {
        "event_id": "synthetic-nba-" + str(i),
        "league": "nba", "market_type": "moneyline", "selection_type": "home",
        "snapshot_utc": stamp(start - timedelta(hours=3)),
        "features_asof_utc": stamp(start - timedelta(hours=4)),
        "start_utc": stamp(start),
        "outcome_verified_at_utc": stamp(start + timedelta(hours=7)),
        "event_source_url": "https://testing.invalid/schedule",
        "feature_source_url": "https://testing.invalid/pregame",
        "outcome_source_url": "https://testing.invalid/outcome",
        "outcome": (i // 3) % 2,
        "features": {
            "pregame_home_form": ((i * 13) % 17) / 17,
            "pregame_away_form": ((i * 7) % 11) / 11,
        },
        "qualified_for_challenger_backtest": True,
        "independent_asof_review": True,
        "independent_outcome_review": True,
        "feature_snapshot_sha256": "a" * 64,
        "outcome_snapshot_sha256": "b" * 64,
    }


def next_event(model):
    snapshot = AS_OF + timedelta(hours=2)
    return {
        "event_id": "fictional-future-nba-1",
        "league": "nba",
        "market_type": "moneyline",
        "selection_type": "home",
        "snapshot_utc": stamp(snapshot),
        "features_asof_utc": stamp(snapshot - timedelta(minutes=15)),
        "start_utc": stamp(AS_OF + timedelta(days=1)),
        "availability_checked_at_utc": stamp(snapshot - timedelta(minutes=12)),
        "event_source_url": "https://testing.invalid/schedule",
        "feature_source_url": "https://testing.invalid/pregame",
        "availability_source_url": "https://testing.invalid/availability",
        "availability_reviewed": True,
        "features": {
            "pregame_home_form": 0.55,
            "pregame_away_form": 0.45,
        },
    }


class NbaProbabilityEngineTests(unittest.TestCase):
    def test_no_evidence_means_no_model(self):
        report, artifact = train_engine([], as_of=AS_OF)
        self.assertIsNone(artifact)
        self.assertEqual(report["result"], BLOCKED)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_small_historical_sample_blocks_without_override(self):
        report, model = train_engine([synthetic_game(i) for i in range(245)],
                                     as_of=AS_OF)
        self.assertEqual(report["result"], BLOCKED)
        self.assertIsNone(model)

    def test_train_on_synthetic_heldout_games_stays_uncertified(self):
        report, model = train_engine([synthetic_game(i) for i in range(260)],
                                     as_of=AS_OF)
        self.assertEqual(report["result"], "fitted_unverified_research_model")
        self.assertEqual(model["version"], VERSION)
        self.assertEqual(model["fit"]["training_rows"], 260)
        self.assertEqual(report["chronological_train_games"], 208)
        self.assertEqual(report["chronological_holdout_games"], 52)
        self.assertEqual(report["out_of_sample_exploratory_metrics"]["holdout_games"], 52)
        self.assertTrue(0 <= report["out_of_sample_exploratory_metrics"]["brier"] <= 1)
        self.assertEqual(report["independently_certified_training_records"], 0)
        self.assertEqual(report["certified_challenger_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertFalse(report["champion_001_modified"])
        self.assertEqual(digest({k: v for k, v in model.items()
                                 if k != "artifact_sha256"}), model["artifact_sha256"])

    def test_quarantined_rows_never_enter_train(self):
        rows = [synthetic_game(i) for i in range(4)]
        rows[0]["qualified_for_challenger_backtest"] = False
        report, model = train_engine(rows, as_of=AS_OF)
        self.assertIsNone(model)
        self.assertEqual(report["unqualified_rows_excluded"], 1)

    def test_missing_independent_review_attestation_rejected(self):
        row = synthetic_game(1)
        row["independent_asof_review"] = False
        with self.assertRaisesRegex(ValueError, "review"):
            train_engine([row], as_of=AS_OF)

    def test_missing_receipt_hash_rejected(self):
        row = synthetic_game(1)
        row["outcome_snapshot_sha256"] = "not-a-hash"
        with self.assertRaises(ValueError):
            train_engine([row], as_of=AS_OF)

    def test_wrong_sport_and_away_labels_rejected(self):
        for key, value in (("league", "nfl"), ("selection_type", "away"),
                           ("market_type", "player_points")):
            row = synthetic_game(1)
            row[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    train_engine([row], as_of=AS_OF)

    def test_future_or_unsettled_history_is_withheld(self):
        rows = [synthetic_game(i) for i in range(260)]
        rows[205]["outcome_verified_at_utc"] = "2028-01-01T00:00:00Z"
        report, model = train_engine(rows, as_of=AS_OF)
        self.assertEqual(report["future_or_unsettled_rows_excluded"], 1)
        self.assertIsNotNone(model)

    def test_duplicate_games_rejected(self):
        with self.assertRaises(ValueError):
            train_engine([synthetic_game(1), synthetic_game(1)], as_of=AS_OF)

    def test_mismatched_training_features_block(self):
        rows = [synthetic_game(i) for i in range(260)]
        rows[20]["features"] = {"pregame_other_form": 0.4}
        report, model = train_engine(rows, as_of=AS_OF)
        self.assertEqual(report["blocker"], "inconsistent_feature_schema")
        self.assertIsNone(model)

    def test_forecast_is_independent_of_sportsbook_odds(self):
        report, model = train_engine([synthetic_game(i) for i in range(260)],
                                     as_of=AS_OF)
        candidate = next_event(model)
        now = AS_OF + timedelta(hours=2, minutes=10)
        result = score_future_event(model, candidate, now=now)
        self.assertTrue(0 < result["research_probability_home_win"] < 1)
        self.assertFalse(result["market_implied_probability_used_as_model"])
        self.assertFalse(result["certified_prediction"])
        self.assertFalse(result["qualified_for_shadow_ledger"])
        self.assertFalse(result["bet_ready"])
        self.assertEqual(result["wager_stake"], 0)
        self.assertFalse(result["champion_001_modified"])

    def test_forged_model_artifact_rejected(self):
        _, model = train_engine([synthetic_game(i) for i in range(260)], as_of=AS_OF)
        tampered = copy.deepcopy(model)
        tampered["fit"]["coefficients"][0] += 10
        with self.assertRaises(ValueError):
            score_future_event(tampered, next_event(model),
                               now=AS_OF+timedelta(hours=2, minutes=10))

    def test_status_review_missing_blocks_forecast(self):
        _, model = train_engine([synthetic_game(i) for i in range(260)], as_of=AS_OF)
        candidate = next_event(model)
        candidate["availability_reviewed"] = False
        with self.assertRaises(ValueError):
            score_future_event(model, candidate,
                               now=AS_OF+timedelta(hours=2, minutes=10))

    def test_stale_injury_data_blocks_forecast(self):
        _, model = train_engine([synthetic_game(i) for i in range(260)], as_of=AS_OF)
        candidate = next_event(model)
        candidate["availability_checked_at_utc"] = stamp(AS_OF-timedelta(hours=4))
        with self.assertRaises(ValueError):
            score_future_event(model, candidate,
                               now=AS_OF+timedelta(hours=2, minutes=10))

    def test_past_tipoff_and_backdating_are_rejected(self):
        _, model = train_engine([synthetic_game(i) for i in range(260)], as_of=AS_OF)
        candidate = next_event(model)
        with self.assertRaises(ValueError):
            score_future_event(model, candidate,
                               now=AS_OF+timedelta(days=2))
        candidate["snapshot_utc"] = stamp(AS_OF-timedelta(minutes=1))
        with self.assertRaises(ValueError):
            score_future_event(model, candidate,
                               now=AS_OF+timedelta(hours=2, minutes=10))

    def test_forecast_feature_schema_locked(self):
        _, model = train_engine([synthetic_game(i) for i in range(260)], as_of=AS_OF)
        c = next_event(model)
        c["features"]["pregame_new_indicator"] = 0.3
        with self.assertRaises(ValueError):
            score_future_event(model, c,
                               now=AS_OF+timedelta(hours=2, minutes=10))

    def test_not_trained_on_market_probability(self):
        row = synthetic_game(1)
        row["features"]["pregame_implied_probability"] = 0.8
        with self.assertRaises(ValueError):
            train_engine([row], as_of=AS_OF)

    def test_missing_history_cli_writes_blocked_report_no_model(self):
        with TemporaryDirectory() as temp:
            p = Path(temp)
            self.assertEqual(main(["--history", str(p/"missing.jsonl"),
                                   "--output-dir", str(p/"output")]), 0)
            report = json.loads((p/"output"/"report.json").read_text())
            self.assertEqual(report["result"], BLOCKED)
            self.assertFalse((p/"output"/"research_model.json").exists())
            self.assertEqual(report["certified_champion_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
