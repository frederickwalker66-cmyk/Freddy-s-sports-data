import unittest
from research.freddys_operational_readiness import assess, REQUIREMENTS

class OperationalReadinessTests(unittest.TestCase):
    def test_no_evidence_is_hold(self):
        result=assess()
        self.assertEqual(result["status"],"HOLD")
        self.assertEqual(result["certified_take_count"],0)
        self.assertEqual(len(result["missing_or_unverified"]),len(REQUIREMENTS))
    def test_self_attested_all_true_still_hold(self):
        result=assess({k:True for k in REQUIREMENTS})
        self.assertEqual(result["status"],"HOLD")
        self.assertEqual(result["certified_take_count"],0)
        self.assertEqual(result["reason"],"INDEPENDENT_VERIFICATION_ENGINE_NOT_CONNECTED")
    def test_malformed_evidence_fails_closed(self):
        self.assertEqual(assess(["unexpected"])["status"],"HOLD")

if __name__=="__main__":
    unittest.main()
