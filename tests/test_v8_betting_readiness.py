"""Exact-market betting-readiness command: trace progress without bogus certification."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v8_betting_readiness import audit_betting_readiness, MARKETS, save_readiness
from v8_one_command import execute, selected

NOW = datetime(2026, 11, 12, 20, tzinfo=timezone.utc)


class BettingReadinessTests(unittest.TestCase):
    def test_missing_evidence_never_claims_a_cleared_gate(self):
        r = audit_betting_readiness(now=NOW)
        self.assertEqual(r["decision"],"PASS_HOLD_NO_CERTIFIED_BETS")
        self.assertEqual(len(r["by_market"]),28)
        self.assertEqual(set(r["by_market"]),set(MARKETS))
        self.assertIsNone(r["research_forward"]["published_outcomes_graded"])
        self.assertIsNone(r["research_forward"]["additional_graded_needed_for_first_metrics"])
        self.assertEqual(r["archive_price_context"]["archived_quote_rows_read"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertFalse(r["bet_ready"])
        self.assertEqual(r["by_market"]["ncaaf_moneyline"]["market_input_stage"],
                         "NO_SAVED_PROVIDER_QUOTES")
        self.assertIn("no_saved_provider_quotes_for_league",
                      r["by_market"]["ncaaf_player_props"]["blockers"])
        for market in r["by_market"].values():
            self.assertEqual(market["market_specific_ev_certified"],0)
            self.assertFalse(market["native_probability_validated_for_exact_market"])

    def test_real_persisted_research_counts_are_scoped_to_nba_home_win(self):
        calibration = {
            "status":"HOLD_WAITING_FOR_100_FORWARD_GRADED_AND_WELL_POPULATED_BINS",
            "archived_original_forward_forecasts":28,
            "graded_research_NBA_games":8,"pending_ungraded":20,
            "certified_positive_ev_bets":0,"bet_ready":False,
        }
        with patch("v8_betting_readiness.read_calibration",return_value=calibration):
            r=audit_betting_readiness(now=NOW,sharp_run_ids=[1001,1002])
        research=r["research_forward"]
        self.assertEqual(research["additional_graded_needed_for_first_metrics"],42)
        self.assertEqual(research["additional_graded_needed_for_exploratory_calibration"],92)
        self.assertEqual(research["awaiting_grade"],20)
        self.assertEqual(r["by_market"]["nba_moneyline"]["research_forward_grades_nba_home_win_only"],8)
        for m in set(MARKETS)-{"nba_moneyline"}:
            self.assertIsNone(r["by_market"][m]["research_forward_grades_nba_home_win_only"])
        self.assertFalse(research["research_calibration_independently_certified"])
        self.assertEqual(r["archive_price_context"]["saved_sharpapi_runs"],[1001,1002])

    def test_even_a_published_aggregator_line_does_not_certify_ev(self):
        game = {
            "champion_001_modified":False,"certified_positive_ev_bets":0,
            "today_recent_upcoming_full_games":1,
            "today_game_market_board":[{"league":"nfl",
                "paired_primary_markets":{"moneyline":{"source_book_label":"draftkings"},
                    "point_spread":{"home_or_over_line":-2.5}}}],
        }
        props = {
            "champion_001_modified":False,"certified_positive_ev_bets":0,
            "today_recent_two_sided_prop_markets":1,
            "today_player_prop_market_probability_board":{"nfl":[{"line":210.5}],"nba":[]},
        }
        with (patch("v8_betting_readiness.summarize_full_game_markets",return_value=(game,[])),
              patch("v8_betting_readiness.summarize_player_props",return_value=(props,[]))):
            r=audit_betting_readiness(now=NOW)
        self.assertEqual(r["by_market"]["nfl_point_spread"]["recent_aggregator_two_sided_examples_displayed"],1)
        self.assertEqual(r["by_market"]["nfl_player_props"]["recent_aggregator_two_sided_examples_displayed"],1)
        self.assertEqual(r["archive_price_context"]["recent_upcoming_two_sided_player_prop_reference_markets"],1)
        self.assertEqual(r["independently_verified_checkout_prices"],0)
        self.assertFalse(r["bet_ready"])

    def test_untrusted_claims_and_bad_source_shapes_are_blocked(self):
        fake={"status":"fake","archived_original_forward_forecasts":28,
              "graded_research_NBA_games":8,"pending_ungraded":20,
              "certified_positive_ev_bets":0,"bet_ready":True}
        with patch("v8_betting_readiness.read_calibration",return_value=fake):
            with self.assertRaisesRegex(ValueError,"unsupported_certification"):
                audit_betting_readiness(now=NOW)
        with self.assertRaisesRegex(ValueError,"timezone"):
            audit_betting_readiness(now=datetime(2026,11,12,20))
        with self.assertRaisesRegex(ValueError,"run_ids"):
            audit_betting_readiness(now=NOW,sharp_run_ids=[True])
        with self.assertRaisesRegex(ValueError,"must_be_list"):
            audit_betting_readiness(now=NOW,sharp_rows={})

    def test_one_command_output_runs_with_no_external_api(self):
        self.assertEqual(selected("run_readiness"),())
        with tempfile.TemporaryDirectory() as folder:
            result=execute("run_readiness",now=NOW,output_dir=folder)
            self.assertEqual(result["certified_positive_ev_bets"],0)
            self.assertFalse(result["betting_readiness"]["bet_ready"])
            path=Path(folder)/"BETTING_READINESS.json"
            self.assertTrue(path.is_file())
            self.assertEqual(json.loads(path.read_text())["decision"],"PASS_HOLD_NO_CERTIFIED_BETS")
            self.assertTrue((Path(folder)/"ONE_COMMAND_REPORT.json").is_file())

    def test_ncaaf_archived_rows_are_not_fresh_paired_or_qualified(self):
        source = [{"league": "ncaaf", "source": "sharpapi_rest",
                   "record_type": "pregame_odds_observation",
                   "market_type": "moneyline"}]
        r = audit_betting_readiness(now=NOW, sharp_rows=source)
        self.assertEqual(
            r["archive_price_context"]
            ["archived_provider_quote_rows_by_league_unverified"]["ncaaf"], 1)
        self.assertEqual(
            r["by_market"]["ncaaf_moneyline"]["market_input_stage"],
            "ARCHIVED_NOT_RECENT_PAIRED")
        self.assertEqual(r["by_market"]["ncaaf_player_props"]
                         ["market_specific_ev_certified"], 0)
        self.assertFalse(r["bet_ready"])

    def test_no_symlink_report_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            real=Path(folder)/"real.json"
            real.write_text("original")
            bad=Path(folder)/"linked.json"
            bad.symlink_to(real)
            with self.assertRaisesRegex(ValueError,"unsafe_readiness_report_destination"):
                save_readiness({"x":1},bad)
            self.assertEqual(real.read_text(),"original")


if __name__=="__main__":
    unittest.main()
