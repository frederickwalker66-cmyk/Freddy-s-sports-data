import unittest
from v8_unified_best_bets import price_freshness, reverse_edge, rank, wilson

NOW="2026-11-28T12:00:00Z"
START="2026-11-28T20:00:00Z"

def quote(odds=-110, stamp="2026-11-28T11:59:00Z"):
    return dict(sportsbook="draftkings",event_id="e1",market_id="m1",
                selection_id="s1",line=220.5,start_utc=START,
                provider_quote_utc=stamp,last_capture_utc=stamp,
                american_odds=odds)

class SafeguardTests(unittest.TestCase):
    def test_freshness(self):
        self.assertEqual(price_freshness(quote(),NOW),"FRESH_RESEARCH_ONLY")
        self.assertEqual(price_freshness(quote(stamp="2026-11-28T11:54:00Z"),NOW),"HOLD_STALE_PRICE")
        self.assertEqual(price_freshness({**quote(),"sportsbook":"other"},NOW),"HOLD_WRONG_BOOK")
        self.assertEqual(price_freshness({**quote(),"start_utc":"2026-11-28T11:00:00Z"},NOW),"HOLD_INVALID_CHRONOLOGY")
        self.assertEqual(price_freshness({**quote(),"american_odds":-90},NOW),"HOLD_INVALID_PRICE")
        self.assertEqual(price_freshness({**quote(),"provider_quote_utc":None},NOW),"HOLD_MISSING_PRICE_EVIDENCE")

    def test_reverse_edge(self):
        old=quote(-110,"2026-11-28T11:30:00Z")
        new=quote(-130)
        splits={k:new[k] for k in ("sportsbook","event_id","market_id","selection_id","line","start_utc")}
        splits.update(observed_utc="2026-11-28T11:59:00Z",ticket_pct=35)
        out=reverse_edge(old,new,splits,NOW)
        self.assertTrue(out["signal"])
        self.assertEqual(out["decision"],"HOLD")
        self.assertIsNone(out["model_probability"])
        self.assertFalse(reverse_edge(old,new,{**splits,"line":221.5},NOW)["signal"])
        self.assertFalse(reverse_edge(old,new,{**splits,"ticket_pct":70},NOW)["signal"])
        self.assertFalse(reverse_edge(old,new,{**splits,"observed_utc":"2026-11-28T11:45:00Z"},NOW)["signal"])

    def test_research_ranking_never_certifies(self):
        windows={"season":dict(wins=25,losses=5),"L10":dict(wins=9,losses=1,hit_rate=.9)}
        candidate=dict(selection="Over",history=dict(windows=windows),
                       certified_prediction=True,bet_ready=True,model_probability=.99,ev=5)
        out=rank([candidate])[0]
        self.assertEqual(out["decision"],"HOLD")
        self.assertFalse(out["certified_prediction"])
        self.assertFalse(out["bet_ready"])
        self.assertIsNone(out["ev"])
        self.assertIsNone(out["model_probability"])
        self.assertGreater(wilson(25,5),0)
        with self.assertRaises(ValueError):
            wilson(-1,5)

if __name__=="__main__":
    unittest.main()
