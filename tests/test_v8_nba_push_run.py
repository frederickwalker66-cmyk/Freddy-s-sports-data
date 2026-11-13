"""A tagged, explicitly requested NBA-only scan must not change normal push behavior."""
import re
import unittest
from pathlib import Path


class NBAOnDemandWorkflowTests(unittest.TestCase):
    def test_explicit_nba_only_tag_is_available_without_new_paid_api_calls(self):
        text = Path(".github/workflows/v8-one-command.yml").read_text()
        match = re.search(r"SELECTED_COMMAND: (\$\{\{[^\n]+\}\})", text)
        artifact = re.search(
            r"name: v8-one-command-(\$\{\{[^\n]+\}\})-\$\{\{ github.run_id \}\}",
            text)
        self.assertIsNotNone(match)
        self.assertIsNotNone(artifact)
        selector = match.group(1)
        self.assertEqual(selector, artifact.group(1))
        self.assertIn(
            "github.event_name == 'push' && contains(github.event.head_commit.message, '[run-nba]') && 'run_nba_best_bets'",
            selector)
        self.assertLess(selector.index("'[run-nba]'"), selector.index("&& 'run_nba_grade'"))
        self.assertIn("github.event_name == 'push' && 'run_nba_grade'", selector)
        self.assertIn("- run_nba\n", text)
        self.assertIn("PROBABILITY_SHARP_EDGE_DASHBOARD.md", text)
        self.assertIn("NBA_SHARP_EDGE_ALWAYS.md", text)
        self.assertIn("SELECTED_COMMAND=run_nba_best_bets", text)

    def test_nba_tag_does_not_auto_run_forward_model_or_place_wagers(self):
        text = Path(".github/workflows/v8-one-command.yml").read_text()
        self.assertNotIn("github.event_name == 'push' && 'run_nba_forward'", text)
        self.assertIn("Research command to run (no paid API and no bets)", text)


if __name__ == "__main__":
    unittest.main()
