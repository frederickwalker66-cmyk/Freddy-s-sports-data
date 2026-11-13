"""NBA shorthand ALWAYS includes full sharp-edge evidence, never market-as-model p."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v8_nba_always_sharp_edge import build_nba_sharp_edge, render, save
from v8_sharp_archive import summarize_sharp_archive
from v8_sharp_player_props import summarize_player_props
from v8_sharp_game_markets import summarize_full_game_markets
from v8_sharp_calibration_dashboard import dashboard
from v8_one_command import main

NOW = datetime(2026, 11, 13, 22, 0, tzinfo=timezone.utc)


def data():
    sharp, _ = summarize_sharp_archive([], now=NOW)
    props, _ = summarize_player_props([], now=NOW)
    games, _ = summarize_full_game_markets([], now=NOW)
    cal = dashboard()
    return sharp, props, games, cal


class NBAAlwaysSharpEdgeTests(unittest.TestCase):
    def test_no_source_is_hold_not_fake_five_legs_or_clv(self):
        r = build_nba_sharp_edge(*data())
        self.assertTrue(r["sharp_edge_checked_every_nba_run"])
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertEqual(r["verified_executable_draftkings_checkout_quotes"], 0)
        self.assertEqual(r["independently_certified_parlay_legs"], 0)
        self.assertIsNone(r["native_exact_market_model_probability"])
        self.assertIsNone(r["verified_clv_percent"])
        self.assertIn("HOLD_", r["decision"])
        self.assertIn("No fresh supported", render(r))
        with tempfile.TemporaryDirectory() as folder:
            save(r, folder)
            self.assertTrue((Path(folder)/"NBA_SHARP_EDGE_ALWAYS.json").is_file())
            self.assertIn("Sharp Edge", (Path(folder)/"NBA_SHARP_EDGE_ALWAYS.md").read_text())

    def test_actual_archived_nba_watch_rows_are_research_only(self):
        sharp,props,games,cal=data()
        sharp["ranked_market_movement_watchlist"]=[
            {"league":"nba","home_team":"Boston","away_team":"New York",
             "home_no_vig_change_percentage_points":2.9,"positive_ev_certified":False},
            {"league":"nfl","home_team":"Boston","away_team":"New York",
             "positive_ev_certified":False}]
        props["ranked_prop_repricing_watchlist"]=[
            {"league":"nba","player_name":"Test Player", "prop_stat":"points",
             "absolute_repricing_pp":3.1,"positive_ev_certified":False}]
        games["today_recent_market_repricing_watchlist"]=[
            {"league":"nba","market":"total_points","home_team":"A","away_team":"B",
             "same_line_no_vig_market_price_change_pp":1.1,
             "certified_positive_ev":False}]
        season={"by_league":{"nba":{"player_last5_complete":376,
                                   "player_last10_complete":196,
                                   "team_last5_complete":30,
                                   "team_last10_complete":28}}}
        result=build_nba_sharp_edge(sharp,props,games,cal,season)
        self.assertEqual(len(result["nba_recent_moneyline_price_movement_watch"]),1)
        self.assertEqual(result["nba_last10_complete_player_histories_source_only"],196)
        self.assertIn("Test Player",render(result))
        self.assertIsNone(result["qualified_independent_model_expected_value_percent"])
        self.assertEqual(result["positive_ev_certified"],0)

    def test_false_professional_flow_or_certification_is_rejected(self):
        sharp,props,games,cal=data()
        props["sharp_flow_verified"]=True
        with self.assertRaisesRegex(ValueError,"false_independent_verification"):
            build_nba_sharp_edge(sharp,props,games,cal)
        props["sharp_flow_verified"]=False
        games["certified_positive_ev_bets"]=1
        with self.assertRaisesRegex(ValueError,"unverified_ev_promotion"):
            build_nba_sharp_edge(sharp,props,games,cal)

    def test_run_nba_phone_command_routes_to_sharp_edge_full_slate(self):
        with patch("v8_one_command.execute") as fake:
            fake.return_value={"requested_leagues":["nba"],"research_edge_candidates":[]}
            with tempfile.TemporaryDirectory() as folder:
                main(["--command","run_nba","--output-dir",folder])
            self.assertEqual(fake.call_args.args[0],"run_nba_best_bets")
            self.assertEqual(fake.call_args.kwargs["days"],35)
        # Legacy research tests can still invoke execute("run_nba",
        # end_date=...) explicitly for pinned historical archives.


if __name__ == "__main__":
    unittest.main()
