"""Fictional validation fixtures; no external odds or model outputs."""
from datetime import datetime, timezone, timedelta
import unittest
from collector import normalize_quote, parse_time

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


if __name__ == "__main__":
    unittest.main()
