"""Synthetic all-eight-sport archive market tests; no paid odds calls or wagers."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from collector import (
    LEAGUES, OPTIONAL_LEAGUES, PROVIDER_LEAGUE_IDS,
    collect, main, normalize_quote,
)
from v8_sharp_game_markets import summarize_full_game_markets
from v8_sharp_player_props import summarize_player_props
from v8_soccer_market_research import summarize_soccer_markets, inspect_soccer_quote
from v8_every_sport_bundle import run_full_stack

NOW = datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc)


def q(league, market, side, line=None, odds=-110, **opts):
    row = {
        "id": "same-id", "source": "sharpapi_rest",
        "record_type": "pregame_odds_observation",
        "sportsbook": "draftkings", "sport": "soccer" if league in (
            "mls", "uefa_champions_league") else "basketball",
        "league": league, "event_id": "fixture-" + league,
        "home_team": "Fixture Home", "away_team": "Fixture Away",
        "market_type": market, "selection": side,
        "selection_type": side, "line": line,
        "odds_american": odds,
        "odds_decimal": 1 + (odds / 100 if odds > 0 else 100 / abs(odds)),
        "timestamp": "2026-11-14T18:55:00Z",
        "recorded_at": "2026-11-14T18:56:00Z",
        "event_start_time": "2026-11-14T20:00:00Z",
        "is_player_prop": False, "is_main_line": True,
        "is_alternate_line": False, "model_probability": None,
        "certified_prediction": False, "player_name": None,
        "player_id": None,
    }
    row.update(opts)
    return row


def no_bets(command, **kwargs):
    return {
        "command": command, "champion_001_modified": False,
        "money_wagered_usd": 0, "certified_positive_ev_bets": 0,
        "research_forward_probability_rows": [],
    }


class AllSportsMarketTests(unittest.TestCase):
    def test_three_primary_games_for_mlb_nhl_ncaab(self):
        for league, spread, total in (
            ("mlb", "run_line", "total_runs"),
            ("nhl", "puck_line", "total_goals"),
            ("ncaab", "point_spread", "total_points"),
        ):
            with self.subTest(league=league):
                quotes = [
                    q(league, "moneyline", "home", odds=-120),
                    q(league, "moneyline", "away", odds=+100),
                    q(league, spread, "home", line=-1.5),
                    q(league, spread, "away", line=+1.5),
                    q(league, total, "over", line=5.5),
                    q(league, total, "under", line=5.5),
                ]
                report, _ = summarize_full_game_markets(quotes, now=NOW)
                self.assertEqual(report["today_recent_upcoming_full_games"], 1)
                item = report["today_game_market_board"][0]
                self.assertEqual(set(item["paired_primary_markets"]), {
                    "moneyline", "point_spread", "total_points"})
                self.assertFalse(item["verified_sportsbook_checkout"])
                self.assertFalse(item["paired_primary_markets"]
                                 ["moneyline"]["market_settlement_scope_independently_verified"])
                self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_supported_primary_mlb_nhl_ncaab_player_props_only(self):
        for league, stat in (
            ("mlb", "player_pitcher_strikeouts"),
            ("nhl", "player_shots_on_goal"),
            ("ncaab", "player_points"),
        ):
            with self.subTest(league=league):
                rows = [q(league, stat, "over", line=3.5, is_player_prop=True,
                          player_id="p1", player_name="Example Athlete"),
                        q(league, stat, "under", line=3.5, is_player_prop=True,
                          player_id="p1", player_name="Example Athlete")]
                report, _ = summarize_player_props(rows, now=NOW)
                self.assertEqual(report["two_sided_same_line_snapshots"], 1)
                self.assertEqual(len(report[
                    "today_player_prop_market_probability_board"][league]), 1)
                self.assertFalse(report["player_active_verified"])
                self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_soccer_three_way_has_draw_and_separate_goal_total(self):
        for league in ("mls", "uefa_champions_league"):
            with self.subTest(league=league):
                rows = [q(league, "moneyline_3-way", "home", odds=+100),
                        q(league, "moneyline_3-way", "draw", odds=+240),
                        q(league, "moneyline_3-way", "away", odds=+220),
                        q(league, "total_goals", "over", 2.5),
                        q(league, "total_goals", "under", 2.5)]
                report = summarize_soccer_markets(rows, now=NOW)
                self.assertEqual(report["today_recent_exact_soccer_markets"], 2)
                three = next(x for x in report["today_soccer_game_market_board"]
                             if x["market"] == "three_way_90_minute")
                self.assertEqual(set(three["american_odds_by_outcome"]),
                                 {"home", "away", "draw"})
                self.assertAlmostEqual(sum(
                    three["normalized_no_vig_market_shares"].values()), 1, places=5)
                self.assertFalse(three["bet_ready"])
                self.assertEqual(report["certified_positive_ev_bets"], 0)
                full, _ = summarize_full_game_markets(rows, now=NOW)
                self.assertEqual(full["today_recent_upcoming_full_games"], 0)

    def test_soccer_two_way_moneyline_and_quarter_goals_blocked(self):
        league = "mls"
        rows = [q(league, "moneyline", "home", odds=-110),
                q(league, "moneyline", "away", odds=+100)]
        report = summarize_soccer_markets(rows, now=NOW)
        self.assertEqual(report["today_recent_exact_soccer_markets"], 0)
        self.assertIn("unpaired_duplicate_or_missing_soccer_outcomes",
                      report["excluded_or_unpaired_reasons"])
        item, reason = inspect_soccer_quote(
            q(league, "total_goals", "over", line=2.25))
        self.assertIsNone(item)
        self.assertEqual(reason,
                         "soccer_goal_total_requires_exact_half_goal_line")
        item, reason = inspect_soccer_quote(
            q(league, "asian_handicap", "home", line=-0.25))
        self.assertIsNone(item)
        self.assertEqual(reason, "ambiguous_or_unimplemented_soccer_settlement")

    def test_soccer_source_crosswalk_preserves_provider_slug(self):
        for model, slug in PROVIDER_LEAGUE_IDS.items():
            row = q(slug, "moneyline", "home", odds=+100,
                    is_live=False)
            row.pop("recorded_at", None)
            out = normalize_quote(row, NOW)
            self.assertEqual(out["league"], model)
            self.assertEqual(out["provider_league_id"], slug)

    def test_price_ids_reused_across_sides_cannot_deduplicate_market(self):
        rows = [q("nba", "moneyline", "home", odds=-120, is_live=False),
                q("nba", "moneyline", "away", odds=+100, is_live=False)]
        for x in rows:
            x.pop("recorded_at", None)
        response = {"data": rows, "pagination": {"has_more": False}}
        with (patch("collector.get_page", return_value=response),
              patch("collector.now_utc", return_value=NOW),
              patch("collector.time.sleep")):
            result, _, calls = collect("dummy", leagues=("nba",), max_pages=1)
        self.assertEqual(calls, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(set(x["selection_type"] for x in result),
                         {"home", "away"})

    def test_all_eight_api_budget_dry_run_does_not_call_provider(self):
        all_eight = ("nba", "nfl", "mlb") + OPTIONAL_LEAGUES
        with (patch("sys.argv", ["collector.py", "--dry-run",
                                 "--leagues", ",".join(all_eight),
                                 "--max-pages", "2"]),
              patch("collector.urlopen", side_effect=AssertionError("network")),
              patch.dict("os.environ", {}, clear=True)):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main()
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(len(result["leagues"]), 8)
        self.assertEqual(result["max_possible_provider_requests"], 32)
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["provider_league_filters"]
                         ["uefa_champions_league"], "uefa_-_champions_league")
        self.assertEqual(LEAGUES, ("nba", "nfl", "mlb"))

    def test_one_command_eight_sports_research_never_invents_bets(self):
        rows = []
        for league in ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab"):
            rows.extend([q(league, "moneyline", "home", odds=-120),
                         q(league, "moneyline", "away", odds=+100)])
        for league in ("mls", "uefa_champions_league"):
            rows.extend([q(league, "moneyline", "home", odds=+100),
                         q(league, "moneyline", "draw", odds=+240),
                         q(league, "moneyline", "away", odds=+220)])
        with tempfile.TemporaryDirectory() as temp:
            report = run_full_stack(
                command="run_all", execute_fn=no_bets,
                sharp_rows=rows, now=NOW, output_dir=temp)
            evidence = report["sharp_edge_research"]["per_sport_market_evidence"]
            self.assertEqual(len(evidence), 8)
            self.assertEqual(len(report["betting_readiness"]["by_market"]), 28)
            for league in evidence:
                self.assertGreater(evidence[league]["archived_provider_quote_rows"], 0)
                self.assertEqual(evidence[league]["fresh_paired_game_boards"], 1)
                self.assertEqual(evidence[league]["primary_source_blocker"],
                                 "UNVERIFIED_MODEL_PROBABILITY_AND_CHECKOUT")
            self.assertEqual(
                report["sharp_edge_research"]["today_full_game_markets_in_selected_leagues"], 8)
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual(report["certified_positive_ev_bets"], 0)
            self.assertEqual(report["money_wagered_usd"], 0)

    def test_soccer_integration_exposes_market_without_ev(self):
        rows = [
            q("mls", "moneyline", "home", odds=+100),
            q("mls", "moneyline", "draw", odds=+240),
            q("mls", "moneyline", "away", odds=+220),
        ]
        with tempfile.TemporaryDirectory() as temp:
            r = run_full_stack(command="run_mls", execute_fn=no_bets,
                               sharp_rows=rows, now=NOW, output_dir=temp)
            evidence = r["sharp_edge_research"]["per_sport_market_evidence"]["mls"]
            self.assertEqual(evidence["archived_provider_quote_rows"], 3)
            self.assertEqual(evidence["fresh_paired_game_boards"], 1)
            self.assertEqual(evidence["primary_source_blocker"],
                             "UNVERIFIED_MODEL_PROBABILITY_AND_CHECKOUT")
            self.assertEqual(r["certified_positive_ev_bets"], 0)
            self.assertFalse(r["champion_001_modified"])
            self.assertEqual(r["money_wagered_usd"], 0)
            self.assertTrue((Path(temp) /
                             "FULL_STACK_MARKET_PROBABILITIES.json").exists())


if __name__ == "__main__":
    unittest.main()
