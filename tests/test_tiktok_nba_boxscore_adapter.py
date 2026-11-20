import unittest
from research.tiktok_nba_boxscore_adapter import rolling_features

def box(game, start, threes, player="1"):
    return {"sport":"nba","event_id":str(game),"player_id":player,
            "player_name":"Fixture","event_start_utc":start,
            "did_not_play":False,"threes_made":threes,
            "independently_verified_player_stats":False,
            "qualified_for_player_prop_training":False}

class AdapterTests(unittest.TestCase):
    def test_rolling_features_only_use_prior_games(self):
        rows=[box(i,f"2026-11-{i:02d}T20:00:00Z",2) for i in range(1,12)]
        report=rolling_features(list(reversed(rows)))
        self.assertEqual(report["rows"][0]["last10_games"],0)
        self.assertEqual(report["unique_games"],11)
        self.assertEqual(report["unique_players"],1)
        self.assertEqual(report["rows_with_full_last10"],1)
        self.assertEqual(report["rows_with_incomplete_last10"],10)
        self.assertEqual(report["historical_90_outcome_wins"]+report["historical_90_outcome_losses"],report["historical_90_rows"])
        self.assertEqual(report["performance_scope"],"retrospective_boxscore_only_no_pregame_odds_or_independent_verification")
        self.assertEqual(report["rows"][10]["last10_hits"],10)
        self.assertTrue(report["rows"][10]["historical_90"])
        self.assertEqual(report["rows"][10]["decision"],"HOLD")
    def test_duplicate_quarantine(self):
        r=box(1,"2026-11-01T20:00:00Z",2)
        self.assertEqual(rolling_features([r,r])["quarantined_rows"],1)
    def test_dnp_quarantine(self):
        r=box(1,"2026-11-01T20:00:00Z",2)
        r["did_not_play"]=True
        self.assertEqual(rolling_features([r])["player_game_rows"],0)
    def test_nan_threshold_rejected(self):
        with self.assertRaises(ValueError):
            rolling_features([],float("nan"))

    def test_invalid_minutes_quarantined(self):
        r=box(1,"2026-11-01T20:00:00Z",2)
        r["minutes"]=float("inf")
        self.assertEqual(rolling_features([r])["quarantined_rows"],1)

    def test_same_time_no_lookahead(self):
        a=box(1,"2026-11-01T20:00:00Z",2)
        b=box(2,"2026-11-01T20:00:00Z",2)
        self.assertEqual(rolling_features([a,b])["rows"][1]["last10_games"],0)

if __name__=="__main__":unittest.main()


class ESPNThreePointLabelTests(unittest.TestCase):
    def test_three_point_made_attempted_parsing(self):
        from challenger_nba_player_boxes import _three_made
        self.assertEqual(_three_made("3-8"),3)
        self.assertIsNone(_three_made("9-8"))

    def _summary(self, label, value):
        def athlete(pid, stat):
            return {"athlete":{"id":pid,"displayName":"Fixture"},
                    "stats":["24","10","4","3",stat,"1","0","18"],
                    "didNotPlay":False}
        def group(tid, pid, stat):
            return {"team":{"id":tid},"statistics":[{
                "names":["MIN","PTS","REB","AST",label,"STL","BLK","FG"],
                "athletes":[athlete(pid,stat)]}]}
        return {"header":{"id":"100","competitions":[{
            "id":"100","date":"2026-11-01T23:00:00Z",
            "status":{"type":{"completed":True}},
            "competitors":[{"team":{"id":"1"}},{"team":{"id":"2"}}]}]},
            "boxscore":{"players":[group("1","123",value),group("2","456","1-4")]}}

    def test_alternate_label_parses_fixture(self):
        from challenger_nba_player_boxes import parse_summary
        rows=parse_summary(self._summary("3PM-A","3-8"),"100","2026-11-02T00:00:00Z")
        self.assertEqual(rows[0]["threes_made"],3)

    def test_conflicting_labels_are_rejected(self):
        from challenger_nba_player_boxes import parse_summary
        data=self._summary("3PT","3-8")
        category=data["boxscore"]["players"][0]["statistics"][0]
        category["names"].append("3PM-A")
        category["athletes"][0]["stats"].append("2-8")
        with self.assertRaisesRegex(ValueError,"conflicting three-point stat labels"):
            parse_summary(data,"100","2026-11-02T00:00:00Z")

class ESPNEventChronologyTests(unittest.TestCase):
    def test_missing_event_start_is_rejected(self):
        from challenger_nba_player_boxes import parse_summary
        fixture=ESPNThreePointLabelTests()._summary("3PT","2-5")
        del fixture["header"]["competitions"][0]["date"]
        with self.assertRaisesRegex(ValueError,"missing timezone-aware NBA event start"):
            parse_summary(fixture,"100","2026-11-02T00:00:00Z")

    def test_naive_event_start_is_rejected(self):
        from challenger_nba_player_boxes import parse_summary
        fixture=ESPNThreePointLabelTests()._summary("3PT","2-5")
        fixture["header"]["competitions"][0]["date"]="2026-11-01T23:00:00"
        with self.assertRaisesRegex(ValueError,"missing timezone-aware NBA event start"):
            parse_summary(fixture,"100","2026-11-02T00:00:00Z")
