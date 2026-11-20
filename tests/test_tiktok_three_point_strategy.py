import unittest
from research.tiktok_three_point_strategy import ThreePointCandidate, evaluate, implied_probability, parlay_independent_probability

class ThreePointStrategyTests(unittest.TestCase):
    def candidate(self, **changes):
        args=dict(player="Example",opponent="Opponent",line=1.5,last5_hits=5,last10_hits=9,
                  last5_games=5,last10_games=10,opponent_3pm_allowed_rank=4,
                  player_3pm_rank=7,minutes_verified=True,injury_verified=True)
        args.update(changes)
        return ThreePointCandidate(**args)

    def test_no_native_probability_holds_even_with_90_percent_history(self):
        self.assertEqual(evaluate(self.candidate())["decision"], "HOLD")

    def test_missing_price_holds(self):
        self.assertEqual(evaluate(self.candidate(native_probability=.8))["decision"], "HOLD")

    def test_positive_ev_research_only(self):
        result=evaluate(self.candidate(native_probability=.8,odds_american=-150,
                    odds_timestamp="2026-11-20T18:00:00-05:00",source="verified"))
        self.assertEqual(result["decision"], "TAKE")
        self.assertEqual(result["certification"], "UNCERTIFIED_RESEARCH_ONLY")

    def test_missing_defense_rank_holds(self):
        result=evaluate(self.candidate(opponent_3pm_allowed_rank=None,native_probability=.8,
                    odds_american=-150,odds_timestamp="2026-11-20T18:00:00-05:00",source="verified"))
        self.assertEqual(result["decision"], "HOLD")

    def test_90_percent_not_forecast(self):
        result=evaluate(self.candidate(last10_hits=9))
        self.assertTrue(result["historical_90"])
        self.assertIsNone(result["native_probability"])

    def test_implied_probability(self):
        self.assertAlmostEqual(implied_probability(-210),210/310)
        self.assertAlmostEqual(implied_probability(100),.5)

    def test_invalid_counts(self):
        with self.assertRaises(ValueError):
            evaluate(self.candidate(last10_hits=11))

    def test_parlay_illustrative(self):
        self.assertAlmostEqual(parlay_independent_probability([.9,.9,.9]),.729)
        self.assertIsNone(parlay_independent_probability([.9,None]))

if __name__ == "__main__":
    unittest.main()
