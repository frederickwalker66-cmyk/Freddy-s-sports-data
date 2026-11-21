import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from research.challenger_002_receipt_verification import verify

class ReceiptVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = b'{"GameID":123,"Status":"Final"}'
        (self.root / "receipt-1.json").write_bytes(self.raw)
        self.row = {
            "event_id": "game-1", "league": "NBA", "market": "moneyline",
            "event_start_at": "2025-01-02T19:00:00+00:00",
            "observed_at": "2025-01-02T18:00:00+00:00",
            "source_observed_at": "2025-01-02T17:59:00+00:00",
            "outcome_observed_at": "2025-01-02T23:00:00+00:00",
            "source_provider": "SportsDataIO", "source_record_id": "receipt-1",
            "source_payload_sha256": hashlib.sha256(self.raw).hexdigest(),
            "outcome": 1, "features": {"home_elo": 1500.0}
        }
    def test_matching_digest_still_not_authenticated(self):
        r = verify([self.row], self.root)
        self.assertEqual(r["status"], "LOCAL_DIGESTS_MATCH_NOT_AUTHENTICATED")
        self.assertFalse(r["provider_authenticated"])
        self.assertEqual(r["certified_take_count"], 0)
    def test_mismatch_blocks(self):
        row = dict(self.row, source_payload_sha256="0"*64)
        self.assertEqual(verify([row], self.root)["status"], "BLOCKED")
    def test_missing_receipt_blocks(self):
        row = dict(self.row, source_record_id="missing")
        self.assertEqual(verify([row], self.root)["status"], "BLOCKED")
    def test_path_traversal_blocks(self):
        row = dict(self.row, source_record_id="../secret")
        self.assertEqual(verify([row], self.root)["status"], "BLOCKED")
    def test_empty_batch_blocks(self):
        self.assertEqual(verify([], self.root)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
