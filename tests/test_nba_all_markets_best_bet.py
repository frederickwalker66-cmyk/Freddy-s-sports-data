import unittest
from research.nba_all_markets_best_bet import evaluate,MARKETS

class TestAllMarketBestBet(unittest.TestCase):
    def test_all_categories_present(self):
        self.assertEqual(len(MARKETS),20)
        self.assertIn("player_pra_over",MARKETS)
    def test_no_unverified_best_bet(self):
        result=evaluate([{"market":"moneyline","selection":"X","champion_probability":0.9,"decimal_odds":2.0}])
        self.assertEqual(result["markets"][0]["decision"],"HOLD")
        self.assertIsNone(result["best_bet"])
    def test_verified_pass_and_take(self):
        receipts={k:"receipt" for k in ("model","odds","timestamp","roster","injury")}
        args=dict(champion_verified=True,draftkings_verified=True,
                  odds_integrity_verified=True,calibration_verified=True)
        rows=[{"market":"spread","selection":"A","champion_probability":0.4,"decimal_odds":2.0,"receipts":receipts},
              {"market":"player_pra_over","selection":"B","champion_probability":0.6,"decimal_odds":2.0,"receipts":receipts}]
        result=evaluate(rows,**args)
        self.assertEqual([x["decision"] for x in result["markets"]],["PASS","TAKE"])
        self.assertEqual(result["best_bet"]["selection"],"B")
if __name__=="__main__": unittest.main()
