"""SportsGameOdds source is never converted into a verified betting edge."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_sgo_research import audit_source_archive
from v8_one_command import execute

NOW = datetime(2026, 11, 13, 16, 0, tzinfo=timezone.utc)


def quote(timestamp="2026-11-13T15:59:10Z", *, source="sportsgameodds_v2",
          market="point_spread", player=None):
    return {
        "source": source, "record_type": "pregame_odds_observation",
        "sportsbook": "draftkings", "league": "nba",
        "market_type": market, "selection": "Home",
        "home_team": "Home", "away_team": "Away",
        "event_id": "sgo:synthetic-event",
        "player_id": player,
        "line": -2.5, "odds_american": -110,
        "timestamp": timestamp,
        "recorded_at": "2026-11-13T15:59:15Z",
        "event_start_time": "2026-11-13T23:00:00Z",
        "is_main_line": False, "certified_prediction": False,
        "model_probability": None,
        "cross_provider_identity_verified": False,
        "draftkings_price_independently_verified": False,
    }


class SourceResearchTests(unittest.TestCase):
    def test_existing_legacy_sgo_repository_secret_aliases_are_recognized(self):
        # Prior October collection workflows accepted these names; a newer
        # workflow must not quietly lose authorization from an existing secret.
        workflow = Path(".github/workflows/sportsgameodds-research.yml").read_text()
        legacy_names = (
            "SPORTSGAMEODDS_API_KEY", "SPORTSGAMEODDS_KEY",
            "SPORTS_GAME_ODDS_API_KEY", "SPORTSGAMEODDS",
            "SPORTS_GAME_ODDS", "SPORTSGAMESODD",
            "SPORTSGAMESODDS", "SPORTS_GAMES_ODD",
            "SPORTS_GAMES_ODDS", "SPORTSGAMEODD", "SPORTS_GAME_ODD",
        )
        for name in legacy_names:
            with self.subTest(name=name):
                self.assertIn("secrets." + name, workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertIn("no network if absent", workflow)
        self.assertIn("--max-pages 1", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_excluded_sgo_source_cannot_auto_replay_in_one_command(self):
        # Legacy source tests remain retrospective only: live one-command
        # workflow must never load archived SGO or trigger on its collector.
        workflow = Path(".github/workflows/v8-one-command.yml").read_text()
        self.assertIn(
            "workflows: ['Collect SharpAPI DraftKings pregame odds']", workflow
        )
        self.assertNotIn(
            "workflows: ['Collect SharpAPI DraftKings pregame odds', "
            "'SportsGameOdds NBA NFL MLB research — manual capped intake']", workflow
        )
        self.assertNotIn(
            "Retrieve last completed SportsGameOdds source artifact", workflow
        )
        self.assertNotIn("--sgo-archive-dir saved_sgo_archives", workflow)
        source_workflow = Path(".github/workflows/sportsgameodds-research.yml").read_text()
        self.assertNotIn("  schedule:", source_workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", source_workflow)

    def test_empty_archive_reports_unavailable_not_false_picks(self):
        with tempfile.TemporaryDirectory() as folder:
            r = audit_source_archive(folder, now=NOW)
            self.assertEqual(r["status"], "no_successful_sgo_capture_artifacts")
            self.assertEqual(r["rows_examined"], 0)
            self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_valid_recent_quotes_still_hold_and_are_not_main_line_certified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sportsgameodds_dk_20261113T155915Z.jsonl").write_text(
                json.dumps(quote()) + "\n" +
                json.dumps(quote(market="player_points", player="P1")) + "\n")
            r = audit_source_archive(root, now=NOW)
            self.assertEqual(r["rows_examined"], 2)
            self.assertEqual(r["recent_upcoming_quote_reference_count"], 2)
            self.assertEqual(r["source_labeled_quotes_by_market"],
                             {"nba_player_prop": 1, "nba_point_spread": 1})
            self.assertFalse(r["source_primary_market_status_authenticated"])
            self.assertEqual(r["independently_validated_native_model_probabilities"], 0)
            self.assertFalse(r["bet_ready"])
            self.assertFalse(r["champion_001_modified"])
            for row in r["recent_upcoming_quote_references"]:
                self.assertIsNone(row["native_model_probability"])
                self.assertFalse(row["qualified_main_line"])
                self.assertFalse(row["sportsbook_checkout_verified"])

    def test_stale_is_archived_without_realtime_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            x = quote(timestamp="2026-11-13T15:30:00Z")
            x["recorded_at"] = "2026-11-13T15:30:05Z"
            Path(folder, "sportsgameodds_dk_20261113T153005Z.jsonl").write_text(json.dumps(x)+"\n")
            r = audit_source_archive(folder, now=NOW)
            self.assertEqual(r["source_labeled_quotes_by_market"]["nba_point_spread"], 1)
            self.assertEqual(r["recent_upcoming_quote_reference_count"], 0)

    def test_source_or_model_probability_promotion_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            x = quote()
            x["model_probability"] = .95
            y = quote(source="sharpapi_rest")
            z = quote()
            z["is_main_line"] = True
            path = Path(folder, "sportsgameodds_dk_test.jsonl")
            path.write_text("\n".join(json.dumps(a) for a in (x,y,z))+"\n")
            r = audit_source_archive(folder, now=NOW)
            self.assertEqual(r["rows_examined"], 3)
            self.assertEqual(r["source_labeled_quotes_by_market"], {})
            self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_mixed_market_phone_command_remains_free_and_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            r=execute("run_mixed_market", now=NOW, output_dir=Path(folder)/"output",
                      sgo_archive_dir=Path(folder)/"not_present")
            source = r["sportsgameodds_archive_research"]
            self.assertEqual(source["status"], "no_successful_sgo_capture_artifacts")
            self.assertEqual(r["certified_positive_ev_bets"], 0)
            self.assertFalse(r["champion_001_modified"])
            self.assertEqual(r["sportsbook_api_requests"], 0)
            self.assertTrue((Path(folder)/"output"/"SGO_SEPARATE_SOURCE_RESEARCH.json").exists())


if __name__=="__main__":
    unittest.main()
