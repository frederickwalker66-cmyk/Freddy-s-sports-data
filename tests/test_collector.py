"""Fictional validation fixtures; no external odds or model outputs."""
from datetime import datetime, timezone, timedelta
import unittest
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
from collector import (normalize_quote, parse_time, LEAGUES, SUPPORTED_LEAGUES,
                       collect, main)

NOW = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)


def example(**updates):
    row = {"id": "example", "sportsbook": "draftkings", "sport": "basketball", "league": "nba",
           "event_id": "fixture-game", "home_team": "Sample Home", "away_team": "Sample Away",
           "market_type": "player_points", "selection": "Over", "player_name": "Example Player",
           "line": 22.5, "odds_american": -110, "odds_decimal": 1.909,
           "event_start_time": "2026-10-28T21:00:00Z", "timestamp": "2026-10-28T19:58:00Z",
           "is_live": False}
    row.update(updates)
    return row


class CollectorTests(unittest.TestCase):
    def test_valid_pregame_quote(self):
        result = normalize_quote(example(), NOW)
        self.assertEqual(result["odds_american"], -110)
        self.assertFalse(result["certified_prediction"])
        self.assertIsNone(result["model_probability"])
        self.assertEqual(result["source_age_seconds"], 120)

    def test_live_rejected(self):
        self.assertIsNone(normalize_quote(example(is_live=True), NOW))

    def test_game_already_started_rejected(self):
        self.assertIsNone(normalize_quote(example(event_start_time="2026-10-28T19:30:00Z"), NOW))

    def test_old_quote_rejected(self):
        self.assertIsNone(normalize_quote(example(timestamp="2026-10-28T19:20:00Z"), NOW))

    def test_future_quote_rejected(self):
        self.assertIsNone(normalize_quote(example(timestamp="2026-10-28T20:01:00Z"), NOW))

    def test_non_draftkings_rejected(self):
        self.assertIsNone(normalize_quote(example(sportsbook="fanduel"), NOW))

    def test_market_odds_not_model_forecast(self):
        self.assertNotIn("estimated_ev", normalize_quote(example(), NOW))

    def test_missing_event_time_rejected(self):
        self.assertIsNone(normalize_quote(example(event_start_time=None), NOW))

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            parse_time("2026-10-28T20:00:00")

    def test_missing_selection_rejected(self):
        self.assertIsNone(normalize_quote(example(selection=None), NOW))

    def test_ncaaf_is_opt_in_and_scheduled_leagues_unchanged(self):
        self.assertEqual(LEAGUES, ("nba", "nfl", "mlb"))
        self.assertIn("ncaaf", SUPPORTED_LEAGUES)
        self.assertIn("nhl", SUPPORTED_LEAGUES)
        self.assertIn("mls", SUPPORTED_LEAGUES)
        self.assertIn("uefa_champions_league", SUPPORTED_LEAGUES)

    def test_ncaaf_dry_run_never_reads_key_or_calls_provider(self):
        buf = io.StringIO()
        with (patch("sys.argv", ["collector.py", "--dry-run", "--leagues",
                                "ncaaf", "--max-pages", "2"]),
              patch.dict("os.environ", {}, clear=True),
              patch("collector.urlopen", side_effect=AssertionError("network called")),
              redirect_stdout(buf)):
            self.assertEqual(main(), 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["leagues"], ["ncaaf"])
        self.assertEqual(result["max_possible_provider_requests"], 4)
        self.assertEqual(result["network_calls"], 0)
        self.assertTrue(result["ncaaf_opted_in"])
        self.assertEqual(result["certified_bets"], 0)

    def test_synthetic_ncaaf_collection_keeps_provenance_unverified(self):
        row = example(league="ncaaf", sport="football",
                      event_start_time="2026-10-28T21:00:00Z",
                      timestamp="2026-10-28T19:59:00Z")
        page = {"data": [row], "pagination": {"has_more": False}}
        with (patch("collector.get_page", return_value=page) as endpoint,
              patch("collector.now_utc", return_value=NOW),
              patch("collector.time.sleep") as sleeper):
            rows, summary, requests = collect(
                "test-secret", leagues=("ncaaf",), max_pages=1)
        self.assertEqual(requests, 2)
        self.assertEqual(endpoint.call_count, 2)
        sleeper.assert_called_once()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["league"], "ncaaf")
        self.assertEqual(rows[0]["source"], "sharpapi_rest")
        self.assertIsNone(rows[0]["model_probability"])
        self.assertFalse(rows[0]["certified_prediction"])
        self.assertEqual(summary[0]["league"], "ncaaf")


if __name__ == "__main__":
    unittest.main()
