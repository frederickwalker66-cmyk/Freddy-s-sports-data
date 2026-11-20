"""Fail-closed regression checks for frozen Champion-001 evidence authentication."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from champion_001_authentication import inspect


class ChampionAuthenticationTests(unittest.TestCase):
    def test_missing_artifact_and_proof_are_reported(self):
        report = inspect()
        self.assertEqual(report["missing_evidence"], [
            "original_champion_model_artifact",
            "independently_custodied_proof_manifest",
        ])
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_malformed_manifest_does_not_crash_or_certify(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "candidate.bin"
            proof = Path(tmp) / "proof.json"
            model.write_bytes(b"test candidate, not an original model")
            proof.write_text("[]", encoding="utf-8")
            report = inspect(model, proof)
            self.assertEqual(report["result"], "blocked_invalid_proof_manifest")
            self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_matching_self_supplied_hash_is_not_independent_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "candidate.bin"
            proof = Path(tmp) / "proof.json"
            model.write_bytes(b"test candidate, not an original model")
            proof.write_text(json.dumps({"model_sha256": hashlib.sha256(model.read_bytes()).hexdigest()}), encoding="utf-8")
            report = inspect(model, proof)
            self.assertTrue(report["sha256_matches_supplied_manifest"])
            self.assertEqual(report["result"], "blocked_independent_original_provenance_and_reproducibility_not_verified")
            self.assertEqual(report["certified_champion_001_predictions"], 0)
            self.assertFalse(report["original_executable_verified"])


if __name__ == "__main__":
    unittest.main()
