"""Tests for prospective Elo safety gates and real historical update math."""
import unittest
from datetime import datetime, timezone
from research.nba_prospective_elo import forecast

NOW=datetime(2026,11,23,17,0,tzinfo=timezone.utc)
def event():
    return {"event_id":"future-100","home_team_espn_id":"1","away_team_espn_id":"2",
            "start_utc":"2026-11-24T01:00:00Z","source_url":"https://site.api.espn.com/example"}

class ProspectiveEloTests(unittest.TestCase):
    def test_empty_history_is_uncalibrated_baseline(self):
        result=forecast([], [event()], now=NOW)
        self.assertGreater(result["forecasts"][0]["research_probability_home_win"],0.5)
        self.assertEqual(result["certified_take_count"],0)
        self.assertEqual(result["forecasts"][0]["decision"],"HOLD")
        self.assertFalse(result["elo_calibrated"])
    def test_completed_event_rejected(self):
        game=event()
        game["start_utc"]="2026-11-23T16:00:00Z"
        with self.assertRaises(ValueError):
            forecast([], [game], now=NOW)
    def test_missing_source_rejected(self):
        game=event()
        game["source_url"]=""
        with self.assertRaises(ValueError):
            forecast([], [game], now=NOW)

if __name__=="__main__":
    unittest.main()
