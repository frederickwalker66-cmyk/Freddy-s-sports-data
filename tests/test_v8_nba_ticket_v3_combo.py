"""Eight-leg V3 combo research swap must remain HOLD without a native edge."""
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest
from v8_nba_ticket_research import audit_named_ticket

ROOT = Path(__file__).resolve().parents[1] / "examples"
NOW = datetime(2026,11,17,22,22,tzinfo=timezone.utc)

class ComboV3TicketTests(unittest.TestCase):
    def test_only_second_leg_replaced_by_rebounds_assists_combo(self):
        v2=json.loads((ROOT / "nba_2026_11_17_eight_leg_research_v2.json").read_text())
        v3=json.loads((ROOT / "nba_2026_11_17_eight_leg_research_v3_combo.json").read_text())
        self.assertEqual(len(v3["legs"]),8)
        self.assertEqual(v3["version"],"V3_COMBO_SWAP")
        self.assertEqual([x for i,x in enumerate(v2["legs"]) if i != 1],
                         [x for i,x in enumerate(v3["legs"]) if i != 1])
        replaced=v3["legs"][1]
        self.assertEqual(replaced["event_id"],v2["legs"][1]["event_id"])
        self.assertEqual(replaced["player_name"],"Jaden McDaniels")
        self.assertEqual(replaced["prop_stat"],"player_rebounds_+_assists")
        self.assertEqual(replaced["selection"],"over")
        self.assertEqual(replaced["line"],8.5)
        self.assertEqual(replaced["prior_disposition"],"HOLD")
        self.assertEqual(v3["ticket_kind"],"research")
        self.assertNotIn("stake_usd",v3)

    def test_new_combo_is_not_certified_bet(self):
        v3=json.loads((ROOT / "nba_2026_11_17_eight_leg_research_v3_combo.json").read_text())
        games={"certified_positive_ev_bets":0,"champion_001_modified":False,"today_game_market_board":[]}
        props={"certified_positive_ev_bets":0,"champion_001_modified":False,
               "today_player_prop_market_probability_board":{"nba":[]}}
        r=audit_named_ticket(v3,games,props,now=NOW)
        self.assertEqual(len(r["legs"]),8)
        self.assertEqual(r["current_qualified_two_sided_reference_count"],0)
        self.assertEqual(len(r["same_event_groups"]),3)
        self.assertEqual(r["verified_champion_001_probabilities"],0)
        self.assertEqual(r["verified_checkout_prices"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertEqual(r["wagers_placed"],0)
        self.assertTrue(all(x["action"]=="HOLD" for x in r["legs"]))

if __name__=="__main__":
    unittest.main()
