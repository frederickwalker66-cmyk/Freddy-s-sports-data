"""Offline, fail-closed one-display Sharp Edge regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_unified_sharp_edge_board import build, render_html, render_markdown, save

SPORTS=["nba","nfl","mlb","nhl","ncaaf","ncaab","mls","uefa_champions_league"]


def bundle(**changes):
    b={
        "champion_001_modified":False,"certified_positive_ev_bets":0,
        "requested_leagues":list(SPORTS),"user_command":"run_sharp",
        "checked_at_utc":"2026-11-16T20:00:00+00:00",
        "sharp_edge_research":{
            "research_only_game_line_examples":[],
            "research_only_player_market_examples":[],
        },
        "research_only_pregame_predictions":[],
        "research_game_schedule":[],
    }
    b.update(changes)
    return b


def nba_market():
    return {
        "league":"nba","away_team":"Orlando","home_team":"Boston",
        "verified_sportsbook_checkout":False,
        "paired_primary_markets":{
            "moneyline":{
                "bookmaker_checkout_price_verified":False,
                "native_model_probability_verified":False,
                "home_or_over_line":None,"away_or_under_line":None,
                "home_or_over_odds":-120,"away_or_under_odds":110,
                "provider_quote_utc":"2026-11-16T19:52:00Z",
                "first_side_no_vig_market_percent":53.37,
                "second_side_no_vig_market_percent":46.63,
                "first_side_break_even_percent":54.55,
                "second_side_break_even_percent":47.62,
            }
        },
    }


def nba_combo():
    return {
        "league":"nba","away_team":"Orlando","home_team":"Boston",
        "player_name":"Example Player","prop_stat":"player_points_+_assists",
        "line":28.5,"over_american_odds":-110,"under_american_odds":-110,
        "last_capture_utc":"2026-11-16T19:53:00Z",
        "first_side_no_vig_market_percent":50.0,
        "second_side_no_vig_market_percent":50.0,
        "first_side_break_even_percent":52.38,
        "second_side_break_even_percent":52.38,
        "player_identity_independently_verified":False,
        "active_player_independently_verified":False,"bet_ready":False,
    }


class OneDisplayTests(unittest.TestCase):
    def test_empty_all_sport_command_shows_all_eight_not_fabricated(self):
        q=build(bundle())
        self.assertEqual(len(q["rows"]),8)
        self.assertEqual(set(x["league"] for x in q["rows"]),set(SPORTS))
        self.assertTrue(all(x["category"]=="COVERAGE" for x in q["rows"]))
        self.assertTrue(all(x["verified_champion_001_probability_percent"] is None for x in q["rows"]))
        self.assertTrue(all(x["expected_roi_percent"] is None for x in q["rows"]))
        self.assertIn("N/A",render_markdown(q))
        self.assertIn("ONE DISPLAY",render_markdown(q))

    def test_all_categories_and_both_sides_in_single_market_table(self):
        b=bundle()
        b["sharp_edge_research"]["research_only_game_line_examples"]=[nba_market()]
        b["sharp_edge_research"]["research_only_player_market_examples"]=[nba_combo()]
        b["research_game_schedule"]=[{"league":"nba","away_team":"Orlando",
                                     "home_team":"Boston"}]
        q=build(b)
        nba=[x for x in q["rows"] if x["league"]=="nba"]
        self.assertEqual(len(nba),5)
        self.assertEqual([x["selection"] for x in nba
                          if x["market"]=="moneyline"],["Boston","Orlando"])
        combo=[x for x in nba if x["category"]=="COMBO"]
        self.assertEqual(len(combo),2)
        self.assertEqual(set(x["market"] for x in combo),{"PA"})
        self.assertEqual(nba[0]["verified_champion_001_probability_percent"],None)
        self.assertEqual(nba[0]["sharp_edge_percentage_points"],None)
        home=next(x for x in nba if x["selection"]=="Boston")
        self.assertEqual(home["no_vig_market_probability_percent"],53.37)
        self.assertEqual(home["break_even_probability_percent"],54.55)
        self.assertEqual(home["source_age_minutes"],8.0)
        self.assertIn("53.37%",render_markdown(q))
        self.assertIn("52.38%",render_markdown(q))

    def test_soccer_draw_not_conflated_with_moneyline(self):
        b=bundle()
        b["sharp_edge_research"]["research_only_game_line_examples"]=[{
            "league":"mls","away_team":"A","home_team":"B",
            "market":"three_way_90_minute",
            "bookmaker_checkout_price_verified":False,
            "independent_model_probability_verified":False,
            "american_odds_by_outcome":{"home":160,"draw":220,"away":175},
            "normalized_no_vig_market_shares":{"home":0.364,"draw":0.295,"away":0.341},
            "provider_quote_utc":"2026-11-16T19:55:00Z"
        }]
        rows=[x for x in build(b)["rows"] if x["league"]=="mls"]
        self.assertEqual({x["selection"] for x in rows},{"HOME","DRAW","AWAY"})
        self.assertEqual({x["category"] for x in rows},{"SOCCER 1X2"})
        self.assertEqual(next(x for x in rows if x["selection"]=="DRAW")
                         ["no_vig_market_probability_percent"],29.5)

    def test_research_forecasts_not_champion_and_not_ev(self):
        b=bundle(research_only_pregame_predictions=[{
            "league":"nfl","home_team":"B","away_team":"A",
            "home_win_research_rule_probability":0.62,
            "away_win_research_rule_probability":0.38,
            "original_forecast_recorded_utc":"2026-11-16T18:01:00Z",
            "native_Champion_001_model_probability":None,
            "market_specific_verified_expected_value":None,
            "verified_live_sportsbook_quote":False
        }])
        rows=[x for x in build(b)["rows"] if x["league"]=="nfl"]
        self.assertEqual([x["research_model_probability_percent"] for x in rows],[38,62])
        self.assertTrue(all(x["verified_champion_001_probability_percent"] is None for x in rows))
        self.assertTrue(all(x["break_even_probability_percent"] is None for x in rows))
        self.assertTrue(all("conditional on no tie" in x["notes"] for x in rows))

    def test_fail_closed_untrusted_certification_and_prop_roster(self):
        with self.assertRaises(ValueError):
            build(bundle(certified_positive_ev_bets=1))
        with self.assertRaises(ValueError):
            build(bundle(champion_001_modified=True))
        b=bundle()
        bad=nba_combo()
        bad["active_player_independently_verified"]=True
        b["sharp_edge_research"]["research_only_player_market_examples"]=[bad]
        with self.assertRaises(ValueError):
            build(b)

    def test_artifact_html_filters_and_escaped_provider_labels(self):
        b=bundle()
        m=nba_market()
        m["home_team"]="Boston <script>alert(1)</script>"
        b["sharp_edge_research"]["research_only_game_line_examples"]=[m]
        q=build(b)
        with tempfile.TemporaryDirectory() as temp:
            save(q,temp)
            out=Path(temp)
            self.assertTrue((out/"ONE_DISPLAY_SHARP_EDGE.html").is_file())
            self.assertTrue((out/"ONE_DISPLAY_SHARP_EDGE.json").is_file())
            self.assertTrue((out/"ONE_DISPLAY_SHARP_EDGE_SUMMARY.md").is_file())
            html=render_html(q)
            self.assertIn("id=\"search\"",html)
            self.assertIn("id=\"sport\"",html)
            self.assertIn("id=\"market\"",html)
            self.assertIn("\\u003cscript",html)
            self.assertNotIn("<script>alert(1)</script>",html)
            self.assertEqual(json.loads((out/"ONE_DISPLAY_SHARP_EDGE.json").read_text())["displayed_rows"],9)


if __name__=="__main__":
    unittest.main()
