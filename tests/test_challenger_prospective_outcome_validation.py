"""Deterministic safeguards for prospective snapshot-to-result linkage."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone

from challenger_prospective_outcome_validation import reconcile

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def snapshot():
    return {
        "record_type": "prospective_evidence_snapshot_research_only", "league": "nba",
        "espn_schedule_event_id": "401001", "home_team": "Atlanta Hawks",
        "away_team": "Cleveland Cavaliers",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00Z",
        "schedule_observed_at_utc": "2026-10-29T21:29:00Z",
        "schedule_source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "team_form_available_for_both_teams": True,
        "odds_observations": [], "certified_prediction": False,
        "model_probability": None, "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def outcome():
    return {
        "record_type": "historical_completed_game_research", "league": "nba",
        "espn_event_id": "401001", "home_team": "Atlanta Hawks",
        "away_team": "Cleveland Cavaliers",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "retrieved_at_utc": "2026-10-30T05:00:00Z",
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "outcome_source": "espn_public_scoreboard",
        "home_score": 108, "away_score": 99, "result": "home",
        "champion_001_modified": False,
    }


class ValidationTests(unittest.TestCase):
    def test_valid_result_linked_but_no_certification(self):
        rows, report = reconcile([snapshot()], [outcome()], NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "linked_to_espn_published_final_only")
        self.assertEqual(rows[0]["published_outcome"]["result"], "home")
        self.assertFalse(rows[0]["qualified_for_challenger_backtest"])
        self.assertFalse(report["model_accuracy_established"])
        self.assertEqual(report["verified_historical_training_examples"], 0)

    def test_ahead_of_tipoff_and_post_start_rejected(self):
        s = snapshot()
        s["snapshot_completed_at_utc"] = "2026-10-30T00:00:01Z"
        rows, report = reconcile([s], [outcome()], NOW)
        self.assertEqual(rows, [])
        self.assertEqual(report["rejected_rows"]["invalid_pregame_snapshot"], 1)

    def test_missing_outcome_stays_pending(self):
        rows, report = reconcile([snapshot()], [], NOW)
        self.assertEqual(rows[0]["status"], "awaiting_published_final")
        self.assertIsNone(rows[0]["published_outcome"])
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_duplicate_archive_snapshots_choose_earliest(self):
        later = snapshot()
        later["snapshot_completed_at_utc"] = "2026-10-29T22:00:00Z"
        rows, report = reconcile([later, snapshot()], [outcome()], NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["snapshot_completed_at_utc"], "2026-10-29T21:30:00+00:00")
        self.assertEqual(report["snapshot_rows_seen"], 2)

    def test_team_mismatch_does_not_link(self):
        other = outcome()
        other["away_team"] = "Boston Celtics"
        rows, report = reconcile([snapshot()], [other], NOW)
        self.assertEqual(rows[0]["status"], "ambiguous_or_mismatched_published_final")
        self.assertEqual(report["independently_adjudicated_outcomes"], 0)

    def test_conflicting_published_results_rejected_as_ambiguous(self):
        other = outcome()
        other["home_score"], other["away_score"] = 101, 99
        rows, _ = reconcile([snapshot()], [outcome(), other], NOW)
        self.assertEqual(rows[0]["status"], "ambiguous_or_mismatched_published_final")

    def test_identical_later_archive_results_do_not_look_ambiguous(self):
        older = outcome()
        newer = outcome()
        newer["retrieved_at_utc"] = "2026-10-31T01:00:00Z"
        rows, report = reconcile([snapshot()], [older, newer], NOW)
        self.assertEqual(rows[0]["status"], "linked_to_espn_published_final_only")
        self.assertEqual(rows[0]["published_outcome"]["consistent_archive_observations"], 2)
        self.assertEqual(report["verified_historical_training_examples"], 0)

    def test_revised_final_score_is_quarantined(self):
        revised = outcome()
        revised["home_score"] = 109
        revised["retrieved_at_utc"] = "2026-10-31T01:00:00Z"
        rows, report = reconcile([snapshot()], [outcome(), revised], NOW)
        self.assertEqual(rows[0]["status"], "ambiguous_or_mismatched_published_final")
        self.assertIsNone(rows[0]["published_outcome"])
        self.assertFalse(report["model_accuracy_established"])

    def test_multiple_observations_with_same_id_but_different_teams_fail(self):
        other = outcome()
        other["home_team"] = "Boston Celtics"
        rows, _ = reconcile([snapshot()], [outcome(), other], NOW)
        self.assertEqual(rows[0]["status"], "ambiguous_or_mismatched_published_final")

    def test_invalid_outcome_does_not_create_false_final(self):
        other = outcome()
        other["retrieved_at_utc"] = "2026-10-29T23:00:00Z"
        rows, report = reconcile([snapshot()], [other], NOW)
        self.assertEqual(rows[0]["status"], "awaiting_published_final")
        self.assertEqual(report["rejected_rows"]["invalid_published_outcome"], 1)

    def test_unverified_price_flag_fails_closed(self):
        s = snapshot()
        s["odds_observations"] = [{"direct_draftkings_checkout_verified": True,
                                   "received_at_utc": "2026-10-29T21:25:00Z"}]
        rows, report = reconcile([s], [outcome()], NOW)
        self.assertEqual(rows, [])
        self.assertEqual(report["rejected_rows"]["invalid_pregame_snapshot"], 1)

    def test_retroactive_pregame_fabrication_rejected(self):
        s = snapshot()
        s["snapshot_completed_at_utc"] = "2026-11-01T00:00:00Z"
        rows, _ = reconcile([s], [outcome()], NOW)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
