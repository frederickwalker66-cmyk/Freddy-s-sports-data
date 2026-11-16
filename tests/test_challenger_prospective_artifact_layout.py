"""Regression tests for root-vs-nested GitHub Actions prospective archives."""
from pathlib import Path
import tempfile
import unittest

from challenger_prospective_artifact_layout import normalize_archive, REQUIRED


class ProspectiveArtifactLayoutTests(unittest.TestCase):
    @staticmethod
    def fixture(root, *, nested=True, complete=True, run_id="43794201623"):
        folder = Path(root) / run_id
        data = folder / "prospective_pregame" if nested else folder
        data.mkdir(parents=True)
        for name in REQUIRED[:3 if complete else 2]:
            (data / name).write_text("original-source-bytes", encoding="utf-8")
        if nested:
            (data / "historical_detail.json").write_text("not-a-market-price")
        # Real multi-path upload creates sibling files as well.
        (folder / "prospective_pregame_source_receipts.json").write_text("{}")
        return folder

    def test_multi_root_upload_is_flattened_without_modifying_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            self.assertEqual(normalize_archive(root,root.name),"flattened")
            self.assertFalse((root/"prospective_pregame").exists())
            for name in REQUIRED:
                self.assertEqual((root/name).read_bytes(),b"original-source-bytes")
            self.assertEqual((root/"historical_detail.json").read_text(),
                             "not-a-market-price")
            self.assertEqual((root/"prospective_pregame_source_receipts.json").read_text(),"{}")
            self.assertEqual(normalize_archive(root,root.name),"already_flat")

    def test_original_single_root_upload_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.fixture(d,nested=False)
            self.assertEqual(normalize_archive(folder,folder.name),"already_flat")

    def test_missing_receipt_does_not_create_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.fixture(d,complete=False)
            with self.assertRaisesRegex(ValueError,"incomplete_nested"):
                normalize_archive(folder,folder.name)
            self.assertFalse((folder/REQUIRED[0]).exists())
            self.assertTrue((folder/"prospective_pregame"/REQUIRED[0]).exists())

    def test_mixed_source_structure_rejected_not_merged(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.fixture(d)
            (folder/REQUIRED[0]).write_text("other-run")
            with self.assertRaisesRegex(ValueError,"ambiguous_mixed"):
                normalize_archive(folder,folder.name)
            self.assertEqual((folder/REQUIRED[0]).read_text(),"other-run")

    def test_bad_run_directory_and_untrusted_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.fixture(d)
            with self.assertRaisesRegex(ValueError,"expected_numeric"):
                normalize_archive(folder,"other")
            (folder/"prospective_pregame"/"extra_symlink").symlink_to(
                folder/"prospective_pregame"/REQUIRED[0])
            with self.assertRaisesRegex(ValueError,"symlinked"):
                normalize_archive(folder,folder.name)

    def test_empty_download_directory_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/"12345"
            folder.mkdir()
            with self.assertRaisesRegex(ValueError,"incomplete_original"):
                normalize_archive(folder,"12345")


if __name__=="__main__":
    unittest.main()
