"""Offline checks for research-only NBA archived evidence crosscheck."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from challenger_nba_source_evidence_crosscheck import audit

def row(name,digest,second_name=None):
    return {"independent_checks":{kind:{"sources":[
        {"archive_file":name,"sha256":digest},
        {"archive_file":second_name or name,"sha256":digest}]} for kind in
        ("schedule","pregame_features","final_outcome")}}

class CrosscheckTests(unittest.TestCase):
    def test_missing_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=audit([row("missing.json","a"*64)],tmp)
            self.assertEqual(result["source_bytes_matching_declared_hashes"],0)
            self.assertEqual(result["rejected_source_references"],6)
            self.assertEqual(result["qualified_training_examples"],0)

    def test_matching_local_bytes_never_certify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"sample.json").write_bytes(b"synthetic")
            (root/"second.json").write_bytes(b"synthetic")
            result=audit([row("sample.json",hashlib.sha256(b"synthetic").hexdigest(),"second.json")],root)
            self.assertEqual(result["source_bytes_matching_declared_hashes"],6)
            self.assertEqual(result["rejected_source_references"],0)
            self.assertFalse(result["independent_publication_time_verified"])
            self.assertEqual(result["qualified_training_examples"],0)
            self.assertFalse(result["champion_001_modified"])

    def test_reused_archive_cannot_count_as_independent_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"sample.json").write_bytes(b"synthetic")
            result=audit([row("sample.json",hashlib.sha256(b"synthetic").hexdigest())],root)
            self.assertEqual(result["source_bytes_matching_declared_hashes"],3)
            self.assertEqual(result["rejected_source_references"],3)
            self.assertTrue(all(x["reason"]=="duplicate_archive_used_as_independent_source" for x in result["rejections"]))
            self.assertEqual(result["qualified_training_examples"],0)

    def test_wrong_digest_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"sample.json").write_bytes(b"synthetic")
            for name in ("sample.json","../escape.json"):
                result=audit([row(name,"0"*64)],root)
                self.assertEqual(result["source_bytes_matching_declared_hashes"],0)
                self.assertEqual(result["rejected_source_references"],6)

if __name__=="__main__":
    unittest.main()
