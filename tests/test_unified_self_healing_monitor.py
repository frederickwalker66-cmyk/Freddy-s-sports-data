import unittest
from research.unified_self_healing_monitor import audit
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
if __name__=="__main__":
    unittest.main()
