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

    def test_alternate_label_is_supported_by_parser(self):
        import inspect
        from challenger_nba_player_boxes import parse_summary
        source=inspect.getsource(parse_summary)
        self.assertIn('"3PM-A"',source)
        self.assertIn('"3PT"',source)
        self.assertIn("conflicting three-point stat labels",source)
