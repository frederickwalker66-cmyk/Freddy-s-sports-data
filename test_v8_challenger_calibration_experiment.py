import unittest
from datetime import datetime, timedelta, timezone
from v8_challenger_calibration_experiment import evaluate

def rows(n):
    return [{"espn_event_id":str(i),
             "record_type":"v8_retrospective_NBA_Elo_event_replay_only",
             "event_start_utc":(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(),
             "retrospective_simulated_home_win_probability":.9,
             "published_score_home_won_research_label":i%2} for i in range(n)]

class CalibrationTests(unittest.TestCase):
    def test_insufficient(self):
        self.assertEqual(evaluate(rows(349))["status"],"HOLD")
    def test_holdout(self):
        result=evaluate(rows(350))
        self.assertEqual(result["holdout_games"],50)
        self.assertEqual(result["calibration_games"],200)
        self.assertTrue(result["improved_brier_and_log_loss"])
        self.assertEqual(result["certified_predictions"],0)
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            evaluate(rows(1)*2)

if __name__=="__main__":
    unittest.main()
