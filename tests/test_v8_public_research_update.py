"""Prohibit misleading claims in public Freddy's Picks AI updates."""
import unittest
from v8_public_research_update import safe_public_update


def report():
    return {
        "champion_001_modified": False,
        "certified_predictions": 0, "certified_positive_ev_bets": 0,
        "automated_wagers": 0, "bet_ready": False,
        "milestone_a_nba": {"independently_complete": False, "research_model_fitted": False},
        "milestone_b_all_eight": {"independently_complete": False, "research_models_fitted": []},
    }


class PublicResearchTests(unittest.TestCase):
    def test_no_data_produces_truthful_caption(self):
        result = safe_public_update(report(), "2026-11-06")
        self.assertIn("Certified positive-EV selections: 0", result["caption"])
        self.assertIn("NOT COMPLETE", result["caption"])
        self.assertFalse(result["automated_posting"])

    def test_no_unverified_picks_can_be_laundered(self):
        data = report()
        data["certified_positive_ev_bets"] = 3
        with self.assertRaisesRegex(ValueError, "unsupported_certification_claim"):
            safe_public_update(data, "2026-11-06")

    def test_refuse_claim_of_completed_milestone(self):
        data = report()
        data["milestone_a_nba"]["independently_complete"] = True
        with self.assertRaisesRegex(ValueError, "external_release_verification_required"):
            safe_public_update(data, "2026-11-06")

    def test_reject_unsupported_sports_and_duplicates(self):
        for models in (["ufc"], ["nba", "nba"]):
            with self.subTest(models=models):
                data = report()
                data["milestone_b_all_eight"]["research_models_fitted"] = models
                with self.assertRaisesRegex(ValueError, "unrecognized_research_model"):
                    safe_public_update(data, "2026-11-06")


if __name__ == "__main__":
    unittest.main()
