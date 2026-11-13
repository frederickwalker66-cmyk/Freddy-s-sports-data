"""All four NBA/NFL markets, independent native model gate and no fake 5-leg EV."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_edge_value import rank_research_edges, research_edge
from v8_mixed_market_board import mixed_market_board
from v8_one_command import execute, selected

NOW = datetime(2026, 11, 13, 13, 0, tzinfo=timezone.utc)


def independent_quote(market="moneyline", selection="home", line=None, p=.58):
    row = {
        "league": "nba", "event_id": "test-event-1",
        "market": market, "selection": selection,
        "bookmaker": "SyntheticBook", "american_odds": -110,
        "champion_001_modified": False,
        "model_version": "synthetic_test_only",
        "model_probability_source": "native_independent_pregame",
        "independent_model_review": True, "independent_price_review": True,
        "model_probability": p,
        "start_utc": "2026-11-13T23:00:00Z",
        "model_forecast_recorded_utc": "2026-11-13T20:00:00Z",
        "price_recorded_utc": "2026-11-13T20:01:00Z",
    }
    if market in ("point_spread", "total_points"):
        row.update({
            "line": line, "is_alternate_line": False,
            "model_target":
                "nba_fullgame_point_spread_cover" if market == "point_spread"
                else "nba_fullgame_total_points_overunder",
            "independent_market_settlement_review": True,
            "independent_exact_line_model_review": True,
        })
    if market == "player_prop":
        row.update({
            "player_id": "source-id-not-authenticated", "player_name": "Example",
            "prop_stat": "points", "line": line,
            "independent_player_active_review": True,
            "independent_prop_stat_settlement_review": True,
            "independent_prop_model_review": True,
            "is_alternate_line": False,
        })
    return row


def game_report():
    return {
        "champion_001_modified": False, "certified_positive_ev_bets": 0,
        "validated_source_quote_observations_by_league_and_market": {},
        "today_game_market_board": [{
            "league": "nba", "provider_event_id": "unverified-event-id",
            "home_team": "Home", "away_team": "Away",
            "start_utc": "2026-11-13T23:00:00+00:00",
            "paired_primary_markets": {
                k: {"market": k, "bookmaker_checkout_price_verified": False,
                    "native_model_probability_verified": False,
                    "home_or_over_line": (-2.5 if k == "point_spread"
                                         else 225.5 if k == "total_points" else None),
                    "away_or_under_line": (2.5 if k == "point_spread"
                                          else 225.5 if k == "total_points" else None),
                    "home_or_over_odds": -110,
                    "away_or_under_odds": -110,
                    "provider_quote_utc": "2026-11-13T12:00:00+00:00"}
                for k in ("moneyline", "point_spread", "total_points")
            },
        }],
    }


def prop_report():
    return {
        "champion_001_modified": False, "certified_positive_ev_bets": 0,
        "valid_prop_quotes_by_league": {},
        "today_player_prop_market_probability_board": {
            "nba": [{
                "league": "nba", "provider_event_id": "unverified-event-id",
                "home_team": "Home", "away_team": "Away",
                "start_utc": "2026-11-13T23:00:00+00:00",
                "last_capture_utc": "2026-11-13T12:00:00+00:00",
                "player_name": "Example Player", "prop_stat": "rebounds",
                "line": 6.5, "over_american_odds": +105,
                "under_american_odds": -125,
                "player_identity_independently_verified": False,
                "active_player_independently_verified": False,
            }], "nfl": [],
        },
    }


class MixedMarketTests(unittest.TestCase):
    def test_all_markets_appear_but_never_promoted_to_bets(self):
        result = mixed_market_board(game_report(), prop_report())
        self.assertEqual(result["displayed_reference_counts_by_market"],
                         {"moneyline": 1, "point_spread": 1, "total_points": 1, "player_prop": 1})
        self.assertEqual(result["total_visible_reference_markets"], 4)
        self.assertEqual(len(result["reference_quotes"]), 4)
        self.assertFalse(result["bet_ready"])
        self.assertEqual(result["certified_positive_ev_bets"], 0)
        self.assertIsNone(result["joint_five_leg_win_probability"])
        self.assertIsNone(result["verified_closing_line_value"])
        self.assertFalse(result["champion_001_modified"])
        for row in result["reference_quotes"]:
            self.assertFalse(row["direct_checkout_verified"])
            self.assertIsNone(row["model_probability"])
            self.assertIsNone(row["indicative_ev_roi_percent"])

    def test_model_promotion_fails_closed(self):
        g, p = game_report(), prop_report()
        g["champion_001_modified"] = True
        with self.assertRaisesRegex(ValueError, "untrusted"):
            mixed_market_board(g, p)
        g, p = game_report(), prop_report()
        p["today_player_prop_market_probability_board"]["nba"][0][
            "player_identity_independently_verified"] = True
        with self.assertRaisesRegex(ValueError, "unverified_player"):
            mixed_market_board(g, p)
        g, p = game_report(), prop_report()
        g["today_game_market_board"][0]["paired_primary_markets"][
            "point_spread"]["native_model_probability_verified"] = True
        with self.assertRaisesRegex(ValueError, "untrusted_mixed_game_quote"):
            mixed_market_board(g, p)

    def test_research_edge_accepts_full_game_spreads_and_overs_unders(self):
        lines = [
            independent_quote("moneyline", "home"),
            independent_quote("point_spread", "away", +7.5),
            independent_quote("total_points", "under", 225.5),
            independent_quote("player_prop", "over", 12.5),
        ]
        output = rank_research_edges(lines)
        self.assertEqual({r["market"] for r in output},
                         {"moneyline", "point_spread", "total_points", "player_prop"})
        self.assertTrue(all(r["indicative_ev_roi_percent"] > 0 for r in output))
        self.assertTrue(all(not r["bet_ready"] for r in output))
        self.assertEqual([r for r in output if r["market"] == "point_spread"][0]["line"], 7.5)

    def test_moneyline_win_probability_cannot_be_spread_cover_probability(self):
        r = independent_quote("point_spread", "home", -7.5)
        r["model_target"] = "nba_fullgame_moneyline"
        with self.assertRaisesRegex(ValueError, "exact_line_spread_total_model"):
            research_edge(r)
        r = independent_quote("total_points", "over", 225.5)
        r["independent_exact_line_model_review"] = False
        with self.assertRaisesRegex(ValueError, "exact_line_spread_total_model"):
            research_edge(r)
        r = independent_quote("point_spread", "home", -7.5)
        r["model_probability_source"] = "no_vig_market"
        with self.assertRaisesRegex(ValueError, "market_implied_probability_not_allowed"):
            research_edge(r)

    def test_alternate_lines_and_integer_push_risk_fail_closed(self):
        for market, selection, line in (
            ("point_spread", "home", -7),
            ("total_points", "over", 220.0),
            ("total_points", "under", -1.5),
        ):
            with self.subTest(market=market, line=line):
                with self.assertRaisesRegex(ValueError, "half_point_game_market"):
                    research_edge(independent_quote(market, selection, line))
        r = independent_quote("point_spread", "away", 3.5)
        r["is_alternate_line"] = True
        with self.assertRaisesRegex(ValueError, "half_point_game_market"):
            research_edge(r)
        r = independent_quote("total_points", "home", 225.5)
        with self.assertRaisesRegex(ValueError, "invalid_selection"):
            research_edge(r)

    def test_phone_mixed_scan_works_with_no_quotes_and_never_fabricates(self):
        self.assertEqual(selected("run_mixed_market"), ("nba", "nfl"))
        with tempfile.TemporaryDirectory() as folder:
            r = execute("run_mixed_market", now=NOW, output_dir=folder)
            m = r["mixed_market_research"]
            self.assertEqual(m["total_visible_reference_markets"], 0)
            self.assertEqual(m["certified_positive_ev_bets"], 0)
            self.assertFalse(m["bet_ready"])
            self.assertIsNone(m["joint_five_leg_win_probability"])
            self.assertTrue((Path(folder) / "MIXED_MARKET_GAME_PROP_RESEARCH.json").is_file())
            self.assertTrue((Path(folder) / "ONE_COMMAND_REPORT.json").is_file())


if __name__ == "__main__":
    unittest.main()
