"""Regression tests for the actual live-audit player-prop integration."""
import datetime as dt
import unittest
from challenger_audit import validate

class LiveAuditPropTests(unittest.TestCase):
    def test_no_roster_or_injury_manifest_quarantines_prop(self):
        now = dt.datetime.now(dt.timezone.utc)
        iso = lambda t: t.isoformat()
        row = {
            "sportsbook": "draftkings",
            "record_type": "pregame_odds_observation",
            "certified_prediction": False,
            "model_probability": None,
            "event_id": "e1",
            "market_type": "player_points",
            "selection": "over",
            "selection_type": "over",
            "is_main_line": True,
            "is_alternate_line": False,
            "odds_american": -110,
            "odds_decimal": 1 + 100/110,
            "league": "nba",
            "home_team": "Home",
            "away_team": "Away",
            "timestamp": iso(now),
            "recorded_at": iso(now),
            "event_start_time": iso(now + dt.timedelta(hours=2)),
            "is_player_prop": True,
            "player_name": "Example Player",
            "player_id": "p1",
            "line": 20.5,
        }
        events = {"e1": {"league":"nba", "home_team":"Home",
                         "away_team":"Away",
                         "start_utc":row["event_start_time"]}}
        reasons = validate(row, events, {}, {})
        self.assertIn("roster_not_independently_verified", reasons)
        self.assertIn("game_day_status_not_verified", reasons)
        self.assertIn("integrity_missing_team_id", reasons)

if __name__ == "__main__":
    unittest.main()
