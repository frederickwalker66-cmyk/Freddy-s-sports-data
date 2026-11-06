"""Offline integration tests: no evidence means no trained or certified V8 model."""
import unittest

from v8_dual_milestone_runner import run, load_jsonl


class DualMilestoneIntegrationTests(unittest.TestCase):
    def test_no_evidence_keeps_both_blocked(self):
        report, nba, other = run([], [])
        self.assertIsNone(nba)
        self.assertEqual(other, {})
        self.assertFalse(report["milestone_a_nba"]["research_model_fitted"])
        self.assertEqual(report["milestone_b_all_eight"]["research_models_fitted"], [])
        self.assertFalse(report["milestone_a_nba"]["independently_complete"])
        self.assertFalse(report["milestone_b_all_eight"]["independently_complete"])
        self.assertEqual(report["certified_predictions"], 0)
        self.assertEqual(report["automated_wagers"], 0)
        self.assertFalse(report["bet_ready"])

    def test_nonexistent_evidence_path_does_not_silently_become_empty(self):
        with self.assertRaises(FileNotFoundError):
            load_jsonl("missing_v8_evidence_that_must_not_exist.jsonl")


if __name__ == "__main__":
    unittest.main()
