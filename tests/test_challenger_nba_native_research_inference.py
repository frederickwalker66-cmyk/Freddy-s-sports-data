import unittest
from research.challenger_nba_native_research_inference import infer

class InferenceGateTests(unittest.TestCase):
    def test_missing_model_rejected(self):
        with self.assertRaises(ValueError):
            infer({}, {"event_id":"123"})
    def test_unverified_model_rejected(self):
        with self.assertRaises(ValueError):
            infer({"version":"fake","lane":"Challenger-001"}, {"event_id":"123"})
    def test_champion_not_accepted_as_challenger(self):
        with self.assertRaises(ValueError):
            infer({"version":"fake","lane":"Champion-001"}, {"event_id":"123"})

if __name__ == "__main__":
    unittest.main()
