import hashlib
import tempfile
import unittest
from pathlib import Path
from mlb_nba_record_receipt_verification import inspect, audit

class RecordReceiptTests(unittest.TestCase):
    def test_missing_records_are_hold(self):
        result = audit([], ".")
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["independently_authenticated_records"], 0)
        self.assertFalse(result["champion_001_modified"])
        self.assertFalse(result["nfl_collection_modified"])

    def test_valid_local_receipts_still_require_independent_attestation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipts = {}
            for kind in ("pregame", "odds", "outcome"):
                name = kind + ".json"
                data = ('{"kind":"' + kind + '"}').encode()
                (root / name).write_bytes(data)
                receipts[kind] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            record = {
                "league": "nba",
                "event_ids": {k: "game-123" for k in ("historical", "pregame", "odds", "outcome")},
                "pregame_received_at_utc": "2026-11-20T16:00:00Z",
                "odds_received_at_utc": "2026-11-20T17:00:00Z",
                "event_start_utc": "2026-11-20T19:00:00Z",
                "outcome_received_at_utc": "2026-11-21T01:00:00Z",
                "receipts": receipts,
                "independent_official_outcome_attestation": True,
                "independent_bookmaker_settlement_attestation": True,
                "independent_odds_source_attestation": True,
            }
            result = inspect(record, root)
            self.assertTrue(result["local_receipt_integrity_passed"])
            self.assertIn("external_attestation_signatures_not_verified", result["reasons"])
            self.assertEqual(result["qualified_training_rows"], 0)
            record["odds_received_at_utc"] = "2026-11-20T20:00:00Z"
            self.assertIn("invalid_receipt_chronology", inspect(record, root)["reasons"])
            record["odds_received_at_utc"] = "2026-11-20T17:00:00Z"
            (root / "odds.json").write_text("tampered")
            self.assertIn("hash_mismatch_odds", inspect(record, root)["reasons"])

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            result = inspect({"league":"mlb","receipts":{"pregame":{"path":"../outside","sha256":"0"*64}}},root)
            self.assertIn("missing_or_unsafe_pregame_bytes",result["reasons"])

if __name__ == "__main__":
    unittest.main()
