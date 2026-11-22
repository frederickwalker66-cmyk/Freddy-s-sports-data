import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from research.challenger_prediction_bridge import bridge
class BridgeTests(unittest.TestCase):
    def test_native_projection_never_certified(self):
        now=datetime.now(timezone.utc)
        candidate={"event_id":"test-event","start_utc":(now+timedelta(hours=3)).isoformat(),
                   "odds_american":-110}
        projection={"model_version":"challenger-test","scored_at_utc":now.isoformat(),
                    "research_probability_home_win":0.61,"model_sha256":"a"*64}
        with patch("research.challenger_prediction_bridge.score_future_event",return_value=projection):
            result=bridge({},candidate,now)
        self.assertEqual(result["status"],"HOLD")
        self.assertFalse(result["certified"])
        self.assertAlmostEqual(result["model_probability"],0.61)
        self.assertFalse(result["independent_source_provenance_verified"])
        self.assertFalse(result["evidence_manifest_complete"])
        self.assertIn("exact_draftkings_market_verified", result["evidence_blockers"])
if __name__=="__main__":
    unittest.main()
