import unittest
from research.champion_native_inference_diagnostics import diagnose

class NativeDiagnosticTests(unittest.TestCase):
    def test_missing_original_model_stays_hold(self):
        report = diagnose({})
        self.assertEqual(report["decision"], "HOLD")
        self.assertEqual(report["certified_take_predictions"], 0)
        self.assertEqual(report["native_probabilities_generated"], 0)
        self.assertFalse(report["inference_executed"])
        self.assertFalse(report["champion_001_modified"])
    def test_fake_hashes_do_not_unlock(self):
        report = diagnose({"FREDDY_CHAMPION_ARTIFACT": "missing.bin",
                           "FREDDY_CHAMPION_RUNNER": "missing.py",
                           "FREDDY_CHAMPION_SHA256": "a"*64,
                           "FREDDY_CHAMPION_RUNNER_SHA256": "b"*64})
        self.assertFalse(report["native_model"]["hash_verified"])
        self.assertEqual(report["decision"], "HOLD")

if __name__ == "__main__":
    unittest.main()
