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
    def test_full_refresh_is_broad_but_free_and_never_automatically_promoted(self):
        refresh=approve("full_refresh_recalibrate",False)
        self.assertEqual(len(refresh),8)
        self.assertEqual(len(set(refresh)),len(refresh))
        self.assertTrue(set(refresh).issubset(set(WATCH.values())))
        for disallowed in ("nba-live-connection.yml",
                           "sportsdataio-research-intake.yml",
                           "collect-sharpapi.yml"):
            self.assertNotIn(disallowed,refresh)
        self.assertIn("challenger-isotonic-calibration.yml",refresh)
        self.assertIn("v8-nfl-player-props-edge.yml",refresh)
        self.assertIn("v8-elite-validation.yml",refresh)
        state=compose({},None,[{"workflow":w,"accepted":True} for w in refresh],NOW)
        self.assertFalse(state["refresh_completion_confirmed"])
        self.assertFalse(state["independent_model_recalibration_certified"])
        self.assertFalse(state["champion_001_modified"])
        self.assertEqual(state["certified_positive_ev_bets"],0)
        self.assertIn("not refresh completion",markdown(state))
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
    def test_stale_scheduled_jobs_are_visible_not_auto_refreshed(self):
        from datetime import timedelta
        payload = {
            "challenger-eight-sport-source-preflight.yml": {
                "workflow_runs":[run(1)]},
            "collect-sharpapi.yml":{
                "workflow_runs":[run(2)]},
        }
        late = NOW + timedelta(days=2)
        report = compose(payload, True, [], late)
        source = report["latest_runs"]["Hourly source capture"]
        odds = report["latest_runs"]["SharpAPI multi-sport"]
        self.assertEqual(source["operational_freshness"],
                         "STALE_LAST_COMPLETED_SUCCESSFUL_JOB")
        self.assertEqual(odds["operational_freshness"],
                         "STALE_LAST_COMPLETED_SUCCESSFUL_JOB")
        self.assertEqual(report["requested_workflow_dispatches"],[])
        view=markdown(report)
        self.assertIn("Stale scheduled-job warning",view)
        self.assertIn("NOT quote freshness",view)
        self.assertIn("Persistent NBA forward grade ledger", view)

    def test_recent_success_not_confused_with_verified_bookmaker_quote(self):
        payload = {"collect-sharpapi.yml":{"workflow_runs":[run(1)]}}
        report = compose(payload, True, [], NOW)
        state = report["latest_runs"]["SharpAPI multi-sport"]
        self.assertEqual(state["operational_freshness"],
                         "RECENT_JOB_NOT_SOURCE_VERIFICATION")
        self.assertEqual(report["direct_draftkings_checkout_quotes_verified"],0)
        self.assertFalse(report["champion_001_modified"])

    def test_old_failed_job_does_not_appear_healthy(self):
        from datetime import timedelta
        payload = {"collect-sharpapi.yml":{
            "workflow_runs":[run(5,conclusion="failure")]}}
        report=compose(payload,None,[],NOW+timedelta(days=2))
        state=report["latest_runs"]["SharpAPI multi-sport"]
        self.assertEqual(state["status"],"job_failed_or_cancelled")
        self.assertEqual(state["operational_freshness"],
                         "NO_RECENT_COMPLETED_SUCCESS_CONFIRMED")

    def test_invalid_time_or_branch_status_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"real_aware_timestamp"):
            compose({},None,[],datetime(2026,11,6,21))
        with self.assertRaisesRegex(ValueError,"branch_protection"):
            compose({},"yes",[],NOW)
if __name__ == "__main__":
    unittest.main()
