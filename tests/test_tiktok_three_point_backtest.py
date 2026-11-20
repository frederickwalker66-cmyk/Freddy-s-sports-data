import unittest
from research.tiktok_three_point_backtest import backtest

def row(**kw):
    r=dict(game_id="g1",player="Test Player",opponent="Test Opponent",
        tipoff_utc="2026-11-20T23:00:00Z",observed_at_utc="2026-11-20T20:00:00Z",
        line="1.5",actual_3pm="2",last5_hits="5",last10_hits="9",
        last5_games="5",last10_games="10",opponent_3pm_allowed_rank="3",
        player_3pm_rank="4",minutes_verified="true",injury_verified="true",
        odds_american="-150",odds_timestamp="2026-11-20T20:00:00Z",
        source="test_fixture",native_probability="")
    r.update(kw)
    return r

class BacktestTests(unittest.TestCase):
    def test_valid_pregame_record_grades(self):
        report=backtest([row()])
        self.assertEqual(report["graded_rows"],1)
        self.assertEqual(report["eligible_wins"],1)
        self.assertEqual(report["certified_bets"],0)
        self.assertEqual(report["eligible_with_timestamped_odds"],1)
        self.assertEqual(report["eligible_with_native_model_probability"],0)

    def test_post_tip_observation_quarantined(self):
        report=backtest([row(observed_at_utc="2026-11-20T23:01:00Z")])
        self.assertEqual(report["graded_rows"],0)
        self.assertEqual(report["quarantined_rows"],1)

    def test_post_tip_quote_quarantined(self):
        report=backtest([row(odds_timestamp="2026-11-20T23:01:00Z")])
        self.assertEqual(report["quarantined_rows"],1)

    def test_missing_features_do_not_qualify(self):
        report=backtest([row(opponent_3pm_allowed_rank="")])
        self.assertEqual(report["graded_rows"],1)
        self.assertEqual(report["strategy_eligible_rows"],0)

    def test_duplicate_is_quarantined(self):
        report=backtest([row(),row()])
        self.assertEqual(report["graded_rows"],1)
        self.assertEqual(report["quarantined_rows"],1)

    def test_confidence_interval(self):
        report=backtest([row()])
        lo,hi=report["eligible_hit_rate_wilson_95_interval"]
        self.assertLess(lo,1)
        self.assertEqual(hi,1)
        self.assertEqual(report["eligible_losses"],0)

    def test_unstamped_odds_quarantined(self):
        report=backtest([row(odds_timestamp="")])
        self.assertEqual(report["quarantined_rows"],1)

    def test_empty_dataset_is_not_90_percent(self):
        report=backtest([])
        self.assertIsNone(report["eligible_empirical_hit_rate"])

if __name__=="__main__":
    unittest.main()
