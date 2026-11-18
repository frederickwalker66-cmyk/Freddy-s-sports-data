"""Offline, no-network virtual-staff safety tests."""
import unittest

from v9_virtual_staff import STAFF, evaluate, markdown


class VirtualStaffTests(unittest.TestCase):
    def report(self):
        return {
            "repository": "test/repo",
            "created_at_utc": "2026-11-18T10:23:00+00:00",
            "latest_failed_or_cancelled_workflows": [],
            "latest_pending_or_running_workflows": [],
            "stale_successful_workflows": [],
            "latest_runs": {
                name: {"status": "job_success_not_model_certification",
                       "url": "https://github.com/test/repo/actions/runs/123"}
                for _, names in STAFF for name in names
            },
        }

    def test_six_distinct_staff_roles(self):
        board = evaluate(self.report())
        self.assertEqual(len(board["six_roles"]), 6)
        self.assertEqual(len({r["employee"] for r in board["six_roles"]}), 6)

    def test_green_jobs_cannot_certify_bets(self):
        board = evaluate(self.report())
        self.assertEqual(board["certified_positive_ev_from_this_audit"], 0)
        self.assertEqual(board["native_model_forecasts_authenticated_by_this_audit"], 0)
        self.assertEqual(board["verified_executable_draftkings_prices_from_this_audit"], 0)
        self.assertEqual(board["automated_wagers"], 0)
        self.assertEqual(board["paid_api_calls"], 0)
        self.assertEqual(board["shadow_stake_usd"], 0)
        self.assertEqual(board["model_release"], "HOLD_UNVERIFIED")
        self.assertFalse(board["champion_001_change_requested"])
        self.assertTrue(all(e["price_or_model_authentication"] == "NOT_ESTABLISHED_BY_JOB_METADATA"
                            for r in board["six_roles"] for e in r["workflow_evidence"]))

    def test_failure_and_staleness_escalate(self):
        report = self.report()
        report["latest_failed_or_cancelled_workflows"] = ["NBA/NFL Sharp Edge and props"]
        report["stale_successful_workflows"] = ["Hourly source capture"]
        board = evaluate(report)
        self.assertEqual(board["six_roles"][0]["status"], "ACTION_REQUIRED")
        self.assertEqual(board["six_roles"][5]["status"], "ACTION_REQUIRED")
        self.assertIn("Failed/cancelled", markdown(board))
        self.assertIn("Stale", markdown(board))

    def test_missing_sources_remain_unknown(self):
        report = self.report()
        report["latest_runs"] = {}
        board = evaluate(report)
        self.assertEqual(board["six_roles"][1]["status"], "SOURCE_COVERAGE_UNVERIFIED")
        self.assertEqual(board["six_roles"][1]["workflow_evidence"][0]["latest_job_status"], "unknown")

    def test_rejects_malformed_report(self):
        with self.assertRaises(ValueError):
            evaluate(None)


if __name__ == "__main__":
    unittest.main()
