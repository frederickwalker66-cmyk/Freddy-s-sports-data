"""Regression tests for quarantined native Challenger forecast-to-final evidence bridge."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_calibration_evidence_bridge import (
    stage_review_queue, main, valid_native, valid_linked
)

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
EVENT = "401809001"


def linked():
    return {
        "league": "nba", "espn_event_id": EVENT,
        "status": "linked_to_espn_published_final_only",
        "snapshot_completed_at_utc": "2026-11-04T18:00:00+00:00",
        "event_start_utc": "2026-11-05T00:00:00+00:00",
        "home_team": "Phoenix Suns", "away_team": "Orlando Magic",
        "published_outcome": {
            "result": "home",
            "published_retrieved_at_utc": "2026-11-05T05:00:00+00:00",
            "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        },
        "independent_league_outcome_verified": False,
        "model_prediction_at_capture": None,
        "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def native():
    return {
        "stage": "challenger_001_prospective_research_only",
        "event_id": EVENT, "market": "nba_moneyline", "selection": "home",
        "model_version": "challenger-001-nba-home-moneyline-v1",
        "model_sha256": "a" * 64,
        "scored_at_utc": "2026-11-04T19:00:00+00:00",
        "snapshot_utc": "2026-11-04T18:55:00+00:00",
        "research_probability_home_win": .58,
        "market_implied_probability_used_as_model": False,
        "qualified_for_shadow_ledger": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


class BridgeTests(unittest.TestCase):
    def test_no_native_forecasts_is_honestly_blocked(self):
        queue, report = stage_review_queue([linked()], [], as_of=NOW)
        self.assertEqual(queue, [])
        self.assertEqual(report["status"], "blocked_no_native_challenger_forecasts")
        self.assertEqual(report["independently_qualified_calibration_rows"], 0)
        self.assertFalse(report["calibration_evidence_file_created"])

    def test_native_format_is_staged_but_never_calibration_ready(self):
        queue, report = stage_review_queue([linked()], [native()], as_of=NOW)
        self.assertEqual(len(queue), 1)
        item = queue[0]
        self.assertEqual(item["native_forecast_value_claimed"], .58)
        self.assertFalse(item["independent_outcome_verified"])
        self.assertFalse(item["model_output_before_event_verified"])
        self.assertFalse(item["eligible_for_calibration"])
        self.assertFalse(report["eligible_for_isotonic_fit"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_untrained_baseline_cannot_be_accepted_as_native(self):
        wrong = deepcopy(native())
        wrong["stage"] = "prospective_untrained_research_baseline_forecast"
        wrong["baseline_home_win_probability"] = .9
        queue, report = stage_review_queue(
            [linked()], [wrong],
            {"stage": "untrained_challenger_shadow_baseline_descriptive_scorecard",
             "unique_valid_forecasts": 151}, NOW)
        self.assertFalse(queue)
        self.assertEqual(report["untrained_fixed_rule_forecasts_excluded"], 151)
        self.assertEqual(report["rejected"]["not_native_challenger_forecast_or_bad_receipt"], 1)

    def test_sportsbook_implied_probabilities_are_rejected(self):
        wrong = deepcopy(native())
        wrong["market_implied_probability_used_as_model"] = True
        queue, report = stage_review_queue([linked()], [wrong], as_of=NOW)
        self.assertFalse(queue)
        self.assertEqual(report["independently_qualified_calibration_rows"], 0)

    def test_bets_and_champion_changes_are_rejected(self):
        wrong = deepcopy(native())
        wrong["bet_ready"] = True
        self.assertEqual(stage_review_queue([linked()], [wrong], as_of=NOW)[0], [])
        other = deepcopy(native())
        other["champion_001_modified"] = True
        self.assertEqual(stage_review_queue([linked()], [other], as_of=NOW)[0], [])

    def test_forecast_after_tip_is_rejected(self):
        late = deepcopy(native())
        late["scored_at_utc"] = "2026-11-05T00:01:00+00:00"
        queue, report = stage_review_queue([linked()], [late], as_of=NOW)
        self.assertEqual(queue, [])
        self.assertEqual(report["rejected"]["pregame_forecast_or_result_timing_mismatch"], 1)

    def test_unverified_outcome_source_and_false_identity_rejected(self):
        bad = deepcopy(linked())
        bad["published_outcome"]["source_url"] = "https://example.com/score"
        self.assertEqual(stage_review_queue([bad], [native()], as_of=NOW)[0], [])
        wrong_id = deepcopy(native())
        wrong_id["event_id"] = "999999"
        self.assertEqual(stage_review_queue([linked()], [wrong_id], as_of=NOW)[0], [])

    def test_cannot_promote_self_declared_review_flags(self):
        f = deepcopy(native())
        f["independent_outcome_verified"] = True
        f["model_output_before_event_verified"] = True
        queue, report = stage_review_queue([linked()], [f], as_of=NOW)
        self.assertEqual(len(queue), 1)
        self.assertFalse(queue[0]["independent_outcome_verified"])
        self.assertFalse(queue[0]["model_output_before_event_verified"])
        self.assertFalse(report["review_flags_automatically_promoted"])

    def test_duplicate_forecast_is_quarantined(self):
        queue, report = stage_review_queue([linked()], [native(), native()], as_of=NOW)
        self.assertFalse(queue)
        self.assertEqual(report["rejected"]["duplicate_native_event"], 1)

    def test_missing_sources_write_diagnostic_only(self):
        with TemporaryDirectory() as d:
            out = Path(d) / "report"
            self.assertEqual(main(["--archive-root", str(Path(d)/"empty"),
                                   "--output-dir", str(out)]), 0)
            report = json.loads((out / "report.json").read_text())
            self.assertEqual(report["status"], "blocked_no_archived_linked_finals")
            self.assertEqual((out/"review_queue.jsonl").read_text(), "")
            self.assertFalse((out/"challenger_oos_probabilities.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
