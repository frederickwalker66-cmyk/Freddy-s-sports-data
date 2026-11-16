"""Zero-network regression checks for NBA player-prop source gap diagnostics."""
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from v8_nba_prop_source_readiness import inspect_nba_prop_capture, render_nba_prop_capture
from v8_one_command import execute

NOW = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)  # 10 AM EST


def prop(side="over", received="2026-11-16T14:50:00Z", **changes):
    odds = -110
    row = {
        "source": "sharpapi_rest", "sportsbook": "draftkings",
        "record_type": "pregame_odds_observation",
        "league": "nba", "event_id": "test-original-nba-event",
        "home_team": "Example Home", "away_team": "Example Away",
        "player_id": None, "player_name": "Sample Athlete",
        "market_type": "player_points", "line": 24.5,
        "selection_type": side,
        "is_player_prop": True,
        "is_main_line": True,
        "is_alternate_line": False,
        "odds_american": odds,
        "odds_decimal": 1 + 100 / abs(odds),
        "timestamp": "2026-11-16T14:49:00Z" if received == "2026-11-16T14:50:00Z"
                     else "2026-11-16T09:59:00Z",
        "recorded_at": received,
        "event_start_time": "2026-11-17T00:00:00Z",
        "model_probability": None,
        "certified_prediction": False,
    }
    row.update(changes)
    return row


class NBAPropReadinessTests(unittest.TestCase):
    def test_no_provider_archive_is_reported_and_not_a_bet(self):
        r = inspect_nba_prop_capture([], now=NOW)
        self.assertEqual(r["primary_source_blocker"],
                         "NO_ARCHIVED_NBA_PLAYER_PROP_SOURCE_ROWS")
        self.assertEqual(r["next_nominal_scheduled_collector_utc"],
                         "2026-11-16T16:00:00+00:00")
        self.assertEqual(r["provider_calls_made_by_this_report"], 0)
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertFalse(r["champion_001_modified"])
        with self.assertRaisesRegex(ValueError, "timezone_aware"):
            inspect_nba_prop_capture([], now=datetime(2026,11,16,15))

    def test_stale_provider_price_is_not_fresh(self):
        stale = prop(received="2026-11-16T10:00:00Z")
        r = inspect_nba_prop_capture([stale], now=NOW, archive_run_ids=[123])
        self.assertEqual(r["primary_source_blocker"], "TODAYS_NBA_PROP_QUOTES_STALE")
        self.assertEqual(r["today_unstarted_game_valid_prop_rows"], 1)
        self.assertEqual(r["today_unstarted_game_recent_prop_rows"], 0)
        self.assertEqual(r["today_unstarted_game_stale_prop_rows"], 1)
        self.assertEqual(r["archive_run_ids"], [123])

    def test_same_line_both_sides_is_research_only_not_certified(self):
        r = inspect_nba_prop_capture([prop("over"), prop("under")], now=NOW)
        self.assertEqual(r["today_fresh_two_sided_exact_line_research_markets"],1)
        self.assertEqual(r["primary_source_blocker"],
                         "RESEARCH_PRICES_ONLY_MISSING_INDEPENDENT_MODEL_ROSTER_AND_CHECKOUT")
        self.assertFalse(r["direct_draftkings_checkout_price_verified"])
        self.assertFalse(r["independently_verified_native_champion_player_prop_probability"])
        self.assertFalse(r["eligible_for_ev_certification"])
        self.assertIn("All remain HOLD", render_nba_prop_capture(r))

    def test_only_one_side_and_bad_identity_are_distinguished(self):
        single = inspect_nba_prop_capture([prop()], now=NOW)
        self.assertEqual(single["primary_source_blocker"],
                         "NO_FRESH_TWO_SIDED_SAME_LINE_NBA_PROP_MARKETS")
        bad = inspect_nba_prop_capture([prop(player_name=None)], now=NOW)
        self.assertEqual(bad["primary_source_blocker"],
                         "NO_VALID_EXACT_NBA_PLAYER_IDENTITY_AND_QUOTES")
        self.assertIn("missing_exact_event_player_stat_identity",
                      bad["rejected_original_prop_rows_by_reason"])

    def test_other_leagues_and_started_events_are_not_promoted(self):
        past = prop(event_start_time="2026-11-16T14:57:00Z",
                    timestamp="2026-11-16T14:49:00Z")
        result = inspect_nba_prop_capture([dict(prop(),league="nfl"),past], now=NOW)
        self.assertEqual(result["nba_prop_archived_source_rows"],1)
        self.assertEqual(result["today_unstarted_game_valid_prop_rows"],0)

    def test_source_schedule_matches_actual_github_collection_cron(self):
        yaml = Path(".github/workflows/collect-sharpapi.yml").read_text()
        self.assertIn("- cron: '0 16,20,23 * * *'",yaml)

    def test_run_sharp_persists_reason_without_betting(self):
        with tempfile.TemporaryDirectory() as root:
            report = execute("run_sharp",now=NOW,sharp_rows=[prop("over")],
                             output_dir=root)
            p=Path(root)/"NBA_PROP_CAPTURE_READINESS.json"
            self.assertTrue(p.exists())
            d=json.loads(p.read_text())
            self.assertEqual(d["primary_source_blocker"],
                             "NO_FRESH_TWO_SIDED_SAME_LINE_NBA_PROP_MARKETS")
            self.assertIn("Next nominal", (Path(root)/
                "NBA_PROP_CAPTURE_READINESS.md").read_text())
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual(report["certified_positive_ev_bets"],0)


if __name__ == "__main__":
    unittest.main()
