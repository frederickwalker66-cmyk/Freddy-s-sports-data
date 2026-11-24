import unittest
from research.portfolio_release_guard import audit_portfolio

class PortfolioGuardTests(unittest.TestCase):
    def test_five_shared_of_seven(self):
        def leg(i):
            return {"event_id": str(i), "market_type": "spread", "selection_id": str(i)}
        result = audit_portfolio([{"legs": [leg(i) for i in range(7)]}, {"legs": [leg(i) for i in [0,1,2,3,4,7,8]]}])
        self.assertEqual(result["overlaps"][0]["shared_legs"], 5)
        self.assertEqual(result["repeated_selection_count"], 5)
        self.assertFalse(result["actionable"])
    def test_same_game_and_duplicate(self):
        leg = {"event_id": "a", "market_type": "spread", "selection_id": "b"}
        result = audit_portfolio([{"legs": [leg, leg]}])
        self.assertIn("DUPLICATE_LEG", result["reasons"])
        self.assertIn("SAME_GAME_JOINT_PROBABILITY_NOT_AUTHENTICATED", result["reasons"])
    def test_missing(self):
        self.assertEqual(audit_portfolio(None)["status"], "HOLD")
