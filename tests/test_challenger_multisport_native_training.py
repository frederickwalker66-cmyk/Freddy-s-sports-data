"""Synthetic safety tests only: no historical event or betting claims."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from challenger_multisport_native_capture import CAPTURE_LEAGUES, MARKETS, SCOPE, SIDES, check_model
from challenger_multisport_native_training import ROW_TYPE, main, train

NOW = datetime(2027, 7, 1, tzinfo=timezone.utc)


def records(league, n=300):
    rows = []
    for i in range(n):
        start = NOW - timedelta(days=n-i+1)
        v = (i * 37 % 101) / 100
        if len(SIDES[league]) == 3:
            result = "away" if v < 0.35 else "draw" if v < 0.65 else "home"
        else:
            result = "home" if v >= 0.5 else "away"
        rows.append({
            "record_type": ROW_TYPE, "league": league,
            "event_id": str(123456789 + i),
            "market_type": MARKETS[league], "settlement_scope": SCOPE[league],
            "start_utc": start.isoformat(),
            "snapshot_utc": (start - timedelta(hours=3)).isoformat(),
            "features_asof_utc": (start - timedelta(hours=4)).isoformat(),
            "outcome_verified_at_utc": (start + timedelta(hours=12)).isoformat(),
            "outcome": result, "features": {"pregame_team_strength": v},
            "event_source_url": "https://site.api.espn.com/test",
            "feature_source_url": "https://data.example.org/pregame",
            "outcome_source_url": "https://league.example.org/results",
            "feature_snapshot_sha256": "a" * 64,
            "outcome_snapshot_sha256": "b" * 64,
            "independent_feature_asof_review": True,
            "independent_outcome_review": True,
            "market_settlement_rules_verified": True,
            "qualified_for_challenger_training": True,
            "champion_001_modified": False,
        })
    return rows


class MultisportNativeTrainingTests(unittest.TestCase):
    def test_all_seven_league_models_match_capture_contract(self):
        for league in sorted(CAPTURE_LEAGUES):
            with self.subTest(league=league):
                report, models = train(records(league), now=NOW)
                self.assertIn(league, models)
                self.assertEqual(report["certified_positive_ev_bets"], 0)
                self.assertFalse(report["champion_001_modified"])
                self.assertIsNotNone(check_model(models[league], league, NOW))
                self.assertEqual(report["by_league"][league]["status"],
                                 "fitted_research_only_not_certified")

    def test_empty_data_fails_closed(self):
        report, models = train([], now=NOW)
        self.assertFalse(models)
        self.assertTrue(all(v["status"] == "blocked_insufficient_evidence"
                            for v in report["by_league"].values()))

    def test_no_automated_review_queue_or_retro_scores(self):
        x = records("nfl")[0]
        x["record_type"] = "challenger_eight_sport_evidence_review_queue_only"
        with self.assertRaisesRegex(ValueError, "only_manual"):
            train([x], now=NOW)

    def test_no_self_qualified_pregame_without_reviews(self):
        x = records("nhl")[0]
        x["independent_feature_asof_review"] = False
        with self.assertRaisesRegex(ValueError, "review_receipts"):
            train([x], now=NOW)

    def test_reject_after_kickoff_feature_and_future_outcome(self):
        x = records("mlb")[0]
        x["features_asof_utc"] = (datetime.fromisoformat(x["start_utc"]) + timedelta(minutes=2)).isoformat()
        with self.assertRaisesRegex(ValueError, "leakage"):
            train([x], now=NOW)
        x = records("nfl")[0]
        x["outcome_verified_at_utc"] = (NOW + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "leakage"):
            train([x], now=NOW)

    def test_hockey_draw_and_player_prop_excluded(self):
        x = records("nhl")[0]
        x["outcome"] = "draw"
        with self.assertRaisesRegex(ValueError, "cannot_be_settled"):
            train([x], now=NOW)
        x = records("nfl")[0]
        x["market_type"] = "passing_yards_over"
        with self.assertRaisesRegex(ValueError, "market_mismatch"):
            train([x], now=NOW)

    def test_duplicate_events_rejected(self):
        x = records("ncaab")[0]
        with self.assertRaisesRegex(ValueError, "duplicate_event"):
            train([x, dict(x)], now=NOW)

    def test_inconsistent_features_block_artifact(self):
        data = records("ncaaf")
        data[-1]["features"] = {"pregame_different_feature": 0.3}
        report, models = train(data, now=NOW)
        self.assertEqual(report["by_league"]["ncaaf"]["status"], "blocked_feature_schema_drift")
        self.assertNotIn("ncaaf", models)

    def test_holdout_outcomes_never_enter_fitted_model_or_source_digest(self):
        from challenger_multisport_native_training import make_fit, digest
        from challenger_prospective_outcome_validation import instant

        games = records("nfl", 300)
        report, models = train(games, now=NOW)
        self.assertIn("nfl", models)
        cut_day = instant(games[int(0.8 * len(games))]["start_utc"]).date()
        prior = [r for r in games if instant(r["start_utc"]).date() < cut_day]
        holdout = [r for r in games if instant(r["start_utc"]).date() >= cut_day]
        earliest_holdout = min(instant(r["snapshot_utc"]) for r in holdout)
        eligible = [r for r in prior if instant(r["outcome_verified_at_utc"]) <= earliest_holdout]
        trained_only = make_fit(eligible, sorted(eligible[0]["features"]), "nfl")
        model = models["nfl"]
        self.assertEqual(model["historical_source_evidence_sha256"], digest(eligible))
        self.assertEqual(model["binary_logistic_coefficients"],
                         trained_only["binary_logistic_coefficients"])
        self.assertEqual(model["feature_means"], trained_only["feature_means"])
        self.assertEqual(model["chronological_training_rows"], len(eligible))
        self.assertEqual(model["later_holdout_rows"], len(holdout))
        self.assertEqual(report["by_league"]["nfl"]["status"],
                         "fitted_research_only_not_certified")

    def test_missing_cli_creates_report_not_model(self):
        with TemporaryDirectory() as temp:
            p = Path(temp)
            code = main(["--evidence", str(p / "missing.jsonl"),
                         "--output-dir", str(p / "out"), "--allow-missing-evidence"])
            self.assertEqual(code, 0)
            self.assertEqual(sorted(x.name for x in (p / "out").iterdir()),
                             ["research_training_report.json"])
            report = json.loads((p / "out" / "research_training_report.json").read_text())
            self.assertEqual(report["trained_research_models"], [])


if __name__ == "__main__":
    unittest.main()
