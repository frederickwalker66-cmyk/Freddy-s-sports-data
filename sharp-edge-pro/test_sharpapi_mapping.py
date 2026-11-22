import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sharpapi_mapping import assess_sharpapi_row

NOW = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)

def row():
    return {"market_id":"m", "event_id":"e", "sportsbook":"draftkings",
            "selection":"home", "odds_decimal":1.91,
            "price_updated_at":(NOW-timedelta(seconds=20)).isoformat(),
            "event_start_time":(NOW+timedelta(hours=1)).isoformat(),
            "is_live":False, "is_active":True,
            "is_stale_pregame_price":False, "is_player_prop":False}

class SharpAPIMappingTests(unittest.TestCase):
    def test_complete_nonplayer_market_research_only(self):
        result = assess_sharpapi_row(row(), NOW)
        self.assertEqual(result["data_quality"], "PASS")
        self.assertEqual(result["certification"], "HOLD")

    def test_live_market_holds(self):
        r=row(); r["is_live"]=True
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_missing_live_flag_holds(self):
        r=row(); del r["is_live"]
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_inactive_market_holds(self):
        r=row(); r["is_active"]=False
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_stale_flag_holds(self):
        r=row(); r["is_stale_pregame_price"]=True
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_missing_stale_flag_holds(self):
        r=row(); del r["is_stale_pregame_price"]
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_player_prop_holds(self):
        r=row(); r["is_player_prop"]=True
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_missing_price_holds(self):
        r=row(); del r["odds_decimal"]
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_stale_timestamp_holds(self):
        r=row(); r["price_updated_at"]=(NOW-timedelta(minutes=3)).isoformat()
        self.assertEqual(assess_sharpapi_row(r,NOW)["data_quality"],"HOLD")

    def test_nonobject_holds(self):
        self.assertEqual(assess_sharpapi_row(None,NOW)["data_quality"],"HOLD")

if __name__ == "__main__":
    unittest.main()
