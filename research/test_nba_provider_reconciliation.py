"""Offline regression tests for NBA provider identity and HOLD gates."""
import unittest
from research.nba_provider_event_reconciliation import reconcile
from research.nba_provider_snapshot_validation import validate

FORECAST={"forecasts":[{"event_id":"401","home_team_espn_id":"10","away_team_espn_id":"20",
"start_utc":"2026-11-25T00:00:00+00:00"}]}
ROW={"provider":"test-feed","provider_event_id":"book-123","espn_event_id":"401",
"event_start_utc":"2026-11-25T00:00:00Z","observed_at_utc":"2026-11-24T23:00:00Z",
"home_team_id":"local-home","away_team_id":"local-away",
"home_team_espn_id":"10","away_team_espn_id":"20",
"sportsbook":"DraftKings","market":"moneyline","selection":"home","american_odds":-110}

class ProviderTests(unittest.TestCase):
    def test_matching_event_still_not_certified(self):
        data=validate({"records":[ROW]},"odds")
        result=reconcile(FORECAST,data)
        self.assertEqual(result["matched_count"],1)
        self.assertFalse(result["certified"])
        self.assertEqual(result["decision"],"HOLD")
    def test_wrong_team_rejected(self):
        row=dict(ROW,home_team_espn_id="99")
        result=reconcile(FORECAST,validate({"records":[row]},"odds"))
        self.assertEqual(result["matched_count"],0)
        self.assertEqual(result["rejected_count"],1)
    def test_missing_crosswalk_rejected(self):
        row=dict(ROW);row.pop("espn_event_id")
        result=reconcile(FORECAST,validate({"records":[row]},"odds"))
        self.assertEqual(result["matched_count"],0)
    def test_started_snapshot_rejected(self):
        row=dict(ROW,observed_at_utc="2026-11-25T00:01:00Z")
        with self.assertRaises(ValueError):
            validate({"records":[row]},"odds")
    def test_wrong_start_rejected(self):
        row=dict(ROW,event_start_utc="2026-11-25T01:00:00Z")
        result=reconcile(FORECAST,validate({"records":[row]},"odds"))
        self.assertEqual(result["matched_count"],0)
    def test_legacy_forecast_does_not_match(self):
        result=reconcile({"forecasts":[{"event_id":"401"}]},validate({"records":[ROW]},"odds"))
        self.assertEqual(result["matched_count"],0)

if __name__=="__main__":unittest.main()
