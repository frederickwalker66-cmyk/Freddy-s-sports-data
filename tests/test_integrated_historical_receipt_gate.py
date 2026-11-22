import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from research.external_source_attestation_gate import canonical
from research.integrated_historical_receipt_gate import reconcile

@unittest.skipUnless(CRYPTO_AVAILABLE, "cryptography required for signature integration")
class IntegratedEvidenceTests(unittest.TestCase):
    def test_signed_and_local_evidence_match_but_training_stays_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipts = {}
            signed_receipts = {}
            for kind, hour in (("pregame", 14), ("odds", 15), ("outcome", 23)):
                name = kind + ".json"
                data = kind.encode()
                (root / name).write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                receipts[kind] = {"path": name, "sha256": digest}
                signed_receipts[kind] = {**receipts[kind], "canonical_game_id": "game-42",
                    "received_at_utc": f"2026-11-20T{hour:02}:00:00Z"}
            record = {"league": "nba", "event_ids": {k:"game-42" for k in ("historical","pregame","odds","outcome")},
                "event_start_utc":"2026-11-20T19:00:00Z",
                "pregame_received_at_utc":"2026-11-20T14:00:00Z",
                "odds_received_at_utc":"2026-11-20T15:00:00Z",
                "outcome_received_at_utc":"2026-11-20T23:00:00Z",
                "receipts": receipts}
            statement = {"schema":"freddys_external_source_receipt_v1",
                "league":"nba", "canonical_game_id":"game-42",
                "event_start_utc":record["event_start_utc"], "receipts":signed_receipts}
            key = Ed25519PrivateKey.generate()
            public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            bundle = {"statement":statement,"signature_base64":base64.b64encode(key.sign(canonical(statement))).decode()}
            result = reconcile(record,bundle,root,public)
            self.assertTrue(result["external_signature_valid"])
            self.assertTrue(result["local_receipt_integrity_passed"])
            self.assertEqual(result["status"],"HOLD")
            self.assertEqual(result["qualified_training_rows"],0)
            record["odds_received_at_utc"] = "2026-11-20T16:00:00Z"
            changed = reconcile(record,bundle,root,public)
            self.assertIn("signed_statement_odds_receipt_time_mismatch",changed["blocking_reasons"])

if __name__ == "__main__":
    unittest.main()
