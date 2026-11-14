"""A five-leg NBA research request must replay archived game and prop quotes, safely."""
from pathlib import Path
import unittest


class FiveLegResearchTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path(".github/workflows/v8-one-command.yml").read_text()

    def test_five_leg_tag_dispatches_existing_mixed_market_command(self):
        token="github.event_name == 'push' && contains(github.event.head_commit.message, '[run-five-leg]') && 'run_mixed_market'"
        self.assertEqual(self.workflow.count(token), 2)
        self.assertIn("github.event_name == 'push' && 'run_nba_grade'", self.workflow)
        self.assertIn("github.event_name == 'push' && contains(github.event.head_commit.message, '[run-nba]') && 'run_nba_best_bets'", self.workflow)
        self.assertIn("PROBABILITY_SHARP_EDGE_DASHBOARD.md", self.workflow)

    def test_five_leg_tag_loads_sharp_and_calibration_only(self):
        for step in (
            "Retrieve recent completed SharpAPI research archives (no API charges)",
            "Download persisted research leaderboard from dedicated long-lived Git branch",
        ):
            idx=self.workflow.index("- name: "+step)
            condition=self.workflow[idx:self.workflow.index("run: |",idx)]
            self.assertIn("'[run-five-leg]'",condition)
        self.assertNotIn("params+=(--sgo-archive-dir saved_sgo_archives)", self.workflow)
        self.assertNotIn("Retrieve last completed SportsGameOdds source artifact", self.workflow)
        self.assertNotIn("--sgo-archive-dir saved_sgo_archives", self.workflow)
        self.assertNotIn("github.event_name == 'push' && 'run_mixed_market'",self.workflow)


if __name__ == "__main__":
    unittest.main()
