import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("market_quality", Path(__file__).with_name("market_quality.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)

def good():
    return dict(market_id="m1", event_id="e1", sportsbook="draftkings",
                selection="home", decimal_odds=1.91,
                observed_at=(NOW - timedelta(seconds=30)).isoformat(),
                start_time=(NOW + timedelta(hours=1)).isoformat())

class MarketQualityTests(unittest.TestCase):
    def test_valid_research_market_is_never_take(self):
        result = module.certification_status(good(), now=NOW)
        self.assertEqual(result["data_quality"], "PASS")
        self.assertEqual(result["certification"], "HOLD")

    def test_missing_market_id(self):
        m = good()
        del m["market_id"]
        self.assertIn("missing_market_id", module.validate_market(m, NOW)[1])

    def test_wrong_sportsbook(self):
        m = good()
        m["sportsbook"] = "other"
        self.assertIn("sportsbook_unverified", module.validate_market(m, NOW)[1])

    def test_null_sportsbook_does_not_crash(self):
        m = good()
        m["sportsbook"] = None
        self.assertFalse(module.validate_market(m, NOW)[0])

    def test_invalid_price(self):
        m = good()
        m["decimal_odds"] = True
        self.assertIn("invalid_decimal_odds", module.validate_market(m, NOW)[1])

    def test_stale_quote(self):
        m = good()
        m["observed_at"] = (NOW - timedelta(seconds=121)).isoformat()
        self.assertIn("stale_or_future_quote", module.validate_market(m, NOW)[1])

    def test_future_quote(self):
        m = good()
        m["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
        self.assertIn("stale_or_future_quote", module.validate_market(m, NOW)[1])

    def test_event_started(self):
        m = good()
        m["start_time"] = NOW.isoformat()
        self.assertIn("event_not_confirmed_pregame", module.validate_market(m, NOW)[1])

    def test_naive_timestamp(self):
        m = good()
        m["observed_at"] = "2026-11-22T15:00:00"
        self.assertIn("invalid_observation_time", module.validate_market(m, NOW)[1])

    def test_player_team_missing(self):
        m = good()
        m["player_id"] = "p1"
        self.assertIn("player_team_unverified", module.validate_market(m, NOW)[1])

    def test_non_object_fails(self):
        self.assertFalse(module.validate_market([], NOW)[0])

if __name__ == "__main__":
    unittest.main()
