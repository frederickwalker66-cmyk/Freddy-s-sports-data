"""Synthetic fixtures test NBA original review-custody gates, never pick accuracy."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from challenger_nba_probability import BLOCKED
from v8_nba_training_intake import audit, load_review_packets

NOW = datetime(2026, 11, 9, 17, tzinfo=timezone.utc)


def packet(event="401", league="nba"):
    return {
        "record_type": "challenger_original_bytes_feature_lineage_review_only",
        "league": league, "event_id": event,
        "home_team": "Home A", "away_team": "Away B",
        "event_start_utc": "2026-11-08T03:00:00Z",
        "snapshot_completed_at_utc": "2026-11-08T01:00:00Z",
        "source_event_line_sha256": "a" * 64,
        "github_run_id_self_reported": "123456",
        "asof_features_for_manual_review_only": {
            "pregame_away_prior_margin_avg": -3.2,
            "pregame_away_prior_win_rate": .4,
            "pregame_home_prior_margin_avg": 5.5,
            "pregame_home_prior_win_rate": .6,
        },
        "published_final_only": {
            "home_score": 112, "away_score": 103, "published_result": "home",
            "published_at_observation_utc": "2026-11-08T06:00:00Z",
        },
        "missing_evidence": ["independent_original_capture_authentication",
                             "independent_result_adjudication"],
        "original_bytes_match_same_run_receipt": True,
        "same_run_receipt_independently_authenticated": False,
        "qualified_for_challenger_training": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


class TrainingIntakeTests(unittest.TestCase):
    def test_packet_produces_review_worklist_not_model(self):
        rows, report, model = audit([packet()], now=NOW)
        self.assertEqual(report["nba_unique_original_capture_events"], 1)
        self.assertEqual(report["nba_manual_review_packets_with_pregame_features_and_published_finals"], 1)
        self.assertIsNone(model)
        self.assertFalse(rows[0]["training_eligible"])
        self.assertEqual(report["additional_independently_qualified_train_games_needed"], 200)
        self.assertEqual(report["additional_independently_qualified_holdout_games_needed"], 50)
        self.assertEqual(report["certified_v8_predictions"], 0)
        self.assertFalse(report["bet_ready"])

    def test_no_fabricated_training_with_no_original_evidence(self):
        rows, report, model = audit([], now=NOW)
        self.assertEqual(rows, [])
        self.assertIsNone(model)
        self.assertEqual(report["nba_unique_original_capture_events"], 0)
        self.assertEqual(report["status"], "HOLD_UNQUALIFIED_INDEPENDENT_EVIDENCE")

    def test_explicit_distinct_empty_reviewed_training_remains_blocked(self):
        rows, report, model = audit([packet()], now=NOW, qualified_history=[])
        self.assertIsNone(model)
        self.assertTrue(report["native_research_training_attempted"])
        self.assertEqual(report["native_research_training_report"]["result"], BLOCKED)
        self.assertEqual(report["native_research_training_report"]["rows_review_attested_and_settled"], 0)
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_conflicting_original_event_never_returns_after_duplicate(self):
        good = packet()
        conflicting = packet()
        conflicting["source_event_line_sha256"] = "b" * 64
        third = packet()
        rows, report, model = audit([good, conflicting, third], now=NOW)
        self.assertEqual(rows, [])
        self.assertEqual(report["excluded_review_packet_reasons"]["conflicting_earliest_capture_quarantined"], 1)
        self.assertEqual(report["excluded_review_packet_reasons"]["previously_conflicted_event_quarantined"], 1)

    def test_wrongly_promoted_packet_cannot_enter_worklist(self):
        bad = packet()
        bad["qualified_for_challenger_training"] = True
        rows, report, model = audit([bad], now=NOW)
        self.assertEqual(rows, [])
        self.assertEqual(report["nba_unique_original_capture_events"], 0)
        self.assertEqual(report["certified_v8_predictions"], 0)

    def test_bad_final_or_postgame_capture_cannot_be_review_ready(self):
        bad = packet()
        bad["snapshot_completed_at_utc"] = "2026-11-08T04:00:00Z"
        bad_result = packet(event="402")
        bad_result["published_final_only"]["published_result"] = "away"
        rows, report, model = audit([bad, bad_result], now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report["nba_manual_review_packets_with_pregame_features_and_published_finals"], 0)

    def test_original_packet_folder_limit_and_mixed_sports(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)/"123"/"prospective_validation"
            dest.mkdir(parents=True)
            (dest/"original_bytes_lineage_review.jsonl").write_text(
                json.dumps(packet())+"\n"+json.dumps(packet(league="nhl",event="456"))+"\n")
            rows, paths = load_review_packets(folder)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(paths), 1)
            review, status, model = audit(rows, now=NOW)
            self.assertEqual(len(review), 1)
            self.assertIsNone(model)


if __name__ == "__main__":
    unittest.main()
