import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
from research.external_source_attestation_gate import canonical, verify

@unittest.skipUnless(CRYPTO_AVAILABLE, 'cryptography is installed in dedicated attestation CI')
class ExternalSourceTests(unittest.TestCase):
    def test_signature_tampering_and_missing_receipts_fail_closed(self):
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipts = {}
            for kind, hour in (("pregame", 15), ("odds", 16), ("outcome", 23)):
                raw = (kind + "-original").encode()
                (root / (kind + ".json")).write_bytes(raw)
                receipts[kind] = {"path": kind + ".json",
                                  "sha256": hashlib.sha256(raw).hexdigest(),
                                  "canonical_game_id": "nba-123",
                                  "received_at_utc": f"2026-11-20T{hour:02}:00:00Z"}
            statement = {"schema": "freddys_external_source_receipt_v1",
                         "league": "nba", "canonical_game_id": "nba-123",
                         "event_start_utc": "2026-11-20T19:00:00Z",
                         "receipts": receipts}
            signed = {"statement": statement,
                      "signature_base64": base64.b64encode(private.sign(canonical(statement))).decode()}
            result = verify(signed, root, public)
            self.assertTrue(result["external_signature_valid"])
            self.assertEqual(result["record_receipts_verified"], 3)
            self.assertEqual(result["qualified_training_rows"], 0)
            self.assertEqual(result["status"], "HOLD")
            self.assertFalse(result["champion_001_modified"])
            signed["statement"]["event_start_utc"] = "2026-11-20T17:00:00Z"
            result = verify(signed, root, public)
            self.assertFalse(result["external_signature_valid"])
            self.assertIn("signature_verification_failed", result["blocking_reasons"])

    def test_untrusted_key_and_unsigned_data_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            result = verify({"statement": {}, "signature_base64": "aGVsbG8="},
                            root, b"not a public key")
            self.assertEqual(result["independently_authenticated_records"], 0)
            self.assertEqual(result["certified_take_predictions"], 0)

if __name__ == "__main__":
    unittest.main()
