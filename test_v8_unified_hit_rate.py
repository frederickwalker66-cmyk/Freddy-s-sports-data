import unittest
from v8_unified_hit_rate import grade, historical, summarize

class HitRateTests(unittest.TestCase):
    def test_markets(self):
        r=dict(PTS=20, REB=8, AST=5, team_points=110, opponent_points=105)
        for market,side,line in [("PR","OVER",27.5),("PA","UNDER",25.5),
            ("RA","OVER",12.5),("PRA","OVER",32.5),("ML","TEAM",0),
            ("SPREAD","TEAM",-4.5),("TOTAL","UNDER",215.5),
            ("TEAM_TOTAL","OVER",109.5),("PTS","UNDER",20.5)]:
            self.assertEqual(grade(r,market,side,line),"WIN")
        self.assertEqual(grade(r,"SPREAD","TEAM",-5),"PUSH")
        self.assertEqual(grade(r,"SPREAD","TEAM",-6),"LOSS")
    def test_pushes(self):
        self.assertEqual(summarize(["WIN","LOSS","PUSH"])["hit_rate"],.5)
        self.assertIsNone(summarize(["PUSH"])["hit_rate"])
    def test_windows_and_cutoff(self):
        rows=[dict(subject_id="p",opponent_id="o" if i%2 else "x",
            game_id=str(i),season="2026",final=True,PTS=i,
            event_start_utc=f"2026-11-{i:02d}T00:00:00Z",
            settled_utc=f"2026-11-{i:02d}T03:00:00Z") for i in range(1,22)]
        args=dict(subject_id="p",opponent_id="o",season="2026",
            cutoff="2026-11-21T00:00:00Z",market="PTS",side="OVER",line=15.5)
        report=historical(rows,**args)
        self.assertEqual(report["windows"]["L5"]["hit_rate"],1)
        self.assertEqual(report["windows"]["L10"]["hit_rate"],.5)
        self.assertEqual(report["windows"]["season"]["sample"],20)
        self.assertEqual(report["windows"]["head_to_head_season"]["sample"],10)
        self.assertEqual(report["decision"],"HOLD")
        with self.assertRaises(ValueError):
            historical(rows+[rows[0]],**args)
    def test_backfill_uses_event_order(self):
        rows=[dict(subject_id="p",opponent_id="o",game_id=str(i),
            season="2026",final=True,PTS=i,
            event_start_utc=f"2026-11-{i:02d}T00:00:00Z",
            settled_utc=f"2026-11-{25-i:02d}T03:00:00Z") for i in range(1,11)]
        report=historical(rows,subject_id="p",opponent_id="o",season="2026",
            cutoff="2026-11-26T00:00:00Z",market="PTS",side="OVER",line=5.5)
        self.assertEqual(report["windows"]["L5"]["hit_rate"],1)

    def test_missing_combo_component(self):
        with self.assertRaises(KeyError):
            grade({"PTS":20},"PRA","OVER",25.5)

if __name__ == "__main__":
    unittest.main()
