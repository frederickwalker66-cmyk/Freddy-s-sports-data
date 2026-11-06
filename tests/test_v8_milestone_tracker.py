"""V8 milestone reporting remains blocked without independently proven inputs."""
import unittest

from v8_milestone_tracker import build_report, LEAGUES


class MilestoneTrackerTests(unittest.TestCase):
    def test_missing_evidence_never_completes_either_milestone(self):
        report = build_report()
        self.assertFalse(report["milestone_a_nba"]["independently_complete"])
        self.assertFalse(report["milestone_b_eight_sports"]["independently_complete"])
        self.assertEqual(set(report["by_league"]), set(LEAGUES))
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_partial_nba_does_not_complete_milestones(self):
        report = build_report({"nba": {
            "independent_source_and_asof_audit": True,
            "qualified_train_games": 200, "qualified_holdout_games": 50,
            "champion_001_modified": False, "market_scope": "moneyline",
        }})
        self.assertIn("independent_settlement_audit", report["by_league"]["nba"]["blockers"])
        self.assertFalse(report["milestone_a_nba"]["engineering_evidence_checklist_passed"])

    def test_fake_all_green_flags_still_needs_independent_review(self):
        fields = {
            "independent_source_and_asof_audit": True,
            "independent_settlement_audit": True,
            "chronological_untouched_holdout": True,
            "reproducible_model_and_probability_audit": True,
            "calibration_and_market_baseline_review": True,
            "verified_executable_odds": True,
            "independent_release_signoff": True,
            "qualified_train_games": 200,
            "qualified_holdout_games": 50,
            "champion_001_modified": False,
        }
        evidence = {}
        for league in LEAGUES:
            record = dict(fields, market_scope="moneyline")
            if league in ("mls", "uefa_champions_league"):
                record.update(market_scope="three_way_90_minute",
                              three_way_draw_and_regulation_rules_audited=True)
            evidence[league] = record
        report = build_report(evidence)
        self.assertTrue(report["milestone_a_nba"]["engineering_evidence_checklist_passed"])
        self.assertTrue(report["milestone_b_eight_sports"]["engineering_evidence_checklist_passed"])
        self.assertFalse(report["milestone_a_nba"]["independently_complete"])
        self.assertFalse(report["milestone_b_eight_sports"]["independently_complete"])
        self.assertEqual(report["certified_predictions"], 0)
        self.assertFalse(report["bet_ready"])

    def test_soccer_regulation_required(self):
        report = build_report({"mls": {"market_scope": "moneyline"}})
        self.assertIn("soccer_market_scope_mismatch", report["by_league"]["mls"]["blockers"])

    def test_invalid_league_and_counts_rejected(self):
        with self.assertRaises(ValueError):
            build_report({"tennis": {}})
        report = build_report({"nba": {"qualified_train_games": True}})
        self.assertIn("qualified_train_games_below_200", report["by_league"]["nba"]["blockers"])


if __name__ == "__main__":
    unittest.main()
