"""V2 replaces only unverified old Portland/Minnesota total; keeps V1 immutable."""
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest
from v8_nba_ticket_research import audit_named_ticket

BASE = Path(__file__).resolve().parents[1] / "examples"
NOW = datetime(2026, 11, 17, 22, 20, tzinfo=timezone.utc)

class ReplacementResearchTicketTests(unittest.TestCase):
    def test_exactly_leg_two_swapped_and_history_preserved(self):
        original = json.loads((BASE / "nba_2026_11_17_eight_leg_research.json").read_text())
        revised = json.loads((BASE / "nba_2026_11_17_eight_leg_research_v2.json").read_text())
        self.assertEqual(len(original["legs"]), 8)
        self.assertEqual(len(revised["legs"]), 8)
        self.assertEqual([x for i,x in enumerate(original["legs"]) if i != 1],
                         [x for i,x in enumerate(revised["legs"]) if i != 1])
        self.assertEqual(original["legs"][1]["market"], "total_points")
        self.assertEqual(original["legs"][1]["line"], 228.5)
        new = revised["legs"][1]
        self.assertEqual(new["market"], "player_prop")
        self.assertEqual(new["player_name"], "Terrence Shannon Jr.")
        self.assertEqual(new["selection"], "under")
        self.assertEqual(new["prop_stat"], "player_made_threes")
        self.assertEqual(new["line"], 1.5)
        self.assertEqual(new["prior_reference_odds"], -121)
        self.assertEqual(new["prior_disposition"], "HOLD")
        self.assertEqual(revised["ticket_kind"], "research")
        self.assertNotIn("stake_usd", revised)
        self.assertNotIn("accepted_at", revised)

    def test_ticket_still_zero_certified_and_three_correlations(self):
        revised = json.loads((BASE / "nba_2026_11_17_eight_leg_research_v2.json").read_text())
        games = {"champion_001_modified": False, "certified_positive_ev_bets":0,
                 "today_game_market_board":[]}
        props = {"champion_001_modified": False, "certified_positive_ev_bets":0,
                 "today_player_prop_market_probability_board":{"nba":[]}}
        report = audit_named_ticket(revised, games, props, now=NOW)
        self.assertEqual(report["leg_count"], 8)
        self.assertEqual(len(report["same_event_groups"]), 3)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertEqual(report["verified_checkout_prices"], 0)
        self.assertEqual(report["wagers_placed"], 0)
        self.assertTrue(all(x["action"] == "HOLD" for x in report["legs"]))

if __name__ == "__main__":
    unittest.main()
