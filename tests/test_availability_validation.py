"""Fictional player props and manually reviewed status fixtures."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from availability_validation import check_availability, load_availability
from challenger_audit import validate

EVENTS = {"game-1": {"league": "nba", "home_team": "Home", "away_team": "Away",
                     "start_utc": "2026-10-28T21:00:00Z", "source_url": "https://www.nba.com"}}

def quote(**kw):
    d = {"record_type": "pregame_odds_observation", "sportsbook": "draftkings",
         "certified_prediction": False, "model_probability": None,
         "league": "nba", "event_id": "game-1", "home_team": "Home", "away_team": "Away",
         "is_main_line": True, "is_alternate_line": False, "is_player_prop": True,
         "market_type": "player_points", "selection_type": "over", "selection": "Over",
         "odds_american": -110, "odds_decimal": 1.909, "line": 22.5,
         "player_id": "dk-7", "player_name": "Example Player",
         "timestamp": "2026-10-28T19:59:00Z",
         "recorded_at": "2026-10-28T20:00:00Z",
         "event_start_time": "2026-10-28T21:00:00Z"}
    d.update(kw)
    return d

def status(**kw):
    d = {"league": "nba", "provider_player_id": "dk-7", "player_name": "Example Player",
         "team": "Away", "event_id": "game-1", "injury_status": "available",
         "lineup_status": "confirmed_active",
         "verified_at_utc": "2026-10-28T19:40:00Z",
         "source_url": "https://official.nba.com/nba-injury-report-2026-27-season/"}
    d.update(kw)
    return d

def validated(**kw):
    return {("nba", "dk-7", "game-1"): status(**kw)}

class GameDayTests(unittest.TestCase):
    def test_no_manifest_quarantines(self):
        self.assertIn("game_day_status_not_verified", check_availability(quote(), {}))
        self.assertEqual(load_availability(None), {})

    def test_game_day_availability_can_pass_with_verified_roster(self):
        rosters = {("nba", "dk-7"): {
            "player_name": "Example Player", "team": "Away", "status": "active",
            "verified_at_utc": "2026-10-28T19:40:00Z",
            "source_url": "https://www.nba.com"}}
        self.assertEqual(validate(quote(), EVENTS, rosters, validated()), [])

    def test_out_and_questionable_fail(self):
        for value in ("out", "questionable", "probable", "doubtful", "unknown"):
            with self.subTest(value=value):
                self.assertIn("player_injury_status_not_cleared", check_availability(quote(), validated(injury_status=value)))

    def test_no_lineup_confirmation_fails(self):
        self.assertIn("game_day_lineup_or_active_status_unconfirmed", check_availability(
            quote(), validated(lineup_status="unconfirmed")))

    def test_old_or_future_status_fails(self):
        for value in ("2026-10-28T16:00:00Z", "2026-10-28T20:15:00Z"):
            self.assertIn("game_day_report_stale_or_future", check_availability(
                quote(), validated(verified_at_utc=value)))

    def test_wrong_event_fails(self):
        self.assertIn("game_day_status_not_verified", check_availability(
            quote(event_id="different-game"), validated()))

    def test_traded_player_team_fails(self):
        self.assertIn("game_day_team_mismatch", check_availability(
            quote(), validated(team="Other Team")))

    def test_name_mismatch_fails(self):
        self.assertIn("game_day_player_mismatch", check_availability(
            quote(), validated(player_name="Other Player")))

    def test_nonofficial_source_manifest_rejected(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "availability.json"
            p.write_text(json.dumps({"players": [status(source_url="https://example.com")]}))
            with self.assertRaises(ValueError):
                load_availability(str(p))

    def test_duplicate_status_manifest_rejected(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "availability.json"
            p.write_text(json.dumps({"players": [status(), status()]}))
            with self.assertRaises(ValueError):
                load_availability(str(p))

    def test_manifest_valid_and_loaded(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "availability.json"
            p.write_text(json.dumps({"players": [status()]}))
            result = load_availability(str(p))
            self.assertIn(("nba", "dk-7", "game-1"), result)

if __name__ == "__main__":
    unittest.main()
