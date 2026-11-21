import unittest
from edge_math import american_to_decimal,break_even_probability,expected_return_per_unit,evaluate

class EdgeMathTests(unittest.TestCase):
    def test_minus_110(self):
        self.assertAlmostEqual(break_even_probability(-110),110/210)
    def test_positive_odds(self):
        self.assertAlmostEqual(american_to_decimal(150),2.5)
    def test_ev(self):
        self.assertAlmostEqual(expected_return_per_unit(.57,-110),.57*(1+100/110)-1)
    def test_missing_forecast_holds(self):
        self.assertEqual(evaluate("Example",-110)["status"],"HOLD")
    def test_unverified_positive_ev_holds(self):
        self.assertEqual(evaluate("Example",-110,.65)["status"],"HOLD")
    def test_invalid_probability(self):
        with self.assertRaises(ValueError):
            expected_return_per_unit(1.2,-110)
    def test_fully_gated_negative_ev_passes(self):
        x=evaluate("Example",-110,.50,True,True,True,True,True)
        self.assertEqual(x["status"],"PASS")
    def test_fully_gated_positive_ev(self):
        x=evaluate("Example",-110,.57,True,True,True,True,True)
        self.assertEqual(x["status"],"TAKE")
if __name__=="__main__":
    unittest.main()
