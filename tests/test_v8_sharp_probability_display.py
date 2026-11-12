"""Price-only probability views: never synthetic model predictions, EV or bets."""
import json
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_sharp_probability_display import price_pair_probabilities
from v8_sharp_game_markets import summarize_full_game_markets
from v8_sharp_player_props import summarize_player_props
from v8_one_command import execute


NOW = datetime(2026, 11, 12, 16, 0, tzinfo=timezone.utc)


def price(odds):
    return 100 / (100+odds) if odds > 0 else abs(odds)/(abs(odds)+100)


def record(league="nba", market="moneyline", side="home", odds=-110,
           player=None, quoted="2026-11-12T15:48:00Z"):
    is_prop = player is not None
    stats = "player_points" if league == "nba" else "player_receptions"
    line = 24.5 if league == "nba" else 3.5
    return {
        "source": "sharpapi_rest", "record_type": "pregame_odds_observation",
        "sportsbook": "draftkings", "league": league,
        "event_id": "provider-event", "home_team": "Home Club",
        "away_team": "Away Club",
        "event_start_time": "2026-11-13T01:00:00Z",
        "market_type": stats if is_prop else market,
        "selection_type": side, "selection": side,
        "player_id": None, "player_name": player,
        "line": line if is_prop else None,
        "is_main_line": True, "is_alternate_line": False,
        "is_player_prop": is_prop,
        "timestamp": quoted, "recorded_at": "2026-11-12T15:49:00Z",
        "odds_american": odds,
        "odds_decimal": 1 + (odds / 100 if odds > 0 else 100 / abs(odds)),
        "model_probability": None, "certified_prediction": False,
    }


class SharpProbabilityDisplayTests(unittest.TestCase):
    def test_symmetric_negative_one_ten_price_yields_fifty_fifty_no_vig(self):
        p=price_pair_probabilities(price(-110),price(-110))
        self.assertEqual(p["first_side_break_even_percent"],52.38)
        self.assertEqual(p["second_side_break_even_percent"],52.38)
        self.assertEqual(p["first_side_no_vig_market_percent"],50.0)
        self.assertEqual(p["second_side_no_vig_market_percent"],50.0)
        self.assertEqual(p["bookmaker_price_overround_percent"],4.76)
        self.assertIsNone(p["native_model_probability_percent"])
        self.assertIsNone(p["certified_ev_roi_percent"])
        self.assertIsNone(p["verified_model_edge_percentage_points"])

    def test_asymmetric_price_is_market_normalized_not_its_break_even(self):
        p=price_pair_probabilities(price(-140),price(+120))
        self.assertAlmostEqual(
            p["first_side_no_vig_market_percent"]+
            p["second_side_no_vig_market_percent"],100,places=2)
        self.assertGreater(p["first_side_break_even_percent"],
                           p["first_side_no_vig_market_percent"])
        self.assertEqual(p["probability_source"],
                         "source_book_label_market_price_only_not_model")
        self.assertFalse(p["direct_executable_sportsbook_checkout_verified"])
        self.assertIsNone(p["verified_sharp_bettor_probability_percent"])

    def test_reject_unsupported_or_irrational_market_probability_input(self):
        for a,b in ((True,.5),(0,.5),(-.1,.5),(.4,.3),
                    (.99,.99),(float("nan"),.7),
                    (float("inf"),.1),("0.5",.5),(None,.5)):
            with self.subTest(pair=(a,b)):
                with self.assertRaises(ValueError):
                    price_pair_probabilities(a,b)

    def test_full_game_board_has_break_even_and_two_sided_market_percent(self):
        rows=[
            record(side="home",odds=-140),
            record(side="away",odds=+120),
        ]
        r,_=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(r["today_recent_upcoming_full_games"],1)
        m=r["today_game_market_board"][0]["paired_primary_markets"]["moneyline"]
        self.assertGreater(m["first_side_no_vig_market_percent"],50)
        self.assertLess(m["second_side_no_vig_market_percent"],50)
        self.assertTrue(m["first_side_break_even_percent"] > 0)
        self.assertIsNone(m["native_model_probability_percent"])
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertEqual(r["model_probability_display"],
                         "UNAVAILABLE_NOT_MODEL_GENERATED")

    def test_nba_nfl_props_show_market_prices_without_needing_a_repricing(self):
        for league in ("nba","nfl"):
            with self.subTest(league=league):
                rows=[
                    record(league=league,side="over",odds=-125,player="Example Athlete"),
                    record(league=league,side="under",odds=+105,player="Example Athlete"),
                ]
                r,mov=summarize_player_props(rows,now=NOW)
                self.assertEqual(r["exact_player_stat_line_repricings_historical"],0)
                self.assertEqual(r["today_recent_two_sided_prop_markets"],1)
                b=r["today_player_prop_market_probability_board"][league][0]
                self.assertEqual(b["player_identity_match_basis"],
                                 "provider_name_only_unverified")
                self.assertFalse(b["player_identity_independently_verified"])
                self.assertGreater(b["first_side_no_vig_market_percent"],50)
                self.assertLess(b["second_side_no_vig_market_percent"],50)
                self.assertIsNone(b["native_model_probability_percent"])
                self.assertIsNone(b["verified_sharp_bettor_probability_percent"])
                self.assertIsNone(b["certified_ev_roi_percent"])
                self.assertEqual(r["certified_positive_ev_bets"],0)
                self.assertEqual(mov,[])

    def test_mismatched_player_market_cannot_generate_probabilities(self):
        rows=[
            record(side="over",odds=-110,player="One Athlete"),
            record(side="under",odds=-110,player="Another Athlete"),
        ]
        r,_=summarize_player_props(rows,now=NOW)
        self.assertEqual(r["today_recent_two_sided_prop_markets"],0)
        self.assertEqual(r["today_player_prop_market_probability_board"]["nba"],[])

    def test_aggregated_probability_board_never_certifies_or_invents_model(self):
        rows=[
            record(side="home",odds=-140),
            record(side="away",odds=+120),
            record(side="over",odds=-125,player="Example Athlete"),
            record(side="under",odds=+105,player="Example Athlete"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            output=execute("run_nfl_props_edge",now=NOW,sharp_rows=rows,
                           output_dir=folder)
            self.assertEqual(output["certified_positive_ev_bets"],0)
            path=Path(folder)/"NBA_NFL_SHARP_EDGE_PROBABILITIES.json"
            self.assertTrue(path.is_file())
            report=json.loads(path.read_text())
            self.assertEqual(len(report["full_games"]),1)
            self.assertEqual(len(report["nba_player_props"]),1)
            self.assertEqual(report["nfl_player_props"],[])
            self.assertIsNone(report["native_model_probability"])
            self.assertIsNone(report["verified_sharp_flow_probability"])
            self.assertEqual(report["certified_positive_ev_bets"],0)
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual(report["automated_wagers"],0)
            self.assertTrue(report["full_games"][0]["paired_primary_markets"]
                            ["moneyline"]["first_side_break_even_percent"] > 0)

    def test_empty_input_reports_no_probabilities_and_no_bets(self):
        with tempfile.TemporaryDirectory() as folder:
            output=execute("run_nfl_props_edge",now=NOW,output_dir=folder)
            game=output["sharp_full_game_markets"]
            props=output["sharp_player_props"]
            self.assertEqual(game["research_market_probabilities_available"],0)
            self.assertEqual(props["today_recent_two_sided_prop_markets"],0)
            self.assertEqual(output["certified_positive_ev_bets"],0)


if __name__=="__main__":
    unittest.main()
