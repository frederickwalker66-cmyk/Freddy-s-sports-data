"""Safety and behavior tests for Challenger-002. Run: python -m unittest discover -s challenger_002 -p 'test_*.py'"""
import datetime as dt
import tempfile
import json
import unittest
from pathlib import Path
from nba_moneyline import load, fit, sigmoid, vector

class SafetyTests(unittest.TestCase):
    def test_probability_bounds(self):
        self.assertGreater(sigmoid(-100), 0)
        self.assertLess(sigmoid(100), 1)
        self.assertEqual(len(vector([0.5,0.5,2,2])),5)

    def test_reject_post_tipoff_capture(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"rows.jsonl"
            path.write_text(json.dumps(dict(event_id="a", tipoff_utc="2026-11-24T19:00:00Z",
                captured_utc="2026-11-24T20:00:00Z",source_id="test",
                home_win_pct_pre=0.5,away_win_pct_pre=0.5,home_rest_days=1,away_rest_days=1,
                home_win=1))+"\n")
            with self.assertRaisesRegex(ValueError,"not pregame"):
                load(path,True)

    def test_reject_duplicate_events(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"rows.jsonl"
            row=dict(event_id="a",tipoff_utc="2026-11-24T19:00:00Z",
                captured_utc="2026-11-24T18:00:00Z",source_id="test",
                home_win_pct_pre=0.5,away_win_pct_pre=0.5,home_rest_days=1,away_rest_days=1,
                home_win=1)
            path.write_text(json.dumps(row)+"\n"+json.dumps(row)+"\n")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                load(path,True)

if __name__=="__main__":
    unittest.main()
