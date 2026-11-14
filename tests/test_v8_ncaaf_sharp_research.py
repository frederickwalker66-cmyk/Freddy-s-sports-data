"""Safety-first NCAAF archived moneyline, spread, total and player prop tests.

Only synthetic two-sided quotes. No paid collection, betting, or Champion updates.
"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from v8_sharp_game_markets import inspect_full_game_quote, summarize_full_game_markets
from v8_sharp_player_props import inspect_player_prop, summarize_player_props
from v8_every_sport_bundle import run_full_stack

NOW = datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc)


def quote(market="moneyline", side="home", line=None, odds=-110, *,
          player=False, **overrides):
    row = {
        "source": "sharpapi_rest",
        "sportsbook": "draftkings",
        "record_type": "pregame_odds_observation",
        "sport": "football",
        "league": "ncaaf",
        "event_id": "SYNTHETIC_NCAAF_GAME",
        "home_team": "Fixture Home",
        "away_team": "Fixture Away",
        "market_type": market,
        "selection_type": side,
        "selection": side,
        "line": line,
        "odds_american": odds,
        "odds_decimal": 1 + (odds / 100 if odds > 0 else 100 / abs(odds)),
        "timestamp": "2026-11-14T18:55:00Z",
        "recorded_at": "2026-11-14T18:56:00Z",
        "event_start_time": "2026-11-14T20:00:00Z",
        "is_player_prop": player,
        "is_main_line": True,
        "is_alternate_line": False,
        "player_id": "fixture-receiver" if player else None,
        "player_name": "Fixture Receiver" if player else None,
        "certified_prediction": False,
        "model_probability": None,
    }
    row.update(overrides)
    return row


def ncaaf_rows():
    rows = []
    rows += [quote("moneyline", "home", None, -120),
             quote("moneyline", "away", None, +100)]
    rows += [quote("point_spread", "home", -3.5),
             quote("point_spread", "away", +3.5)]
    rows += [quote("total_points", "over", 49.5),
             quote("total_points", "under", 49.5)]
    rows += [quote("player_receiving_yards", "over", 75.5, player=True),
             quote("player_receiving_yards", "under", 75.5, player=True)]
    return rows


def empty_core(command, **kwargs):
    return {"command": command, "champion_001_modified": False,
            "money_wagered_usd": 0, "certified_positive_ev_bets": 0,
            "research_forward_probability_rows": []}


class NCAAFArchivedResearchTests(unittest.TestCase):
    def test_ncaaf_three_full_game_markets_only_as_unverified_research(self):
        rows = ncaaf_rows()
        report, movements = summarize_full_game_markets(rows, now=NOW)
        self.assertEqual(report["today_recent_upcoming_full_games"], 1)
        self.assertEqual(len(movements), 0)
        game = report["today_game_market_board"][0]
        self.assertEqual(game["league"], "ncaaf")
        self.assertTrue(game["all_three_game_markets_present"])
        self.assertEqual(set(game["paired_primary_markets"]),
                         {"moneyline", "point_spread", "total_points"})
        self.assertFalse(game["verified_sportsbook_checkout"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_ncaaf_strict_prop_pair_is_not_a_pick(self):
        props = ncaaf_rows()[-2:]
        report, movements = summarize_player_props(props, now=NOW)
        self.assertEqual(report["valid_prop_quotes_by_league"]["ncaaf"], 2)
        self.assertEqual(report["two_sided_same_line_snapshots"], 1)
        self.assertEqual(len(report["today_player_prop_market_probability_board"]["ncaaf"]), 1)
        item = report["today_player_prop_market_probability_board"]["ncaaf"][0]
        self.assertEqual(item["prop_stat"], "player_receiving_yards")
        self.assertFalse(item["active_player_independently_verified"])
        self.assertFalse(item["bet_ready"])
        self.assertEqual(report["certified_ncaaf_player_props"], 0)
        self.assertFalse(movements)

    def test_wrong_vendor_and_unsupported_settlement_fail_closed(self):
        game = quote(source="sportsgameodds_v2")
        item, reason = inspect_full_game_quote(game)
        self.assertIsNone(item)
        self.assertEqual(reason, "untrusted_primary_market_or_certification_flags")
        prop = quote("player_receiving_yards_combo_h2h", "over", 50.5,
                     player=True)
        item, reason = inspect_player_prop(prop)
        self.assertIsNone(item)
        self.assertEqual(reason, "unsupported_or_ambiguous_prop_settlement_market")
        in_play = quote(event_start_time="2026-11-14T18:54:00Z")
        item, reason = inspect_full_game_quote(in_play)
        self.assertIsNone(item)
        self.assertEqual(reason, "inplay_or_outdated_provider_receipt")

    def test_full_stack_exposes_ncaaf_source_gaps_without_fabricating_ev(self):
        with tempfile.TemporaryDirectory() as temp:
            empty = run_full_stack(
                command="run_ncaaf", execute_fn=empty_core,
                now=NOW, output_dir=Path(temp) / "empty")
            self.assertEqual(
                empty["by_league"]["ncaaf"]["archived_sportsbook_market_support"],
                "ncaaf_parser_ready_no_archived_provider_quotes")
            self.assertEqual(
                empty["sharp_edge_research"]["per_sport_market_evidence"]
                ["ncaaf"]["archived_provider_quote_rows"], 0)
            self.assertEqual(
                empty["sharp_edge_research"]["per_sport_market_evidence"]
                ["ncaaf"]["primary_source_blocker"], "NO_ARCHIVED_PROVIDER_QUOTES")
            self.assertFalse(
                empty["quoted_market_probability_research"]["ncaaf_live_provider_feed_proven"])
            report = run_full_stack(
                command="run_ncaaf", execute_fn=empty_core,
                now=NOW, output_dir=Path(temp) / "quotes",
                sharp_rows=ncaaf_rows())
            evidence = report["sharp_edge_research"]["per_sport_market_evidence"]["ncaaf"]
            self.assertEqual(evidence["archived_provider_quote_rows"], 8)
            self.assertEqual(evidence["fresh_paired_game_boards"], 1)
            self.assertEqual(evidence["fresh_paired_player_prop_markets"], 1)
            self.assertEqual(evidence["primary_source_blocker"],
                             "UNVERIFIED_MODEL_PROBABILITY_AND_CHECKOUT")
            self.assertEqual(report["certified_positive_ev_bets"], 0)
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual(report["money_wagered_usd"], 0)
            markdown = (Path(temp) / "quotes" /
                        "FULL_STACK_ALL_IN_ONE_REPORT.md").read_text()
            self.assertIn("NCAAF", markdown)
            self.assertIn("Market input readiness by sport", markdown)


if __name__ == "__main__":
    unittest.main()
