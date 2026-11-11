"""Synthetic NBA evidence admission tests. Not evidence of actual NBA results."""
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from challenger_authenticated_chronological_dataset import canon, sha256
from challenger_nba_independent_source_admission import (
    ROW_TYPE, build, outcome_attestation, pregame_attestation, save)
from challenger_nba_probability import train_engine

NOW = datetime(2027, 1, 1, tzinfo=timezone.utc)


class NBAOriginalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pre = Ed25519PrivateKey.generate()
        self.final = Ed25519PrivateKey.generate()

    def make(self, i):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
        prior = start - timedelta(hours=3)
        features = {"pregame_home_form": (i * 17 % 101) / 100,
                    "pregame_away_form": (i * 29 % 103) / 100}
        pre_content = canon({"test_only": True, "event": i, "features": features})
        final_content = canon({"test_only": True, "event": i, "winner": i % 2})
        prepath, outpath = f"nba_pregame_{i}.json", f"nba_final_{i}.json"
        (self.root / prepath).write_bytes(pre_content)
        (self.root / outpath).write_bytes(final_content)
        row = {
            "record_type": ROW_TYPE,
            "event_id": str(500000000 + i), "league": "nba",
            "market_type": "moneyline", "selection_type": "home",
            "settlement_scope": "including_overtime",
            "snapshot_utc": prior.isoformat(),
            "features_asof_utc": (prior - timedelta(minutes=10)).isoformat(),
            "start_utc": start.isoformat(),
            "outcome_verified_at_utc": (start + timedelta(hours=3)).isoformat(),
            "event_source_url": "https://example.org/fixture",
            "feature_source_url": "https://example.org/pregame",
            "outcome_source_url": "https://example.org/final",
            "features": features, "outcome": i % 2,
            "qualified_for_challenger_backtest": True,
            "independent_asof_review": True,
            "independent_outcome_review": True,
            "feature_snapshot_sha256": sha256(pre_content),
            "outcome_snapshot_sha256": sha256(final_content),
            "champion_001_modified": False,
        }
        for side, proof, signer, filename in (
            ("pregame_proof", pregame_attestation(row), self.pre, prepath),
            ("outcome_proof", outcome_attestation(row), self.final, outpath),
        ):
            row[side] = {
                "attestation": proof,
                "signature_b64": base64.b64encode(signer.sign(canon(proof))).decode(),
                "original_path": filename,
            }
        return row

    def gate(self, rows):
        return build(rows, self.root, self.pre.public_key(),
                     self.final.public_key(), NOW)

    def test_exact_250_signed_mock_games_seal_200_and_50(self):
        rows = [self.make(i) for i in range(250)]
        report, groups = self.gate(rows)
        self.assertTrue(report["candidate_dataset_ready_for_external_review"])
        self.assertEqual(len(groups["train"]), 200)
        self.assertEqual(len(groups["holdout"]), 50)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(report["source_witness_identity_externally_vetted_by_software"])
        self.assertFalse(report["holdout_external_worm_custody_proven_by_software"])
        directory = self.root / "sealed"
        save(directory, report, groups)
        save(directory, report, groups)
        marker = directory / "nba_holdout_local_seal.json"
        self.assertEqual(len(json.loads(marker.read_text())["holdout_event_ids"]), 50)
        marker.write_text("{}")
        with self.assertRaisesRegex(ValueError, "seal_changed"):
            save(directory, report, groups)

    def test_nba_train_model_is_fit_from_earlier_200_only(self):
        report, groups = self.gate([self.make(i) for i in range(250)])
        ids = [r["event_id"] for r in groups["holdout"]]
        summary, model = train_engine(groups["train"] + groups["holdout"],
                                      as_of=NOW, sealed_holdout_ids=ids)
        self.assertEqual(summary["chronological_train_games"], 200)
        self.assertEqual(summary["chronological_holdout_games"], 50)
        self.assertEqual(model["fit"]["training_rows"], 200)
        self.assertFalse(model["holdout_was_used_to_fit_or_refit_model"])
        self.assertEqual(summary["certified_champion_001_predictions"], 0)

    def test_249_is_not_qualified_and_self_flags_are_not_evidence(self):
        report, groups = self.gate([self.make(i) for i in range(249)])
        self.assertIsNone(groups)
        self.assertFalse(report["candidate_dataset_ready_for_external_review"])
        forged = self.make(1)
        forged.pop("pregame_proof")
        report, groups = self.gate([forged])
        self.assertIsNone(groups)
        self.assertEqual(report["nba_original_games_witness_admitted"], 0)

    def test_tampered_original_source_or_signature_rejected(self):
        row = self.make(2)
        (self.root / "nba_pregame_2.json").write_bytes(b"tampered original")
        report, groups = self.gate([row])
        self.assertIsNone(groups)
        self.assertEqual(report["nba_original_games_witness_admitted"], 0)
        self.assertTrue(any("digest_mismatch" in reason for reason in report["rejected"]))
        row = self.make(3)
        row["outcome_proof"]["signature_b64"] = "AAAA"
        report, groups = self.gate([row])
        self.assertIsNone(groups)
        self.assertTrue(any("signature_invalid" in reason for reason in report["rejected"]))

    def test_source_clock_and_event_identity_cannot_be_backdated(self):
        row = self.make(4)
        row["features_asof_utc"] = (
            datetime.fromisoformat(row["start_utc"]) + timedelta(seconds=1)).isoformat()
        report, groups = self.gate([row])
        self.assertEqual(report["nba_original_games_witness_admitted"], 0)
        row = self.make(5)
        row["event_id"] = "synthetic-id"
        report, groups = self.gate([row])
        self.assertEqual(report["nba_original_games_witness_admitted"], 0)

    def test_witnesses_must_be_distinct_and_keys_cannot_be_missing(self):
        row = self.make(6)
        with self.assertRaisesRegex(ValueError, "must_be_distinct"):
            build([row], self.root, self.pre.public_key(), self.pre.public_key(), NOW)
        report, groups = build([row], self.root, now=NOW)
        self.assertIsNone(groups)
        self.assertEqual(report["status"], "HOLD_MISSING_EXTERNAL_NBA_TRUST_ANCHORS")

    def test_same_day_holdout_boundary_cannot_leak_train_games(self):
        rows = [self.make(i) for i in range(250)]
        # Move game 199 onto the same day as game 200; proof is re-signed.
        rows[199]["start_utc"] = rows[200]["start_utc"]
        rows[199]["snapshot_utc"] = rows[200]["snapshot_utc"]
        rows[199]["features_asof_utc"] = rows[200]["features_asof_utc"]
        rows[199]["outcome_verified_at_utc"] = rows[200]["outcome_verified_at_utc"]
        for field, assertion, private in (("pregame_proof", pregame_attestation, self.pre),
                                          ("outcome_proof", outcome_attestation, self.final)):
            signed = assertion(rows[199])
            rows[199][field]["attestation"] = signed
            rows[199][field]["signature_b64"] = base64.b64encode(private.sign(canon(signed))).decode()
        report, groups = self.gate(rows)
        self.assertIsNone(groups)
        self.assertEqual(report["chronological_training_games"], 199)
        self.assertEqual(report["untouched_holdout_games"], 51)


if __name__ == "__main__":
    unittest.main()
