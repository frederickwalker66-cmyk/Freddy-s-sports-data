"""Synthetic-only safeguards for genuine native Challenger pregame receipt capture."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_probability import VERSION, digest
from challenger_native_pregame_capture import capture, main

UTC = timezone.utc
NOW = datetime(2027, 1, 1, 12, 3, tzinfo=UTC)
EVENT_START = datetime(2027, 1, 1, 19, tzinfo=UTC)
SNAP = datetime(2027, 1, 1, 12, tzinfo=UTC)
EID = "401123456"


def stamp(d):
    return d.isoformat()


def make_model():
    model = {
        "version": VERSION, "lane": "Challenger-001",
        "market_type": "nba_home_moneyline",
        "status": "unverified_research_model_not_deployed",
        "trained_at_utc": "2027-01-01T00:00:00+00:00",
        "last_training_event_start_utc": "2026-12-30T00:00:00+00:00",
        "fit": {"features": ["pregame_away_form", "pregame_home_form"],
                "means": [0.5, 0.5], "standard_deviations": [0.2, 0.2],
                "coefficients": [0.0, -0.4, 0.4],
                "training_home_win_rate": .5, "training_rows": 250},
        "qualified_for_real_money_wagers": False,
        "champion_001_modified": False,
    }
    model["artifact_sha256"] = digest(model)
    return model


def make_snapshot():
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": EID,
        "home_team": "Synthetic Home", "away_team": "Synthetic Away",
        "event_start_utc": stamp(EVENT_START),
        "snapshot_completed_at_utc": stamp(SNAP),
        "schedule_observed_at_utc": stamp(SNAP - timedelta(minutes=1)),
        "schedule_source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "odds_observations": [],
        "qualified_for_challenger_backtest": False,
        "model_probability": None,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


def make_candidate():
    return {
        "league": "nba", "market_type": "moneyline", "selection_type": "home",
        "event_id": EID,
        "home_team": "Synthetic Home", "away_team": "Synthetic Away",
        "start_utc": stamp(EVENT_START),
        "snapshot_utc": stamp(SNAP),
        "features_asof_utc": stamp(SNAP - timedelta(minutes=10)),
        "availability_checked_at_utc": stamp(SNAP - timedelta(minutes=5)),
        "availability_reviewed": True,
        "event_source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "feature_source_url": "https://testing.invalid/pregame",
        "availability_source_url": "https://testing.invalid/availability",
        "features": {"pregame_home_form": 0.6, "pregame_away_form": 0.4},
    }


class NativeCaptureTests(unittest.TestCase):
    def test_missing_model_fails_closed(self):
        records, report = capture([make_snapshot()], [make_candidate()], None, now=NOW)
        self.assertFalse(records)
        self.assertEqual(report["status"], "blocked_missing_or_invalid_research_model")
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_missing_candidates_fails_closed(self):
        r, report = capture([make_snapshot()], [], make_model(), now=NOW)
        self.assertFalse(r)
        self.assertEqual(report["status"], "blocked_missing_fresh_native_feature_candidates")

    def test_valid_synthetic_future_scores_research_only(self):
        receipt, report = capture([make_snapshot()], [make_candidate()], make_model(), now=NOW,
                                  run_id="test-run")
        self.assertEqual(len(receipt), 1)
        one = receipt[0]
        self.assertGreater(one["research_probability_home_win"], 0.5)
        self.assertEqual(one["event_id"], EID)
        self.assertEqual(one["stage"], "challenger_001_prospective_research_only")
        self.assertEqual(one["archive_run_id_self_reported"], "test-run")
        self.assertFalse(one["market_implied_probability_used_as_model"])
        self.assertFalse(one["native_model_fit_independently_certified"])
        self.assertFalse(one["eligible_for_isotonic_fit"])
        self.assertFalse(one["bet_ready"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_invalid_signature_rejected(self):
        model = make_model()
        model["fit"]["coefficients"][0] = 10.0
        result, report = capture([make_snapshot()], [make_candidate()], model, now=NOW)
        self.assertFalse(result)
        self.assertFalse(report["research_model_artifact_present_and_format_valid"])

    def test_late_gameday_capture_rejected(self):
        result, report = capture([make_snapshot()], [make_candidate()], make_model(),
                                 now=EVENT_START + timedelta(minutes=1))
        self.assertFalse(result)
        self.assertEqual(report["status"], "blocked_no_usable_nba_pregame_snapshots")

    def test_wrong_team_or_event_id_rejected(self):
        c = make_candidate()
        c["home_team"] = "Other Home"
        r, _ = capture([make_snapshot()], [c], make_model(), now=NOW)
        self.assertFalse(r)
        c = make_candidate()
        c["event_id"] = "999111"
        r, _ = capture([make_snapshot()], [c], make_model(), now=NOW)
        self.assertFalse(r)

    def test_no_market_probability_substitution(self):
        c = make_candidate()
        c["probability_source"] = "sportsbook_implied"
        r, report = capture([make_snapshot()], [c], make_model(), now=NOW)
        self.assertFalse(r)
        self.assertEqual(report["rejections"]["market_probability_disallowed"], 1)

    def test_stale_availability_and_future_features_rejected(self):
        c = make_candidate()
        c["availability_checked_at_utc"] = stamp(SNAP - timedelta(hours=3))
        r, _ = capture([make_snapshot()], [c], make_model(), now=NOW)
        self.assertFalse(r)
        c = make_candidate()
        c["features_asof_utc"] = stamp(SNAP + timedelta(minutes=1))
        r, _ = capture([make_snapshot()], [c], make_model(), now=NOW)
        self.assertFalse(r)

    def test_duplicate_candidates_no_extra_predictions(self):
        c = make_candidate()
        records, report = capture([make_snapshot()], [c, c], make_model(), now=NOW)
        self.assertEqual(len(records), 1)
        self.assertEqual(report["rejections"]["duplicate_candidate"], 1)

    def test_missing_inputs_cli_reports_and_creates_empty_receipt(self):
        with TemporaryDirectory() as d:
            p = Path(d)
            rc = main(["--snapshots", str(p/"missing-snapshot.jsonl"),
                       "--model", str(p/"missing-model.json"),
                       "--candidates", str(p/"missing-candidates.jsonl"),
                       "--output-dir", str(p/"out")])
            self.assertEqual(rc, 0)
            self.assertEqual((p/"out"/"native_challenger_forecasts.jsonl").read_text(), "")
            report = json.loads((p/"out"/"native_forecast_capture_report.json").read_text())
            self.assertEqual(report["status"], "blocked_missing_or_invalid_research_model")
            self.assertEqual(report["actual_native_research_forecasts_written"], 0)


if __name__ == "__main__":
    unittest.main()
