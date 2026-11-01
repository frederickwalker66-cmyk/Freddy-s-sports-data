"""Offline tests for archived NBA source inventory (synthetic bytes only)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from challenger_nba_source_inventory import inventory

class ArchiveInventoryTests(unittest.TestCase):
    def test_empty_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(inventory(Path(tmp)), [])

    def test_real_bytes_hashed_without_certification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"snapshot.json").write_bytes(b"synthetic pregame evidence")
            result=inventory(root)
            self.assertEqual(result,[{"file":"snapshot.json",
                "sha256":hashlib.sha256(b"synthetic pregame evidence").hexdigest()}])

    def test_hidden_files_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/".hidden").write_bytes(b"secret")
            (root/"visible.json").write_bytes(b"public")
            self.assertEqual([x["file"] for x in inventory(root)],["visible.json"])

    def test_symlink_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"target.json").write_bytes(b"content")
            (root/"link.json").symlink_to(root/"target.json")
            self.assertEqual([x["file"] for x in inventory(root)],["target.json"])

if __name__=="__main__":
    unittest.main()
