"""Offline checks for immutable-file evidence provenance, not betting clearance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture_evidence_manifest import build_manifest


class EvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = {
            "retrieved_at_utc": "2026-10-29T20:00:00+00:00",
            "game_date_et": "2026-10-29",
            "sources": {"nba": {"status": "evidence_downloaded"},
                        "nba_player_index": {"status": "unavailable"}},
            "player_props_cleared": 0,
            "model_probabilities_generated": 0,
            "champion_001_modified": False,
        }
        (self.root / "nba_injury_report.pdf").write_bytes(b"%PDF-fixture")
        self.write_report()

    def write_report(self):
        (self.root / "source_refresh_report.json").write_text(json.dumps(self.report))

    def manifest(self):
        return build_manifest(self.root,
                now=datetime(2026, 10, 29, 20, 10, tzinfo=timezone.utc))

    def test_hashes_and_source_statuses_stay_research_only(self):
        m = self.manifest()
        files = {x["name"]: x for x in m["file_hashes"]}
        self.assertEqual(files["nba_injury_report.pdf"]["sha256"],
                         hashlib.sha256(b"%PDF-fixture").hexdigest())
        self.assertEqual(m["source_statuses"]["nba_player_index"], "unavailable")
        self.assertFalse(m["pregame_event_timestamp_alignment_verified"])
        self.assertEqual(m["verified_training_examples"], 0)
        self.assertEqual(m["certified_champion_001_predictions"], 0)
        self.assertFalse(m["champion_001_modified"])

    def test_reject_naive_and_future_scan_times(self):
        self.report["retrieved_at_utc"] = "2026-10-29T20:00:00"
        self.write_report()
        with self.assertRaises(ValueError):
            self.manifest()
        self.report["retrieved_at_utc"] = "2026-10-30T20:00:00+00:00"
        self.write_report()
        with self.assertRaises(ValueError):
            self.manifest()

    def test_fail_closed_if_bet_or_model_clearance_is_claimed(self):
        self.report["model_probabilities_generated"] = 1
        self.write_report()
        with self.assertRaises(ValueError):
            self.manifest()
        self.report["model_probabilities_generated"] = 0
        self.report["champion_001_modified"] = True
        self.write_report()
        with self.assertRaises(ValueError):
            self.manifest()

    def test_missing_report_is_not_silent_success(self):
        (self.root / "source_refresh_report.json").unlink()
        with self.assertRaises(ValueError):
            self.manifest()


if __name__ == "__main__":
    unittest.main()
