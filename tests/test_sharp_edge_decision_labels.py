import unittest
from research.sharp_edge_decision_labels import classify, label_board


class DecisionLabelTests(unittest.TestCase):
    def test_unverified_take_becomes_hold(self):
        self.assertEqual(classify({"decision": "TAKE"})["decision"], "HOLD")

    def test_pass_stays_pass(self):
        self.assertEqual(classify({"decision": "PASS"})["decision"], "PASS")

    def test_authenticated_certified_take(self):
        row = {"decision": "TAKE", "certified": True, "authenticated_source": True,
               "native_champion_probability_verified": True, "positive_ev_verified": True}
        self.assertEqual(classify(row)["decision"], "TAKE")

    def test_missing_any_certification_is_hold(self):
        row = {"decision": "TAKE", "certified": True, "authenticated_source": True,
               "native_champion_probability_verified": True, "positive_ev_verified": False}
        self.assertEqual(classify(row)["decision"], "HOLD")

    def test_board_has_explicit_labels(self):
        result = label_board([{"selection_id": "a"}, {"selection_id": "b", "decision": "PASS"}])
        self.assertEqual([r["decision"] for r in result], ["HOLD", "PASS"])
