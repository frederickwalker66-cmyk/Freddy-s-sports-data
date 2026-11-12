"""One-command workflow safety: matching labels and no duplicate forward runs on push."""
import re
import unittest
from pathlib import Path


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


    def test_manual_default_is_nfl_props_edge_not_model_status(self):
        self.assertRegex(
            self.text,
            r"(?s)workflow_dispatch:\n    inputs:\n      command:.*?default: run_nfl_props_edge")
        self.assertIn("          - run_nfl_props_edge\n", self.text)
        self.assertIn("inputs.command || 'run_sports'", self.text)
        self.assertNotIn("default: model_status", self.text)

    def test_nfl_props_one_click_workflow_runs_exact_command(self):
        dedicated=Path(".github/workflows/v8-nfl-player-props-edge.yml").read_text()
        self.assertIn("  workflow_dispatch:\n", dedicated)
        self.assertIn("--command run_nfl_props_edge", dedicated)
        self.assertIn("--sharp-archive-dir saved_sharp_archives", dedicated)
        self.assertIn("--workflow collect-sharpapi.yml", dedicated)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", dedicated)
        self.assertIn("    branches: [main]", dedicated)
        self.assertIn("actions: read", dedicated)
        self.assertIn("cancel-in-progress: false", dedicated)
        self.assertNotIn("SHARPAPI_KEY", dedicated)
        self.assertNotIn("python collector.py", dedicated)
        self.assertNotIn("default: model_status", dedicated)
        self.assertNotIn("run_edge --edge-input", dedicated)


if __name__ == "__main__":
    unittest.main()
