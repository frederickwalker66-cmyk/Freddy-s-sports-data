import unittest
from v8_confidence_risk import screen, confidence_report

class ConfidenceRiskTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(screen(None, 2)["decision"], "HOLD")
        self.assertEqual(screen(float("nan"), 2)["decision"], "HOLD")
    def test_straight(self):
        self.assertEqual(screen(.74, 2)["decision"], "PASS")
        self.assertEqual(screen(.80, 1.2)["decision"], "PASS")
        self.assertTrue(screen(.80, 1.5)["research_threshold_met"])
        self.assertEqual(screen(.80, 1.5)["decision"], "HOLD")
    def test_parlay(self):
        self.assertEqual(screen(.49, 3, 5)["decision"], "PASS")
        self.assertEqual(screen(.60, 2, 5)["decision"], "HOLD")
    def test_no_certification(self):
        self.assertEqual(confidence_report()["certified_bets"], 0)

if __name__ == "__main__":
    unittest.main()
