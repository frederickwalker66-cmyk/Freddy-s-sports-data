import unittest
from research.challenger_002_dataset_audit import audit, REQUIRED_EVIDENCE

class DatasetAuditTests(unittest.TestCase):
    def test_empty_rows_block_even_with_manifest(self):
        manifest={key:True for key in REQUIRED_EVIDENCE}
        manifest.update(auditor="independent",evidence_uri="audit://case-1")
        r=audit([],manifest)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["certified_take_count"],0)
    def test_missing_evidence_blocks(self):
        r=audit([],{})
        self.assertEqual(r["status"],"BLOCKED")
        self.assertIn("EVIDENCE_MISSING_PREGAME_CAPTURE_INDEPENDENTLY_VERIFIED",r["blockers"])
    def test_self_attested_evidence_never_unlocks(self):
        manifest={key:True for key in REQUIRED_EVIDENCE}
        manifest.update(auditor="claimed-auditor", evidence_uri="claimed://receipt")
        result=audit([],manifest)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("INDEPENDENT_EVIDENCE_AUTHENTICATION_NOT_IMPLEMENTED",result["blockers"])

    def test_missing_manifest_blocks(self):
        self.assertIn("MISSING_INDEPENDENT_EVIDENCE_MANIFEST",audit([],None)["blockers"])

if __name__ == "__main__":
    unittest.main()
