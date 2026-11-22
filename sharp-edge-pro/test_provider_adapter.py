import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("provider_adapter", HERE / "provider_adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
NOW = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
MAP = {x: x for x in adapter.REQUIRED}

def row():
    return dict(market_id="m", event_id="e", sportsbook="draftkings",
                selection="home", decimal_odds=1.9,
                observed_at=(NOW-timedelta(seconds=20)).isoformat(),
                start_time=(NOW+timedelta(hours=2)).isoformat())

class ProviderAdapterTests(unittest.TestCase):
    def test_explicit_mapping_is_research_pass_only(self):
        self.assertEqual(adapter.assess_record(row(), MAP, NOW),
                         {"data_quality": "PASS", "certification": "HOLD",
                          "reasons": ["model_probability_and_injury_gates_not_verified"]})

    def test_missing_mapping_holds(self):
        self.assertEqual(adapter.assess_record(row(), {}, NOW)["data_quality"], "HOLD")

    def test_missing_provider_field_holds(self):
        r = row()
        del r["event_id"]
        self.assertEqual(adapter.assess_record(r, MAP, NOW)["data_quality"], "HOLD")

    def test_unrecognized_raw_type_holds(self):
        self.assertEqual(adapter.assess_record([], MAP, NOW)["data_quality"], "HOLD")

    def test_stale_market_holds(self):
        r = row()
        r["observed_at"] = (NOW-timedelta(minutes=3)).isoformat()
        self.assertEqual(adapter.assess_record(r, MAP, NOW)["data_quality"], "HOLD")

if __name__ == "__main__":
    unittest.main()
