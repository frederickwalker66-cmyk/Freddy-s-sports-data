"""Every One Command run must show percentages with strict source provenance."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_one_command import execute
from v8_probability_edge_dashboard import build_dashboard, render_dashboard


def empty_report(**extras):
    return {
        "command": "run_sharp",
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "research_edge_candidates": [],
        **extras,
    }


class ProbabilitySharpEdgeDashboardTests(unittest.TestCase):
    def test_no_evidence_does_not_invent_probability_or_sharp_percent(self):
        view = build_dashboard(empty_report())
        self.assertEqual(view["market_side_rows_total"], 0)
        self.assertEqual(view["certified_positive_ev_bets"], 0)
        self.assertIsNone(view["sharp_bettor_handle_percentage"])
        self.assertFalse(view["champion_001_modified"])
        text = render_dashboard(view)
        for market in ("moneyline", "point_spread", "total_points", "player_prop"):
            self.assertIn(market, text)
        self.assertIn("N/A", text)
        self.assertIn("HOLD", text)

    def test_every_completed_one_command_emits_json_and_phone_markdown(self):
        for command in ("model_status", "run_edge", "run_calibration", "run_readiness"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as folder:
                r = execute(command, output_dir=folder)
                self.assertEqual(r["probability_sharp_edge_dashboard"]["command"], command)
                name = Path(folder) / "PROBABILITY_SHARP_EDGE_DASHBOARD"
                view = json.loads(name.with_suffix(".json").read_text())
                lines = name.with_suffix(".md").read_text()
                self.assertEqual(view["certified_positive_ev_bets"], 0)
                self.assertIn("Model edge (pp)", lines)
                self.assertIn("Sharp Edge", lines)
                self.assertIn("N/A", lines)
                self.assertEqual(json.loads((Path(folder) / "ONE_COMMAND_REPORT.json").read_text())["probability_sharp_edge_dashboard"], view)

    def test_two_sided_price_math_not_promoted_to_model(self):
        q = {
            "market": "moneyline", "native_model_probability_verified": False,
            "bookmaker_checkout_price_verified": False,
            "home_or_over_line": None, "away_or_under_line": None,
            "home_or_over_odds": -120, "away_or_under_odds": 110,
            "first_side_no_vig_market_percent": 53.37,
            "second_side_no_vig_market_percent": 46.63,
            "first_side_break_even_percent": 54.55,
            "second_side_break_even_percent": 47.62,
            "provider_quote_utc": "2026-11-13T12:00:00Z",
        }
        game = {"league": "nba", "away_team": "Away", "home_team": "Home",
                "paired_primary_markets": {"moneyline": q}}
        view = build_dashboard(empty_report(
            sharp_full_game_markets={"today_game_market_board": [game]},
            sharp_archive={"ranked_market_movement_watchlist": [
                {"league": "nba", "away_team": "Away", "home_team": "Home",
                 "home_no_vig_change_percentage_points": 2.3}]}))
        self.assertEqual(view["market_side_rows_total"], 2)
        home = view["market_side_rows"][0]
        self.assertEqual(home["no_vig_market_probability_percent"], 53.37)
        self.assertEqual(home["break_even_probability_percent"], 54.55)
        self.assertIsNone(home["model_probability_percent"])
        self.assertIsNone(home["model_edge_percentage_points"])
        self.assertIsNone(home["expected_roi_percent"])
        self.assertEqual(view["market_movement_watchlist"][0]["market_price_movement_percentage_points"], 2.3)
        self.assertIsNone(view["market_movement_watchlist"][0]["sharp_money_handle_percent"])
        self.assertIn("2.3", render_dashboard(view))

    def test_independently_authored_research_edge_visible_but_not_certified(self):
        view = build_dashboard(empty_report(
            command="run_edge",
            research_edge_candidates=[{
                "league": "nba", "event_id": "research_sample",
                "market": "moneyline", "selection": "home",
                "american_odds": -110, "price_recorded_utc": "2026-11-13T16:00:00Z",
                "indicative_model_probability": 0.58,
                "break_even_probability": 110/210,
                "indicative_edge_percentage_points": 5.61905,
                "indicative_ev_roi_percent": 10.72,
                "certified_prediction": False,
            }]))
        r = view["market_side_rows"][0]
        self.assertEqual(r["model_probability_percent"], 58.0)
        self.assertAlmostEqual(r["break_even_probability_percent"], 52.38)
        self.assertAlmostEqual(r["model_edge_percentage_points"], 5.61905)
        self.assertEqual(r["expected_roi_percent"], 10.72)
        self.assertEqual(r["decision"], "RESEARCH_ONLY_HOLD")
        self.assertEqual(view["certified_positive_ev_bets"], 0)

    def test_original_nba_forward_model_percent_but_no_betting_edge(self):
        view = build_dashboard(empty_report(
            command="run_nba_forward",
            research_forward_probability_rows=[{
                "league": "nba", "away_team": "Away", "home_team": "Home",
                "forecast_recorded_utc": "2026-11-13T14:00:00Z",
                "model_probability_home_win_research_only": .61,
                "estimated_away_win_probability_research_only": .39,
                "certified_prediction": False,
            }]))
        self.assertEqual(view["market_side_rows_total"], 2)
        self.assertEqual(view["market_side_rows"][0]["model_probability_percent"], 61)
        self.assertEqual(view["market_side_rows"][1]["model_probability_percent"], 39)
        self.assertIsNone(view["market_side_rows"][0]["no_vig_market_probability_percent"])
        self.assertIsNone(view["market_side_rows"][0]["expected_roi_percent"])
        self.assertIn("RESEARCH_ONLY_HOLD", render_dashboard(view))

    def test_refuse_upstream_certified_bet_or_unsafe_model_override(self):
        for broken in (
            empty_report(certified_positive_ev_bets=1),
            empty_report(champion_001_modified=True),
            empty_report(research_edge_candidates=[{"certified_prediction": True}]),
            empty_report(research_forward_probability_rows=[{"certified_prediction": True}]),
        ):
            with self.assertRaises(ValueError):
                build_dashboard(broken)

    def test_phone_workflow_shows_view_for_every_command(self):
        src = Path(".github/workflows/v8-one-command.yml").read_text()
        self.assertIn("Always show percentages and Sharp Edge on every run", src)
        self.assertIn("PROBABILITY_SHARP_EDGE_DASHBOARD.md", src)
        self.assertIn("cat \"$report\" >> \"$GITHUB_STEP_SUMMARY\"", src)
        self.assertIn("v8_probability_edge_dashboard.py", src)
        self.assertIn("test_v8_probability_edge_dashboard.py", src)


if __name__ == "__main__":
    unittest.main()
