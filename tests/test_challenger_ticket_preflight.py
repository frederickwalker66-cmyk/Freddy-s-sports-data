"""Fail-closed, fictional tests for Challenger slip preflight."""
import unittest
from challenger_ticket_preflight import (
    audit_slip, break_even_probability, grade_slip_results,
)


def leg(event="game-1", **overrides):
    d = {
        "event_id": event, "market_type": "moneyline", "selection": "Example Home",
        "odds_american": -110, "dk_quote_verified": True,
        "is_player_prop": False, "model_probability": None,
        "model_probability_verified": False,
    }
    d.update(overrides)
    return d


class ChallengerTicketPreflightTests(unittest.TestCase):
    def test_american_odds_break_even(self):
        self.assertAlmostEqual(break_even_probability(-150), 0.6)
        self.assertAlmostEqual(break_even_probability(200), 1/3)
        for invalid in (0, 99, -99, True, -110.0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    break_even_probability(invalid)

    def test_unverified_probability_cannot_create_ev(self):
        report = audit_slip([leg(model_probability=0.8)])
        self.assertEqual(report["decision"], "PASS")
        self.assertIsNone(report["legs"][0]["model_ev_per_unit_if_verified"])
        self.assertIn("independent_model_probability_unverified", report["blockers"])

    def test_prop_not_confirmed_active_is_blocked(self):
        report = audit_slip([leg(is_player_prop=True, availability_verified=False,
                                 market_type="player_points")])
        self.assertIn("player_availability_or_role_unverified", report["blockers"])

    def test_shared_game_requires_joint_probability(self):
        report = audit_slip([leg(), leg(selection="Example Player 15+", is_player_prop=True,
                                      availability_verified=True, market_type="player_points")],
                            quoted_parlay_odds=250, parlay_quote_verified=True)
        self.assertIn("game-1", report["same_event_ids"])
        self.assertIn("validated_joint_probability_missing", report["blockers"])
        self.assertIsNone(report["combined_model_ev_per_unit_if_verified"])

    def test_no_fabricated_sgp_payout(self):
        report = audit_slip([leg("g1"), leg("g2")])
        self.assertIsNone(report["combined_quote_break_even_probability"])
        self.assertIn("exact_parlay_price_missing", report["blockers"])

    def test_fully_evidenced_positive_ev_still_research_only(self):
        row = leg(model_probability=0.7, model_probability_verified=True)
        report = audit_slip([row], quoted_parlay_odds=-110,
                            parlay_quote_verified=True,
                            joint_probability=0.7, joint_probability_verified=True)
        self.assertGreater(report["combined_model_ev_per_unit_if_verified"], 0)
        self.assertFalse(report["bet_ready"])
        self.assertEqual(report["decision"], "RESEARCH_REVIEW_ONLY")
        self.assertFalse(report["champion_001_modified"])

    def test_unverified_parlay_quote_blocks(self):
        report = audit_slip([leg(model_probability=0.7, model_probability_verified=True)],
                            quoted_parlay_odds=-110, joint_probability=0.7,
                            joint_probability_verified=True)
        self.assertIn("parlay_checkout_quote_unverified", report["blockers"])
        self.assertIsNone(report["combined_model_ev_per_unit_if_verified"])

    def test_void_is_not_loss_or_model_forecast(self):
        result = grade_slip_results(["win", "win", "void", "loss"])
        self.assertEqual(result["preliminary_ticket_state"], "loss")
        self.assertEqual(result["settled_leg_hit_rate"], 2/3)
        self.assertFalse(result["final_payout_verified"])

    def test_void_only_needs_bookmaker_confirmation(self):
        result = grade_slip_results(["win", "void", "push"])
        self.assertEqual(result["preliminary_ticket_state"],
                         "requires_bookmaker_payout_confirmation")

    def test_invalid_probabilities_rejected(self):
        for p in (-0.1, 1.01, float("nan"), True):
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    audit_slip([leg(model_probability=p)])


if __name__ == "__main__":
    unittest.main()
