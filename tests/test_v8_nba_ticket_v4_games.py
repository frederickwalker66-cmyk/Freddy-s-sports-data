"""V4 only replaces leg 2 with a game moneyline; HOLD all unverified selections."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from v8_nba_ticket_research import audit_named_ticket

ROOT=Path(__file__).resolve().parents[1]/"examples"
class V4GamesTicketTests(unittest.TestCase):
    def test_game_substitution_and_fail_closed_audit(self):
        v3=json.loads((ROOT/"nba_2026_11_17_eight_leg_research_v3_combo.json").read_text())
        v4=json.loads((ROOT/"nba_2026_11_17_eight_leg_research_v4_games.json").read_text())
        self.assertEqual(len(v4["legs"]),8)
        self.assertEqual([v for i,v in enumerate(v3["legs"]) if i!=1],
                         [v for i,v in enumerate(v4["legs"]) if i!=1])
        leg=v4["legs"][1]
        self.assertEqual((leg["market"],leg["selection"],leg["line"]),
                         ("moneyline","home",None))
        self.assertEqual(leg["prior_reference_odds"],-143)
        self.assertEqual(v4["ticket_kind"],"research")
        self.assertNotIn("stake_usd",v4)
        games={"certified_positive_ev_bets":0,"champion_001_modified":False,"today_game_market_board":[]}
        props={"certified_positive_ev_bets":0,"champion_001_modified":False,
               "today_player_prop_market_probability_board":{"nba":[]}}
        report=audit_named_ticket(v4,games,props,now=datetime(2026,11,17,22,26,tzinfo=timezone.utc))
        self.assertEqual(report["leg_count"],8)
        self.assertEqual(len(report["same_event_groups"]),3)
        self.assertEqual(report["certified_positive_ev_bets"],0)
        self.assertEqual(report["verified_checkout_prices"],0)
        self.assertEqual(report["wagers_placed"],0)
        self.assertTrue(all(x["action"]=="HOLD" for x in report["legs"]))

if __name__=="__main__":
    unittest.main()
