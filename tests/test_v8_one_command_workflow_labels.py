"""One-command workflow safety: matching labels and no duplicate forward runs on push."""
import re
import unittest
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from v8_sharp_probability_display import price_pair_probabilities
from v8_sharp_calibration_dashboard import dashboard as calibration_dashboard


class PhoneWorkflowLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=Path(".github/workflows/v8-one-command.yml").read_text(encoding="utf-8")

    def test_daily_research_capture_and_manual_forecast_both_available(self):
        self.assertIn("- cron: '37 20 * * *'", self.text)
        self.assertIn("          - run_nba_forward\n", self.text)

    def test_artifact_name_follows_exact_selected_command(self):
        actual=re.search(r"SELECTED_COMMAND: (\$\{\{[^\n]+\}\})",self.text)
        upload=re.search(r"name: v8-one-command-(\$\{\{[^\n]+\}\})-\$\{\{ github.run_id \}\}",self.text)
        self.assertIsNotNone(actual)
        self.assertIsNotNone(upload)
        self.assertEqual(actual.group(1),upload.group(1))
        self.assertIn("github.event_name == 'push' && 'run_nba_grade'",actual.group(1))
        self.assertNotIn("github.event_name == 'push' && 'run_nba_forward'",actual.group(1))

    def test_pushing_code_does_not_manufacture_another_pregame_forecast(self):
        line=next(x for x in self.text.splitlines() if x.startswith("    if: github.event_name == 'workflow_dispatch'"))
        self.assertIn("'push'",line)
        self.assertIn("'workflow_dispatch'",line)
        self.assertIn("'schedule'",line)
        self.assertIn("github.event_name == 'push' && 'run_nba_grade'",self.text)
        self.assertNotIn("github.event_name == 'push' && 'run_nba_forward'",self.text)

    def test_grade_command_can_be_run_from_phone_and_daily_automatically(self):
        self.assertIn("          - run_nba_grade\n",self.text)
        self.assertIn("- cron: '53 13 * * *'",self.text)
        self.assertIn("--nba-grade-archives-dir saved_nba_forward_archives",self.text)


    def test_manual_default_is_all_eight_sports_not_model_status(self):
        self.assertRegex(
            self.text,
            r"(?s)workflow_dispatch:\n    inputs:\n      command:.*?default: run")
        self.assertIn("          - run\n", self.text)
        self.assertIn("          - run_all\n", self.text)
        self.assertIn("          - run_nfl_props_edge\n", self.text)
        self.assertIn("          - run_mixed_market\n", self.text)
        self.assertIn("inputs.command || 'run'", self.text)
        self.assertIn("github.event.schedule == '23 9 * * 0' && 'run_all'", self.text)
        self.assertNotIn("default: model_status", self.text)

    def test_nfl_props_one_click_workflow_runs_exact_command(self):
        dedicated=Path(".github/workflows/v8-nfl-player-props-edge.yml").read_text()
        self.assertIn("  workflow_dispatch:\n", dedicated)
        self.assertIn("--command run_nfl_props_edge", dedicated)
        self.assertIn("--sharp-archive-dir saved_sharp_archives", dedicated)
        self.assertIn("--workflow collect-sharpapi.yml", dedicated)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", dedicated)
        self.assertIn("    branches: [main]", dedicated)
        self.assertIn("      - 'SHARP_EDGE_RERUN_REQUEST.md'", dedicated)
        self.assertIn("actions: read", dedicated)
        self.assertIn("cancel-in-progress: false", dedicated)
        self.assertNotIn("SHARPAPI_KEY", dedicated)
        self.assertNotIn("python collector.py", dedicated)
        self.assertNotIn("default: model_status", dedicated)
        self.assertNotIn("run_edge --edge-input", dedicated)
        self.assertIn("      - 'v8_sharp_player_props.py'", dedicated)
        self.assertIn("      - 'tests/test_v8_sharp_player_props.py'", dedicated)
        self.assertIn("**Name-only provider quotes (IDs missing; unverified athletes):**", dedicated)


    def _full_game_inline_summary(self):
        """Extract actual GitHub Actions heredoc, not a copied test substitute."""
        dedicated=Path(".github/workflows/v8-nfl-player-props-edge.yml").read_text()
        before, marker, after=dedicated.partition("          python - <<'PY'\n")
        self.assertTrue(marker, "missing Python summary block")
        source, marker, _=after.partition("\n          PY")
        self.assertTrue(marker, "missing Python summary block terminator")
        return textwrap.dedent(source)

    def test_full_game_phone_summary_python_compiles(self):
        code=self._full_game_inline_summary()
        compile(code,"v8-nfl-props-inline-summary.py","exec")
        self.assertIn("today_game_market_board",code)
        self.assertIn("**Decision: PASS / HOLD",code)

    def test_full_game_phone_summary_displays_all_markets_and_never_certifies(self):
        code=self._full_game_inline_summary()
        game={
            "away_team":"Away Club","home_team":"Home Club",
            "paired_primary_markets":{
                "moneyline":{
                    "home_or_over_odds":-140,"away_or_under_odds":120,
                    "home_or_over_line":None,"away_or_under_line":None},
                "point_spread":{
                    "home_or_over_odds":-110,"away_or_under_odds":-110,
                    "home_or_over_line":-2.5,"away_or_under_line":2.5},
                "total_points":{
                    "home_or_over_odds":-115,"away_or_under_odds":-105,
                    "home_or_over_line":220.5,"away_or_under_line":220.5},
            },
        }
        def odds_implied(v):
            return 100 / (v+100) if v > 0 else abs(v) / (abs(v)+100)
        for market in game["paired_primary_markets"].values():
            market.update(price_pair_probabilities(
                odds_implied(market["home_or_over_odds"]),
                odds_implied(market["away_or_under_odds"])))
        prop={
            "player_name":"Sample Athlete","prop_stat":"player_points","line":24.5,
            "over_american_odds":-125,"under_american_odds":105,
            **price_pair_probabilities(odds_implied(-125), odds_implied(105)),
        }
        payload={
            "command":"run_nfl_props_edge","certified_positive_ev_bets":0,
            "sharp_archive":{"archive_run_ids":[123]},
            "sharp_edge_calibration":calibration_dashboard(None),
            "sharp_edge_clv":{
                "status":"HOLD_NO_TRACKED_ENTRY_AND_AUTHENTIC_CLOSING_QUOTE",
                "realized_clv_percent":None,
                "market_repricing_is_verified_clv":False,
                "exact_market_entry_close_pairs":0,
                "archived_provider_market_repricing_observations":0,
                "champion_001_modified":False},
            "sharp_player_props":{
                "valid_provider_name_only_quote_observations_research_only":2,
                "today_player_prop_market_probability_board":{
                    "nba":[prop],"nfl":[]}},

            "sharp_full_game_markets":{
                "today_recent_upcoming_full_games":1,
                "today_recent_upcoming_market_movement_observations":0,
                "validated_source_quote_observations_by_league_and_market":{
                    "nba_moneyline":2,"nba_point_spread":2,"nba_total_points":2},
                "today_game_market_board":[game]},
            "nfl_and_player_props_edge_research":{
                "certified_positive_ev_bets":0,"champion_001_modified":False},
        }
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/"v8_results/nfl_props_edge/ONE_COMMAND_REPORT.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps(payload))
            result=subprocess.run([sys.executable,"-c",code],cwd=folder,
                                  capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("Away Club @ Home Club",result.stdout)
            self.assertIn("-140 / +120",result.stdout)
            self.assertIn("-2.5 / +2.5",result.stdout)
            self.assertIn("+220.5 / +220.5",result.stdout)
            self.assertIn("Sharp Edge Probability View",result.stdout)
            self.assertIn("50.00% / 50.00%",result.stdout)
            self.assertIn("Sample Athlete",result.stdout)
            self.assertIn("Model p / EV",result.stdout)
            self.assertIn("Closing Line Value (CLV)",result.stdout)
            self.assertIn("Realized CLV: UNAVAILABLE / HOLD",result.stdout)
            self.assertIn("Sharp Edge Calibration",result.stdout)
            self.assertIn("Unknown (no verified pair source)",result.stdout)
            self.assertIn("N/A / HOLD",result.stdout)
            self.assertIn("HOLD",result.stdout)
            payload["certified_positive_ev_bets"]=1
            report.write_text(json.dumps(payload))
            blocked=subprocess.run([sys.executable,"-c",code],cwd=folder,
                                   capture_output=True,text=True,timeout=10)
            self.assertNotEqual(blocked.returncode,0)
            self.assertIn("research_run_cannot_be_promoted_to_certified",blocked.stderr)



    def test_v8_one_command_probability_inline_summary_compiles(self):
        """Guard the actual phone report Python without brittle newline escaping."""
        workflow=Path(".github/workflows/v8-one-command.yml").read_text()
        part=workflow.split(
            "- name: Present report directly in phone run summary",1)[1]
        lines=part.splitlines()
        start=next(i for i,line in enumerate(lines)
                   if line.strip()=="python - <<'PY'")
        finish=next(i for i,line in enumerate(lines[start+1:],start+1)
                    if line.strip()=="PY")
        code=textwrap.dedent("\n".join(lines[start+1:finish]))
        compile(code,"v8-one-command-inline-summary.py","exec")
        self.assertIn("NBA/NFL Sharp Edge",code)
        self.assertIn("O/U no-vig",code)
        self.assertIn("Native calibrated model probability: UNAVAILABLE",code)
        self.assertIn("Sharp Edge Calibration Status",code)
        self.assertIn("minimum",code.lower())


if __name__ == "__main__":
    unittest.main()
