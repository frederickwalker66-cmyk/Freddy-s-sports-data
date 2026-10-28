"""Fictional sample data; these tests do not prove real rosters are current."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_audit import audit, validate
from roster_validation import load_rosters, check_player_roster

EVENTS = {"demo": {"event_id": "demo", "league": "nba",
                    "home_team": "Demo Home", "away_team": "Demo Away",
                    "start_utc": "2026-10-28T21:00:00Z",
                    "source_url": "https://www.nba.com"}}

def prop(**overrides):
    row = {
        "record_type": "pregame_odds_observation", "sportsbook": "draftkings",
        "certified_prediction": False, "model_probability": None,
        "event_id": "demo", "league": "nba",
        "home_team": "Demo Home", "away_team": "Demo Away",
        "market_type": "player_points", "selection": "Over",
        "selection_type": "over", "is_main_line": True,
        "is_alternate_line": False, "is_player_prop": True,
        "odds_american": -110, "odds_decimal": 1.909,
        "player_id": "provider-123", "player_name": "Example Athlete",
        "line": 21.5, "timestamp": "2026-10-28T19:59:00Z",
        "recorded_at": "2026-10-28T20:00:00Z",
        "event_start_time": "2026-10-28T21:00:00Z",
    }
    row.update(overrides)
    return row

def roster(**overrides):
    row = {"league": "nba", "provider_player_id": "provider-123",
           "official_player_id": "official-789", "player_name": "Example Athlete",
           "team": "Demo Away", "status": "active",
           "source_url": "https://www.nba.com/team/example",
           "verified_at_utc": "2026-10-28T19:30:00Z"}
    row.update(overrides)
    return row

class RosterTests(unittest.TestCase):
    def test_no_roster_manifest_quarantines_prop(self):
        self.assertEqual(load_rosters(None), {})
        self.assertIn("roster_not_independently_verified", validate(prop(), EVENTS))
        stage, quarantine, report = audit([prop()], EVENTS)
        self.assertEqual(len(stage), 0)
        self.assertEqual(len(quarantine), 1)
        self.assertFalse(report["roster_refresh_automated"])

    def test_properly_verified_roster_can_stage_research_only(self):
        rows = {("nba", "provider-123"): roster()}
        # Roster-only certification never clears an injury/lineup check.
        self.assertIn("game_day_status_not_verified", validate(prop(), EVENTS, rows))
        stage, quarantine, report = audit([prop()], EVENTS, rows)
        self.assertEqual((len(stage), len(quarantine)), (0, 1))
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_traded_or_wrong_team_quarantined(self):
        reasons = check_player_roster(prop(), {("nba", "provider-123"): roster(team="Other Team")})
        self.assertIn("roster_team_not_in_event", reasons)

    def test_inactive_or_injured_quarantined(self):
        self.assertIn("player_not_active_on_roster", check_player_roster(
            prop(), {("nba", "provider-123"): roster(status="injured")}))

    def test_wrong_name_quarantined(self):
        self.assertIn("roster_player_name_mismatch", check_player_roster(
            prop(), {("nba", "provider-123"): roster(player_name="Someone Else")}))

    def test_outdated_roster_quarantined(self):
        self.assertIn("roster_stale_or_future", check_player_roster(
            prop(), {("nba", "provider-123"): roster(verified_at_utc="2026-10-26T19:30:00Z")}))

    def test_future_roster_quarantined(self):
        self.assertIn("roster_stale_or_future", check_player_roster(
            prop(), {("nba", "provider-123"): roster(verified_at_utc="2026-10-29T19:30:00Z")}))

    def test_id_crosswalk_missing_quarantined(self):
        self.assertIn("roster_not_independently_verified", check_player_roster(
            prop(player_id="other-id"), {("nba", "provider-123"): roster()}))

    def test_manifest_rejects_unofficial_source(self):
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "rosters.json"
            filename.write_text(json.dumps({"players": [roster(source_url="https://example.com/not-official")]}))
            with self.assertRaises(ValueError):
                load_rosters(filename)

    def test_manifest_rejects_duplicate_player_id(self):
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "rosters.json"
            filename.write_text(json.dumps({"players": [roster(), roster(team="Demo Home")]}))
            with self.assertRaises(ValueError):
                load_rosters(filename)

    def test_manifest_loads_and_requires_review_time(self):
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "rosters.json"
            filename.write_text(json.dumps({"players": [roster()]}))
            self.assertIn(("nba", "provider-123"), load_rosters(filename))

if __name__ == "__main__":
    unittest.main()
