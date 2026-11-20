import unittest
from datetime import datetime, timezone
from scripts.live_certified_predictions import run

class LiveCertificationTests(unittest.TestCase):
    def test_empty_feed_has_no_fake_predictions(self):
        result = run([], now=datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(result["certified_take_count"], 0)
        self.assertTrue(result["no_certified_picks"])

    def test_unsigned_candidate_holds(self):
        result = run([{"selection": "NBA OVER"}])
        self.assertEqual(result["decisions"][0]["decision"], "HOLD")
        self.assertEqual(result["hold_count"], 1)

    def test_reject_unbounded_input(self):
        with self.assertRaises(ValueError):
            run([{}] * 501)

if __name__ == "__main__":
    unittest.main()
