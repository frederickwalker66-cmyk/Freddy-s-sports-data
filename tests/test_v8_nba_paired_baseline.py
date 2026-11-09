"""NBA paired research baseline must not leak a result before presumed maturity."""
import unittest
from datetime import datetime, timedelta, timezone

from v8_nba_paired_baseline import compare, rolling_home_prior


def games(n):
    first=datetime(2026,1,12,23,tzinfo=timezone.utc)
    return [
        (first+timedelta(days=i//4,minutes=i%4),str(1000000+i),
         str(i%10+1),str(i%10+20), 0 if i%3==0 else 1)
        for i in range(n)
    ]


class RollingPriorTests(unittest.TestCase):
    def test_first_event_outcome_never_becomes_next_event_early(self):
        t=datetime(2026,1,12,18,tzinfo=timezone.utc)
        data=[
            (t,"1","H","A",1),
            (t,"2","B","C",1),
            (t+timedelta(hours=2),"3","D","E",0),
            (t+timedelta(hours=48),"4","F","G",1),
        ]
        result=rolling_home_prior(data)
        self.assertEqual(result[:3],[.5,.5,.5])
        self.assertAlmostEqual(result[3],.75)

    def test_empty_and_bad_embargo(self):
        self.assertEqual(rolling_home_prior([]),[])
        with self.assertRaisesRegex(ValueError,"invalid_minimum_result_embargo"):
            rolling_home_prior([],embargo_hours=2)

    def test_120_events_yield_paired_scores_and_bootstrap_but_no_certification(self):
        rows=games(120)
        elo=[(.58,y,t.isoformat()) for t,eid,h,a,y in rows]
        summary,paired=compare(rows,elo)
        self.assertEqual(len(paired),120)
        self.assertTrue(summary["scores_available"])
        self.assertEqual(summary["later_reconstructed_evaluation_events"],40)
        self.assertGreaterEqual(summary["bootstrap_days"],5)
        self.assertEqual(summary["bootstrap_iterations"],1000)
        lo,hi=summary["approximate_paired_day_bootstrap_brier_improvement_95pct_CI"]
        self.assertLessEqual(lo,hi)
        self.assertAlmostEqual(
            summary["elo_minus_rolling_baseline_brier_improvement"],
            summary["rolling_home_win_baseline_brier"]-summary["elo_brier_unrounded"],
            places=8,
        )
        self.assertEqual(summary["certified_predictions"],0)
        self.assertFalse(summary["bet_ready"])
        self.assertFalse(summary["independently_certified_model"])
        self.assertTrue(all(item["historical_forecast_actually_recorded_before_tipoff"] is False
                            for item in paired))

    def test_small_sample_no_measured_skill(self):
        rows=games(11)
        elo=[(.58,y,t.isoformat()) for t,eid,h,a,y in rows]
        summary,paired=compare(rows,elo)
        self.assertFalse(summary["scores_available"])
        self.assertIsNone(summary["elo_minus_rolling_baseline_brier_improvement"])
        self.assertIsNone(summary["approximate_paired_day_bootstrap_brier_improvement_95pct_CI"])
        self.assertEqual(summary["certified_predictions"],0)

    def test_different_order_or_label_fails(self):
        rows=games(3)
        elo=[(.5,y,t.isoformat()) for t,eid,h,a,y in rows]
        elo[0]=(.5,1-rows[0][-1],rows[0][0].isoformat())
        with self.assertRaisesRegex(ValueError,"forecast_alignment_failure"):
            compare(rows,elo)
        with self.assertRaisesRegex(ValueError,"NBA_elo_replay_length_mismatch"):
            compare(rows,[])

    def test_bad_label_fails(self):
        t=datetime(2026,1,12,18,tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError,"only_binary_NBA_final"):
            rolling_home_prior([(t,"5","H","A",None)])


if __name__ == "__main__":
    unittest.main()
