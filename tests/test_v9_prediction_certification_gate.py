"""Offline safety tests for the V9 original-evidence certification gap auditor."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from v9_prediction_certification_gate import inspect, markdown, archive_report


def board():
    return {
        "classification": "RESEARCH_ONLY_HOLD", "champion_001_modified": False,
        "source_manifest": {"schedule": {
            "status": "READ_EXISTING_ARCHIVE_ONLY", "run_id": 123,
            "run_created_at_utc": "2026-11-18T11:00:00+00:00"}},
        "game_and_prop_display_rows": [{
            "league": "nba", "game": "Example Away @ Example Home",
            "category": "NBA ML", "market": "home_moneyline",
            "selection": "Example Home", "american_odds_attributed_unverified": -120,
            "uncalibrated_research_rule_percent_not_champion": 75.0,
            "certified_native_model_probability_percent": 92.0,
            "certified_ev_percent": 80.0,
            "evidence": {"run_id": 99, "json_array_pointer": "/rows/0"},
        }],
        "certified_positive_ev_count_by_this_board": 500,
    }


def meeting():
    return {
        "meeting_utc": "2026-11-18T11:30:00+00:00",
        "champion_001_modified": False, "final_team_decision": "HOLD",
        "source_run_id": 123, "pregame_games": [{
            "event_id": "789", "game": "Example Away @ Example Home",
            "league": "NBA", "start_utc": "2026-11-18T12:00:00+00:00",
            "source_observed_utc": "2026-11-18T11:01:00+00:00",
            "start_eastern": "2026-11-18T07:00:00-05:00",
            "source_run_id": 123,
            "proposed_prediction": "Example Home",
            "model_probability": 0.99, "verified_odds": -120,
            "certified_ev": 0.80,
        }],
    }


class CertificationReadinessTests(unittest.TestCase):
    def test_name_matches_and_forged_upstream_ev_cannot_certify(self):
        report = inspect(board(), meeting())
        self.assertEqual(report["final_team_decision"], "HOLD")
        self.assertEqual(report["certified_predictions"], 0)
        self.assertEqual(report["certified_positive_ev"], 0)
        self.assertEqual(report["qualified_parlays"], 0)
        self.assertEqual(report["qualified_shadow_predictions"], 0)
        self.assertEqual(report["automated_wagers"], 0)
        self.assertEqual(report["paid_api_requests"], 0)
        game = report["game_reviews"][0]
        self.assertEqual(game["name_only_research_market_count"], 1)
        self.assertEqual(game["decision"], "HOLD")
        self.assertFalse(game["name_only_market_identity_verified"])
        self.assertFalse(game["qualified_shadow_prediction"])
        self.assertIsNone(game["certified_expected_value"])
        self.assertIsNone(game["native_champion_001_probability"])
        self.assertIsNone(game["executable_draftkings_odds"])
        self.assertEqual(len(game["certification_evidence_gates"]), 8)
        self.assertEqual(len(report["six_employee_reviews"]), 6)

    def test_self_signed_champion_claims_cannot_authorize_a_pick(self):
        champion = {"data": {"original_executable_verified": True,
                             "immutable_model_version_authenticated": True,
                             "result": "approved"},
                    "downloaded_sha256": "a" * 64}
        release = {"data": {"release_decision": "CERTIFIED"},
                   "downloaded_sha256": "b" * 64}
        review = inspect(board(), meeting(), champion=champion, release=release)
        ctx = review["upstream_research_context_not_approval"]
        self.assertTrue(ctx["champion_original_executable_reported"])
        self.assertFalse(ctx["champion_provenance_independently_authenticated_here"])
        self.assertFalse(ctx["independent_release_approval_verified_here"])
        self.assertEqual(review["final_team_decision"], "HOLD")

    def test_stale_source_and_mismatch_do_not_pass(self):
        b = board()
        b["source_manifest"]["schedule"]["run_created_at_utc"] = "2026-11-18T07:00:00Z"
        r = inspect(b, meeting())
        self.assertEqual(r["research_source_status"], "SOURCE_STALE_OR_FUTURE")
        self.assertEqual(r["certified_predictions"], 0)
        b["source_manifest"]["schedule"]["run_id"] = 999
        r = inspect(b, meeting())
        self.assertEqual(r["research_source_status"], "MEETING_ARCHIVE_RUN_MISMATCH")

    def test_reject_modified_champion_and_unapproved_meeting(self):
        b = board()
        b["champion_001_modified"] = True
        with self.assertRaises(ValueError):
            inspect(b, meeting())
        m = meeting()
        m["final_team_decision"] = "CERTIFIED"
        with self.assertRaises(ValueError):
            inspect(board(), m)

    def test_reject_duplicate_and_post_tipoff(self):
        m = meeting()
        m["pregame_games"].append(dict(m["pregame_games"][0]))
        with self.assertRaises(ValueError):
            inspect(board(), m)
        m = meeting()
        m["pregame_games"][0]["start_utc"] = "2026-11-18T11:00:00Z"
        with self.assertRaises(ValueError):
            inspect(board(), m)

    def test_no_games_does_not_mean_failed_bet(self):
        m = meeting()
        m["pregame_games"] = []
        report = inspect(board(), m)
        self.assertEqual(report["game_reviews"], [])
        self.assertIn("No pregame event", markdown(report))
        self.assertEqual(report["final_team_decision"], "HOLD")

    def test_original_archive_bytes_hash_only_not_signature(self):
        with TemporaryDirectory() as root:
            p = Path(root) / "model_completion"
            p.mkdir()
            (p / "champion_authentication.json").write_text(
                json.dumps({"original_executable_verified": True}), encoding="utf-8")
            doc = archive_report(root, "model_completion/champion_authentication.json")
            self.assertEqual(len(doc["downloaded_sha256"]), 64)
            self.assertFalse(doc["original_independent_source_authentication"])
            self.assertTrue(doc["data"]["original_executable_verified"])


if __name__ == "__main__":
    unittest.main()
