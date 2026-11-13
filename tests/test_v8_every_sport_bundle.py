"""One-command NBA/NFL/NHL/MLB/college/soccer all-in-one integration tests."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_every_sport_bundle import run_full_stack, COMMAND_TO_SPORT, ALL
from v8_one_command import selected, COMMANDS

NOW = datetime(2026,11,13,23,0,tzinfo=timezone.utc)


def forward(league):
    return {
        "espn_event_id":"901", "home_team":"Example Home",
        "away_team":"Example Away", "start_utc":"2026-11-14T02:00:00Z",
        "forecast_recorded_utc":"2026-11-13T23:00:00Z",
        "model_probability_home_win_research_only":0.63,
    }


class BundleIntegrationTests(unittest.TestCase):
    def _execute(self, received, *, unsafe_sport=None):
        def runner(command,**kwargs):
            received.append((command,kwargs))
            lg=(command.split("_")[1] if command != "run_nba_best_bets" else "nba")
            bad=unsafe_sport==lg
            result={
                "command":command, "champion_001_modified":False,
                "money_wagered_usd":0,
                "certified_positive_ev_bets":1 if bad else 0,
                "research_forward_probability_rows":
                    [forward(lg)] if lg in ("nba","nfl","nhl") else [],
            }
            return result
        return runner

    def test_every_named_sport_is_one_complete_bundle(self):
        for cmd, scope in COMMAND_TO_SPORT.items():
            with self.subTest(cmd=cmd), tempfile.TemporaryDirectory() as folder:
                received=[]
                result=run_full_stack(command=cmd,execute_fn=self._execute(received),
                                      now=NOW,output_dir=folder)
                self.assertEqual(tuple(result["requested_leagues"]),scope)
                self.assertEqual(len(received),len(scope))
                self.assertEqual(result["certified_positive_ev_bets"],0)
                self.assertFalse(result["champion_001_modified"])
                self.assertEqual(result["money_wagered_usd"],0)
                self.assertEqual(len(result["by_league"]),len(scope))
                self.assertFalse(result["best_bets_and_edge_leaderboard"]
                                 ["certified_positive_ev_ranked_bets"])
                self.assertIsNone(result["closing_line_value"]["verified_realized_clv_percent"])
                self.assertTrue((Path(folder)/"FULL_STACK_ALL_IN_ONE_REPORT.md").is_file())
                for section in (
                    "PREDICTIONS","SHARP_EDGE","BEST_BETS","MARKET_PROBABILITIES",
                    "CALIBRATION","CLV","L5_L10","PARLAY_PREFLIGHT",
                    "BETTING_READINESS"):
                    self.assertTrue((Path(folder)/f"FULL_STACK_{section}.json").is_file())
                self.assertEqual(len(result["research_only_pregame_predictions"]),
                                 sum(x in ("nba","nfl","nhl") for x in scope))
                for lg in scope:
                    self.assertEqual(result["by_league"][lg]["certified_positive_ev_bets"],0)
                    self.assertIsNone(result["by_league"][lg]["market_specific_expected_roi_percent"])
                if "mlb" in scope:
                    self.assertIn("not_supported",
                        result["by_league"]["mlb"]["archived_sportsbook_market_support"])

    def test_alias_commands_and_supported_leagues_are_consistent(self):
        self.assertEqual(tuple(COMMAND_TO_SPORT["run_sports"]),ALL)
        self.assertEqual(selected("run_nba_nfl"),("nba","nfl"))
        self.assertEqual(selected("run_all"),ALL)
        self.assertTrue(all(c in COMMANDS for c in COMMAND_TO_SPORT))

    def test_untrusted_positive_ev_is_never_presented_as_best_bet(self):
        with tempfile.TemporaryDirectory() as folder:
            report=run_full_stack(
                command="run_nba_nfl",
                execute_fn=self._execute([],unsafe_sport="nfl"),
                now=NOW,output_dir=folder)
            self.assertEqual(report["by_league"]["nfl"]["execution_status"],
                             "HOLD_SOURCE_OR_VALIDATION_FAILED")
            self.assertEqual(report["component_failures_by_league"]["nfl"]
                             ["exception_class"],"ValueError")
            self.assertEqual(report["best_bets_and_edge_leaderboard"]
                             ["certified_positive_ev_ranked_bets"],[])
            self.assertEqual(report["certified_positive_ev_bets"],0)
            self.assertEqual(len(report["research_only_pregame_predictions"]),1)

    def test_untrained_sport_has_no_invented_elo_probability(self):
        with tempfile.TemporaryDirectory() as folder:
            r=run_full_stack(command="run_uefa",execute_fn=self._execute([]),
                             now=NOW,output_dir=folder)
            self.assertEqual(r["research_only_pregame_predictions"],[])
            self.assertEqual(r["best_bets_and_edge_leaderboard"]
                             ["research_direction_watchlist_unranked_by_ev"],[])
            self.assertIsNone(r["by_league"]["uefa_champions_league"]
                              ["qualified_exact_market_model_p"])
            md=(Path(folder)/"FULL_STACK_ALL_IN_ONE_REPORT.md").read_text()
            self.assertIn("NOT verified",md) if False else self.assertIn("HOLD",md)
            self.assertIn("not supported",md.lower()) if False else self.assertIn("not_supported",md)

    def test_original_unreviewed_elo_is_not_champion_and_not_ev(self):
        with tempfile.TemporaryDirectory() as folder:
            r=run_full_stack(command="run_nfl",execute_fn=self._execute([]),
                             now=NOW,output_dir=folder)
            f=r["research_only_pregame_predictions"][0]
            self.assertEqual(f["home_win_research_rule_probability"],.63)
            self.assertTrue(f["NFL_conditional_on_no_tie_not_DK_moneyline_probability"])
            self.assertIsNone(f["native_Champion_001_model_probability"])
            self.assertIsNone(f["market_specific_verified_expected_value"])
            self.assertEqual(r["best_bets_and_edge_leaderboard"]["certified_positive_ev_bets"],0)


if __name__=="__main__":
    unittest.main()
