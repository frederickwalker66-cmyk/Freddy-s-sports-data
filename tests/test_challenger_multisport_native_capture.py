"""Synthetic-only eight-sport native scoring tests; absolutely no real bets."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_multisport_native_capture import (
    BINARY, THREE_WAY, LEAGUES, SCOPE, MARKETS, SIDES,
    capture_multisport, check_model, digest, main
)

UTC = timezone.utc
NOW = datetime(2027, 1, 1, 14, 0, tzinfo=UTC)
START = NOW + timedelta(hours=5)
SNAP = NOW - timedelta(minutes=10)


def model(league):
    m = {
        "model_version": f"challenger-001-{league}-native-home-v1",
        "league": league, "market_type": MARKETS[league],
        "settlement_scope": SCOPE[league], "lane": "Challenger-001",
        "status": "unverified_research_model_not_deployed",
        "qualified_for_real_money_wagers": False,
        "calibration_independently_certified": False,
        "champion_001_modified": False,
        "chronological_training_rows": 250,
        "later_holdout_rows": 50,
        "historical_source_evidence_sha256": "b" * 64,
        "trained_at_utc": (NOW-timedelta(days=1)).isoformat(),
        "feature_names": ["pregame_away_form", "pregame_home_form"],
        "feature_means": [0.5, 0.5],
        "feature_stds": [0.2, 0.2],
    }
    if league in BINARY:
        m["binary_logistic_coefficients"] = [0, -0.6, 0.6]
    else:
        m["three_way_softmax_coefficients"] = {
            "home": [0.2, -0.4, 0.5],
            "draw": [0.0, 0.0, 0.0],
            "away": [-0.1, 0.4, -0.5],
        }
    m["artifact_sha256"] = digest(m)
    return m


def snapshot(league, event_id="401232344"):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league, "espn_schedule_event_id": event_id,
        "home_team": "Home", "away_team": "Away",
        "event_start_utc": START.isoformat(),
        "snapshot_completed_at_utc": SNAP.isoformat(),
        "schedule_observed_at_utc": (SNAP-timedelta(seconds=10)).isoformat(),
        "schedule_source_url": "https://site.api.espn.com/example",
        "odds_observations": [], "model_probability": None,
        "qualified_for_challenger_backtest": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


def candidate(league, event_id="401232344"):
    return {
        "league": league, "event_id": event_id,
        "market_type": MARKETS[league], "settlement_scope": SCOPE[league],
        "home_team": "Home", "away_team": "Away",
        "start_utc": START.isoformat(), "snapshot_utc": NOW.isoformat(),
        "features_asof_utc": (NOW-timedelta(minutes=15)).isoformat(),
        "availability_checked_at_utc": (NOW-timedelta(minutes=5)).isoformat(),
        "availability_reviewed": True,
        "event_source_url": "https://site.api.espn.com/example",
        "feature_source_url": "https://testing.invalid/pregame",
        "availability_source_url": "https://testing.invalid/lineups",
        "features": {"pregame_away_form": 0.4, "pregame_home_form": 0.6},
    }


class EightSportNativeTests(unittest.TestCase):
    def test_all_eight_markets_have_correct_outcome_definitions(self):
        self.assertEqual(len(LEAGUES), 8)
        self.assertEqual(len(BINARY), 6)
        self.assertEqual(len(THREE_WAY), 2)
        self.assertEqual(SCOPE["nhl"], "including_overtime")
        self.assertEqual(SIDES["uefa_champions_league"], ("home", "draw", "away"))

    def test_missing_models_fail_closed_all_leagues(self):
        data, report = capture_multisport(
            [snapshot(l) for l in LEAGUES], [], {}, now=NOW
        )
        self.assertFalse(data)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertEqual(report["per_league_model_gate"]["nba"],
                         "delegated_to_existing_nba_specialist_recorder")
        for l in LEAGUES:
            if l != "nba":
                self.assertTrue(report["per_league_model_gate"][l].startswith("blocked"))

    def test_binary_scoring_five_other_sports(self):
        for league in BINARY - {"nba"}:
            with self.subTest(league=league):
                rows, report = capture_multisport([snapshot(league)], [candidate(league)],
                                                   {league: model(league)}, now=NOW)
                self.assertEqual(len(rows), 2)
                self.assertEqual({r["selection_key"] for r in rows}, {"home", "away"})
                self.assertAlmostEqual(sum(r["research_probability"] for r in rows), 1, places=7)
                self.assertTrue(all(r["bet_ready"] is False for r in rows))
                self.assertEqual(report["unique_games_scored_uncertified"], 1)

    def test_three_way_soccer_scoring(self):
        for league in THREE_WAY:
            with self.subTest(league=league):
                rows, _ = capture_multisport([snapshot(league)], [candidate(league)],
                                              {league: model(league)}, now=NOW)
                self.assertEqual(len(rows), 3)
                self.assertEqual({r["selection_key"] for r in rows}, {"home", "draw", "away"})
                self.assertAlmostEqual(sum(r["research_probability"] for r in rows), 1, places=7)
                self.assertEqual({r["settlement_scope"] for r in rows},
                                 {"regulation_90_minutes_including_stoppage"})

    def test_no_nba_recoding_as_generic_model(self):
        r, report = capture_multisport([snapshot("nba")], [candidate("nba")],
                                        {"nba": model("nba")}, now=NOW)
        self.assertFalse(r)
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_player_props_cannot_be_recast_as_game_winner(self):
        c = candidate("nfl")
        c["market_type"] = "player_points"
        r, report = capture_multisport([snapshot("nfl")], [c],
                                        {"nfl": model("nfl")}, now=NOW)
        self.assertFalse(r)
        self.assertGreater(report["rejected"]["identity_market_source_or_availability_invalid"], 0)

    def test_market_break_even_cannot_be_substituted(self):
        c = candidate("mlb")
        c["probability_source"] = "sportsbook_implied"
        r, report = capture_multisport([snapshot("mlb")], [c], {"mlb": model("mlb")}, now=NOW)
        self.assertFalse(r)
        self.assertGreater(report["rejected"]["identity_market_source_or_availability_invalid"], 0)

    def test_artifact_integrity_and_training_requirements(self):
        m = model("ncaab")
        m["chronological_training_rows"] = 0
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            check_model(m, "ncaab", NOW)
        m = model("ncaab")
        m["chronological_training_rows"] = 199
        m["artifact_sha256"] = digest({k: v for k, v in m.items()
                                       if k != "artifact_sha256"})
        with self.assertRaisesRegex(ValueError, "requirements"):
            check_model(m, "ncaab", NOW)

    def test_stale_availability_and_future_event_deny(self):
        c = candidate("nhl")
        c["availability_checked_at_utc"] = (NOW - timedelta(hours=3)).isoformat()
        r, _ = capture_multisport([snapshot("nhl")], [c], {"nhl": model("nhl")}, now=NOW)
        self.assertFalse(r)
        c = candidate("nhl")
        r, report = capture_multisport([snapshot("nhl")], [c], {"nhl": model("nhl")},
                                       now=START + timedelta(minutes=1))
        self.assertFalse(r)

    def test_future_model_training_is_refused(self):
        m = model("nfl")
        m["trained_at_utc"] = (NOW + timedelta(hours=1)).isoformat()
        m["artifact_sha256"] = digest({k: v for k, v in m.items()
                                       if k != "artifact_sha256"})
        r, report = capture_multisport([snapshot("nfl")], [candidate("nfl")],
                                       {"nfl": m}, now=NOW)
        self.assertFalse(r)
        self.assertTrue(report["per_league_model_gate"]["nfl"].startswith("blocked"))

    def test_missing_inputs_cli_reports_zero_and_writes_empty_file(self):
        with TemporaryDirectory() as d:
            p = Path(d)
            self.assertEqual(main(["--snapshots", str(p/"none1"),
                                   "--candidates", str(p/"none2"),
                                   "--model-dir", str(p/"models"),
                                   "--output-dir", str(p/"output")]), 0)
            self.assertEqual((p/"output"/"native_multisport_forecasts.jsonl").read_text(), "")
            report = json.loads((p/"output"/"multisport_native_capture_report.json").read_text())
            self.assertEqual(report["market_selections_captured_uncertified"], 0)


if __name__ == "__main__":
    unittest.main()
