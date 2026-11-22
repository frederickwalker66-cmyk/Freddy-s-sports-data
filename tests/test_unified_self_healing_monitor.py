import unittest
from research.unified_self_healing_monitor import audit, transient_log, recover_latest, pipeline_status
from datetime import datetime, timezone
class MonitorTests(unittest.TestCase):
    def test_failure_never_retries_without_proof(self):
        attempts={}
        calls=[]
        runs=[{"path":".github/workflows/prediction-mode.yml","head_branch":"main",
               "status":"completed","conclusion":"failure","id":123,"event":"schedule"}]
        result=audit(runs,attempts,auto_retry=True,retry=calls.append)
        self.assertEqual(calls,[])
        self.assertEqual(result["latest_by_workflow"]["prediction-mode.yml"]["repair"],"manual_review_required")
        self.assertEqual(result["certified_takes"],0)
    def test_other_branch_excluded(self):
        r=audit([{"path":".github/workflows/prediction-mode.yml","head_branch":"feature",
                  "status":"completed","conclusion":"success","id":4}],{})
        self.assertIn("prediction-mode.yml",r["missing_workflows"])
    def test_log_classifier(self):
        self.assertTrue(transient_log("Error: 503 Service Unavailable"))
        self.assertFalse(transient_log("AssertionError: test failed"))
        self.assertFalse(transient_log("Error: permission denied"))
    def test_single_retry_and_no_repeat(self):
        calls=[]
        run={"path":".github/workflows/prediction-mode.yml","head_branch":"main",
             "status":"completed","conclusion":"failure","id":123,"event":"schedule",
             "run_attempt":1,"created_at":"2026-11-22T20:00:00Z"}
        def execute(r):
            return recover_latest([r],"token","owner/repo",
                 now=datetime(2026,11,22,20,10,tzinfo=timezone.utc),
                 get_jobs=lambda _: [{"id":456,"conclusion":"failure"}],
                 get_log=lambda _: "Error: 503 Service Unavailable",
                 rerun=calls.append)
        self.assertEqual(execute(run)[0]["action"],"retry_requested_once")
        self.assertEqual(calls,[123])
        run["run_attempt"]=2
        self.assertEqual(execute(run)[0]["action"],"not_eligible")
        self.assertEqual(calls,[123])
    def test_no_retry_for_failed_assertions(self):
        calls=[]
        run={"path":".github/workflows/prediction-mode.yml","head_branch":"main",
             "status":"completed","conclusion":"failure","id":123,"event":"schedule",
             "run_attempt":1,"created_at":"2026-11-22T20:00:00Z"}
        result=recover_latest([run],"token","owner/repo",
             now=datetime(2026,11,22,20,10,tzinfo=timezone.utc),
             get_jobs=lambda _: [{"id":456,"conclusion":"failure"}],
             get_log=lambda _: "AssertionError: test failed",
             rerun=calls.append)
        self.assertEqual(result[0]["action"],"manual_review")
        self.assertEqual(calls,[])
    def test_pipeline_stages_fail_closed(self):
        runs=[{"path":".github/workflows/prediction-mode.yml","head_branch":"main",
               "created_at":"2026-11-22T20:00:00Z","conclusion":"success","status":"completed","id":2}]
        result=pipeline_status(runs)
        self.assertEqual(result["prediction"]["ci_state"],"PASS")
        self.assertFalse(result["prediction"]["evidence_verified"])
        self.assertFalse(result["prediction"]["certified"])
        self.assertEqual(result["challenger_training"]["ci_state"],"NEEDS_REVIEW")
if __name__=="__main__":
    unittest.main()
