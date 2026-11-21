"""Synthetic cryptographic regression fixtures: no real bets or model proof."""
import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone
from scripts.certify_sharp_edge import canonical, evaluate


class SharpEdgeCertificationTests(unittest.TestCase):
    MODEL_KEY = "m" * 40
    ODDS_KEY = "o" * 40
    RELEASE_KEY = "r" * 40
    VERSION = "champion-001-frozen-verified-v1"

    def signed(self, payload, key):
        return {"payload": payload, "signature": hmac.new(
            key.encode(), canonical(payload), hashlib.sha256).hexdigest()}

    def candidate(self, probability=0.6, price=2.0):
        now = datetime.now(timezone.utc)
        common = dict(event_id="nba-123", market_id="total-points",
                      selection_id="over", line=225.5)
        model = dict(common, probability=probability, model_family="Champion-001",
                     model_version=self.VERSION, independent_model_validation=True,
                     model_artifact_sha256="a" * 64, calibration_report_sha256="b" * 64,
                     forecast_receipt_id="synthetic-test-only",
                     predicted_at=(now-timedelta(minutes=2)).isoformat())
        odds = dict(common, decimal_odds=price, sportsbook="DraftKings",
                    direct_checkout_verified=True, checkout_receipt_id="synthetic-checkout-test",
                    observed_at=now.isoformat(), event_start=(now+timedelta(hours=3)).isoformat())
        release = dict(model_version=self.VERSION, model_artifact_sha256="a" * 64,
                       calibration_report_sha256="b" * 64,
                       original_champion_001_authenticated=True,
                       reference_outputs_independently_reproduced=True,
                       calibration_independently_validated=True,
                       release_authorized=True, release_approval_receipt_id="synthetic-review-test")
        return {"model_attestation": self.signed(model, self.MODEL_KEY),
                "odds_attestation": self.signed(odds, self.ODDS_KEY),
                "release_attestation": self.signed(release, self.RELEASE_KEY)}

    def evaluate_valid_fixture(self, candidate, **kwargs):
        settings = dict(model_key=self.MODEL_KEY, odds_key=self.ODDS_KEY,
                        release_key=self.RELEASE_KEY, approved_model_versions=(self.VERSION,))
        settings.update(kwargs)
        return evaluate(candidate, **settings)

    def test_missing_keys_holds(self):
        self.assertEqual(evaluate(self.candidate())["decision"], "HOLD")

    def test_distinct_verified_sources_allow_synthetic_take(self):
        report = self.evaluate_valid_fixture(self.candidate())
        self.assertEqual(report["decision"], "TAKE")
        self.assertTrue(report["certified"])

    def test_negative_ev_passes(self):
        report = self.evaluate_valid_fixture(self.candidate(price=1.5))
        self.assertEqual(report["decision"], "PASS")

    def test_tampered_odds_holds(self):
        candidate = self.candidate()
        candidate["odds_attestation"]["payload"]["decimal_odds"] = 3.0
        self.assertEqual(self.evaluate_valid_fixture(candidate)["decision"], "HOLD")

    def test_mismatched_market_holds(self):
        candidate = self.candidate()
        odds = candidate["odds_attestation"]["payload"]
        odds["line"] = 226.5
        candidate["odds_attestation"] = self.signed(odds, self.ODDS_KEY)
        self.assertIn("EXACT_MARKET_MISMATCH", self.evaluate_valid_fixture(candidate)["reasons"])

    def test_unapproved_model_release_holds(self):
        report = self.evaluate_valid_fixture(self.candidate(), approved_model_versions=())
        self.assertIn("MODEL_RELEASE_NOT_IN_INDEPENDENT_APPROVAL_REGISTRY", report["reasons"])

    def test_same_custodian_holds(self):
        result = self.evaluate_valid_fixture(self.candidate(), release_key=self.MODEL_KEY)
        self.assertEqual(result["decision"], "HOLD")

    def test_missing_independent_release_holds(self):
        report = self.evaluate_valid_fixture(self.candidate(), release_key=None)
        self.assertEqual(report["decision"], "HOLD")
        self.assertIn("INDEPENDENT_CHAMPION_RELEASE_ATTESTATION_NOT_VERIFIED", report["reasons"])

    def test_challenger_cannot_be_certified_as_champion(self):
        candidate = self.candidate()
        model = candidate["model_attestation"]["payload"]
        model["model_family"] = "Challenger-001"
        candidate["model_attestation"] = self.signed(model, self.MODEL_KEY)
        report = self.evaluate_valid_fixture(candidate)
        self.assertEqual(report["decision"], "HOLD")
        self.assertIn("NATIVE_CHAMPION_001_MODEL_REQUIRED", report["reasons"])

    def test_unverified_checkout_holds_even_with_signed_odds(self):
        candidate = self.candidate()
        odds = candidate["odds_attestation"]["payload"]
        odds["direct_checkout_verified"] = False
        candidate["odds_attestation"] = self.signed(odds, self.ODDS_KEY)
        self.assertIn("EXECUTABLE_SPORTSBOOK_CHECKOUT_RECEIPT_NOT_VERIFIED",
                      self.evaluate_valid_fixture(candidate)["reasons"])

    def test_independent_provenance_failure_holds_even_when_signed(self):
        candidate = self.candidate()
        proof = candidate["release_attestation"]["payload"]
        proof["reference_outputs_independently_reproduced"] = False
        candidate["release_attestation"] = self.signed(proof, self.RELEASE_KEY)
        self.assertIn("INDEPENDENT_CHAMPION_PROVENANCE_OR_CALIBRATION_NOT_VERIFIED",
                      self.evaluate_valid_fixture(candidate)["reasons"])

    def test_forged_model_hash_mismatch_holds(self):
        candidate = self.candidate()
        model = candidate["model_attestation"]["payload"]
        model["model_artifact_sha256"] = "c" * 64
        candidate["model_attestation"] = self.signed(model, self.MODEL_KEY)
        self.assertIn("INDEPENDENT_MODEL_RELEASE_DIGEST_MISMATCH",
                      self.evaluate_valid_fixture(candidate)["reasons"])


if __name__ == "__main__":
    unittest.main()
