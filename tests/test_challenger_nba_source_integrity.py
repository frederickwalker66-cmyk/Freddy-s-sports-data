"""Offline regression tests for NBA archived-source SHA-256 integrity."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from challenger_nba_source_integrity import verify

class SourceIntegrityTests(unittest.TestCase):
    def test_matching_bytes_are_not_training_certification(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            payload=b"synthetic fixture only"
            (root/"source.json").write_bytes(payload)
            result=verify([{"file":"source.json","sha256":hashlib.sha256(payload).hexdigest()}],root)
            self.assertEqual(result["integrity_matches"],1)
            self.assertEqual(result["qualified_training_examples"],0)
            self.assertFalse(result["independently_authenticated_publication"])

    def test_tampered_bytes_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"source.json").write_bytes(b"changed")
            result=verify([{"file":"source.json","sha256":hashlib.sha256(b"original").hexdigest()}],root)
            self.assertEqual(result["failures"],1)
            self.assertEqual(result["results"][0]["reason"],"source_digest_mismatch")

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            result=verify([{"file":"../secret","sha256":"a"*64}],Path(folder))
            self.assertEqual(result["failures"],1)
            self.assertEqual(result["results"][0]["reason"],"missing_or_unsafe_source_file")

    def test_missing_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            result=verify([{"file":"missing.json","sha256":"a"*64}],Path(folder))
            self.assertEqual(result["failures"],1)

if __name__=="__main__":
    unittest.main()
