"""No network, no model updates: synthetic crossfeed safety fixtures."""
import unittest
from datetime import datetime,timezone
from crossfeed_reconcile import reconcile,market_key

NOW=datetime(2026,10,29,20,0,tzinfo=timezone.utc)
def quote(source="sharpapi_rest",eid="A",odds=-115,kind="moneyline",side="home",line=None,selection="ATL Hawks"):
    return {
        "source":source,"event_id":eid,"league":"nba",
        "home_team":"Atlanta Hawks","away_team":"Cleveland Cavaliers",
        "event_start_time":"2026-10-30T00:10:00Z" if source=="sharpapi_rest" else "2026-10-30T00:00:00Z",
        "market_type":kind,"selection_type":side,"selection":selection,"line":line,
        "player_name":None,"sportsbook":"draftkings","odds_american":odds,
        "timestamp":"2026-10-29T19:50:00Z","recorded_at":"2026-10-29T19:51:00Z",
        "certified_prediction":False,"model_probability":None
    }
class TestReconcile(unittest.TestCase):
    def test_agree_never_certifies(self):
        a,d,r=reconcile([quote()],[quote("sportsgameodds_v2","B")],NOW)
        self.assertEqual((len(a),len(d),r["event_time_discrepancies"]),(1,0,1))
        self.assertFalse(a[0]["bet_ready"])
        self.assertFalse(a[0]["draftkings_direct_price_verified"])
        self.assertEqual(r["certified_champion_001_predictions"],0)
    def test_disagreement_is_not_ev(self):
        a,d,r=reconcile([quote()],[quote("sportsgameodds_v2","B",-120)],NOW)
        self.assertEqual((len(a),len(d)),(0,1))
        self.assertFalse(d[0]["positive_ev_certified"])
    def test_lines_must_match(self):
        a,d,r=reconcile([quote(kind="point_spread",line=-1.5)],
                        [quote("sportsgameodds_v2","B",kind="point_spread",line=-2.5)],NOW)
        self.assertEqual(r["matched_market_lines"],0)
    def test_team_totals_excluded(self):
        self.assertIsNone(market_key(quote(kind="total_points",side="over",line=100.5,selection="Home Over")))
    def test_same_event_ambiguous_is_not_compared(self):
        a,d,r=reconcile([quote(),quote(eid="A2")],[quote("sportsgameodds_v2","B")],NOW)
        self.assertEqual(r["matched_events"],0)
    def test_no_duplicate_match_behind_stale_collections(self):
        b=quote("sportsgameodds_v2","B")
        b["recorded_at"]="2026-10-29T18:50:00Z"
        b["timestamp"]="2026-10-29T18:49:00Z"
        self.assertEqual(reconcile([quote()],[b],NOW)[2]["matched_market_lines"],0)
