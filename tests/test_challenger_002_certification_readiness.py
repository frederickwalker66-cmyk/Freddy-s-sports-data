import unittest
from research.challenger_002_certification_readiness import assess, REQUIRED

class CertificationReadinessTests(unittest.TestCase):
    def test_empty_is_hold(self):
        r=assess()
        self.assertEqual(r["status"],"HOLD")
        self.assertEqual(len(r["missing"]),len(REQUIRED))
        self.assertEqual(r["certified_take_count"],0)
    def test_claim_without_receipt_is_not_verified(self):
        r=assess({k:{"verified":True} for k in REQUIRED})
        self.assertEqual(r["status"],"HOLD")
    def test_all_receipts_still_require_human_review(self):
        r=assess({k:{"verified":True,"receipt_sha256":"a"*64} for k in REQUIRED})
        self.assertEqual(r["status"],"CERTIFICATION_REVIEW_REQUIRED")
        self.assertFalse(r["automated_certification_granted"])
        self.assertEqual(r["certified_take_count"],0)

if __name__=="__main__":
    unittest.main()
