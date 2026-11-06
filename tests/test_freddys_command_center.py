"""Offline phone control center validation: never call external paid sources."""
from datetime import datetime, timezone
import unittest
from freddys_command_center import approve, compose, latest, markdown, WATCH
NOW = datetime(2026, 11, 6, 21, 0, tzinfo=timezone.utc)
def run(n, conclusion="success", event="schedule", status="completed", branch="main"):
    return {"id": n, "created_at": "2026-11-06T20:00:00Z",
            "status": status, "conclusion": conclusion, "event": event,
            "head_branch": branch}
class MobileControlTests(unittest.TestCase):
    def test_paid_live_requires_explicit_separate_confirmation(self):
        with self.assertRaisesRegex(ValueError,"paid_API_requires"):
            approve("nba_live_paid", False)
        with self.assertRaisesRegex(ValueError,"paid_API_requires"):
            approve("sportsdataio_paid", False)
        self.assertEqual(approve("nba_live_paid", True), ("nba-live-connection.yml",))
    def test_unknown_command_does_not_dispatch(self):
        with self.assertRaisesRegex(ValueError,"allowlisted"):
            approve("untrusted.yml", True)
        with self.assertRaisesRegex(ValueError,"allowlisted"):
            approve("nba_live_paid", "true")
    def test_free_diagnostic_does_not_call_paid_sources(self):
        checks=approve("all_free_diagnostics",False)
        self.assertEqual(len(checks),3)
        self.assertNotIn("nba-live-connection.yml", checks)
        self.assertNotIn("sportsdataio-research-intake.yml", checks)
        self.assertNotIn("collect-sharpapi.yml", checks)
    def test_pr_and_non_main_are_not_current_production(self):
        a=run(11)
        b=run(12,event="pull_request")
        c=run(13,branch="feature")
        self.assertEqual(latest({"workflow_runs":[a,b,c]})["run_id"],11)
    def test_failure_is_not_masked_as_success(self):
        s=latest({"workflow_runs":[run(2,conclusion="failure")]})
        self.assertEqual(s["status"],"job_failed_or_cancelled")
        s=latest({"workflow_runs":[run(2,conclusion=None,status="in_progress")]})
        self.assertEqual(s["status"],"job_pending_or_running")
    def test_missing_source_is_unknown_not_zero_success(self):
        self.assertEqual(latest({"error":True})["status"],"github_api_unknown")
        self.assertEqual(latest({"workflow_runs":"bad"})["status"],"malformed_response_unknown")
        self.assertEqual(latest({"workflow_runs":[]})["status"],"no_recent_production_run")
    def test_no_model_release_by_software_status(self):
        p={key:{"workflow_runs":[run(500+i)]} for i,key in enumerate(WATCH.values())}
        s=compose(p,False,[],NOW)
        self.assertEqual(s["model_release_status"],"BLOCKED_NOT_CERTIFIED")
        self.assertEqual(s["certified_positive_ev_bets"],0)
        self.assertFalse(s["champion_001_original_authenticated"])
        self.assertFalse(s["champion_001_modified"])
        self.assertFalse(s["branch_protected"])
        self.assertIn("Phone Command Center",markdown(s))
    def test_invalid_time_or_branch_status_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"real_aware_timestamp"):
            compose({},None,[],datetime(2026,11,6,21))
        with self.assertRaisesRegex(ValueError,"branch_protection"):
            compose({},"yes",[],NOW)
if __name__ == "__main__":
    unittest.main()
