"""Synthetic-only tests for nontrainable NBA history-review intake."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

from challenger_nba_history_intake import REVIEW_BLOCKERS, build_intake, main
from challenger_nba_probability import train_engine

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def packet(**overrides):
    row = {
        "record_type": "challenger_eight_sport_evidence_review_queue_only",
        "league": "nba", "event_id": "401701001",
        "home_team": "Example Home", "away_team": "Example Away",
        "snapshot_utc": "2026-10-30T18:00:00+00:00",
        "features_asof_utc": "2026-10-30T18:00:00+00:00",
        "start_utc": "2026-10-30T19:00:00+00:00",
        "published_outcome_seen_utc": "2026-10-31T08:00:00+00:00",
        "schedule_source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "published_result_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "research_target": "published_score_winner_binary_research",
        "review_status": "needs_league_rule_and_independent_outcome_review",
        "features": {
            "pregame_home_prior_win_rate": 0.6,
            "pregame_away_prior_win_rate": 0.4,
            "pregame_home_prior_margin_avg": 4.0,
            "pregame_away_prior_margin_avg": -2.0,
        },
        "published_score_only": {"home": 106, "away": 98},
        "published_result_research_label": "home",
        "source_receipt_sha256_not_independently_verified": "a"*64,
        "linked_receipt_sha256_not_independently_verified": "b"*64,
        "independent_feature_asof_review": False,
        "independent_outcome_adjudication": False,
        "market_settlement_rules_verified": False,
        "qualified_for_challenger_backtest": False,
        "eligible_to_train_probability_model": False,
        "certified_prediction": False,
        "model_probability": None,
        "bet_ready": False,
        "champion_001_modified": False,
    }
    row.update(overrides)
    return row


class HistoryIntakeTests(unittest.TestCase):
    def test_valid_packet_is_not_a_training_record(self):
        rows, report = build_intake([packet()], NOW)
        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["outcome"], 1)
        self.assertEqual(item["selection_type"], "home")
        self.assertFalse(item["qualified_for_challenger_backtest"])
        self.assertFalse(item["eligible_to_train_probability_model"])
        self.assertFalse(item["independent_asof_review"])
        self.assertFalse(item["independent_outcome_review"])
        self.assertIsNone(item["feature_snapshot_sha256"])
        self.assertEqual(item["review_required"], REVIEW_BLOCKERS)
        self.assertEqual(report["independently_verified_training_records"], 0)
        self.assertEqual(report["shortfall_vs_250_structural_candidates"], 249)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_cannot_be_promoted_by_nba_probability_engine(self):
        rows, _ = build_intake([packet()], NOW)
        report, model = train_engine(rows, as_of=NOW)
        self.assertEqual(report["result"], "blocked_no_qualified_nba_training_data")
        self.assertIsNone(model)
        self.assertEqual(report["unqualified_rows_excluded"], 1)

    def test_source_and_temporal_leaks_rejected(self):
        cases = [
            {"snapshot_utc": "2026-10-30T19:00:00Z"},
            {"features_asof_utc": "2026-10-30T18:00:01Z"},
            {"published_outcome_seen_utc": "2026-10-30T18:50:00Z"},
            {"published_outcome_seen_utc": "2026-11-01T00:00:00Z"},
            {"schedule_source_url": "https://evil.invalid/scoreboard"},
            {"published_result_url": "http://site.api.espn.com/bad"},
            {"features": {"pregame_wins": 1.0}},
            {"model_probability": 0.7},
            {"qualified_for_challenger_backtest": True},
            {"independent_outcome_adjudication": True},
            {"champion_001_modified": True},
            {"published_result_research_label": "away"},
            {"published_score_only": {"home": 98, "away": 98}},
            {"source_receipt_sha256_not_independently_verified": "invalid"},
        ]
        for update in cases:
            with self.subTest(update=update):
                rows, report = build_intake([packet(**update)], NOW)
                self.assertEqual(rows, [])
                self.assertEqual(report["counts"]["invalid_nba_rows"], 1)

    def test_away_label_is_still_home_team_outcome_zero(self):
        rows, report = build_intake([packet(
            published_score_only={"home": 91, "away": 108},
            published_result_research_label="away")], NOW)
        self.assertEqual(rows[0]["outcome"], 0)
        self.assertEqual(report["nba_review_candidates"], 1)

    def test_duplicate_event_rejects_every_copy(self):
        a=packet()
        b=packet(published_score_only={"home": 99, "away": 97})
        rows, report = build_intake([a,b], NOW)
        self.assertEqual(rows, [])
        self.assertEqual(report["counts"]["ambiguous_duplicate_event_ids"], 1)
        self.assertEqual(report["counts"]["duplicate_rows_quarantined"], 2)

    def test_other_sports_excluded_and_invalid_rows_quarantined(self):
        rows, report = build_intake([packet(league="mls"), "bad", packet()], NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report["counts"]["non_nba_rows_excluded"], 1)
        self.assertEqual(report["counts"]["invalid_research_rows"], 1)

    def test_cli_generates_review_only_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/"queue.jsonl"
            src.write_text(json.dumps(packet())+"\n", encoding="utf-8")
            output=root/"out"
            self.assertEqual(main(["--review-queue",str(src),"--output-dir",str(output)]),0)
            candidates=(output/"nba_history_review_candidates.jsonl").read_text()
            summary=json.loads((output/"nba_history_intake_report.json").read_text())
            self.assertIn('"qualified_for_challenger_backtest": false', candidates)
            self.assertEqual(summary["trained_models_created"], 0)
            self.assertFalse((output/"historical_results.jsonl").exists())
            self.assertFalse((output/"research_model.json").exists())


if __name__ == "__main__":
    unittest.main()
