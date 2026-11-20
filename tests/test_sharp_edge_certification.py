import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone
from scripts.certify_sharp_edge import canonical, evaluate

class SharpEdgeCertificationTests(unittest.TestCase):
    def signed(self, payload, key):
        return {"payload": payload, "signature": hmac.new(key.encode(), canonical(payload), hashlib.sha256).hexdigest()}

    def candidate(self, probability=0.6, price=2.0):
        now = datetime.now(timezone.utc)
        common = dict(event_id="nba-123", market_id="total-points", selection_id="over", line=225.5)
        model = dict(common, probability=probability, model_version="challenger-validated-v1",
                     independent_model_validation=True, predicted_at=(now-timedelta(minutes=2)).isoformat())
        odds = dict(common, decimal_odds=price, sportsbook="DraftKings",
                    observed_at=now.isoformat(), event_start=(now+timedelta(hours=3)).isoformat())
        return {"model_attestation": self.signed(model, "m"*40),
                "odds_attestation": self.signed(odds, "o"*40)}

    def test_missing_keys_holds(self):
        self.assertEqual(evaluate(self.candidate())["decision"], "HOLD")

    def test_distinct_verified_sources_allow_take(self):
        report = evaluate(self.candidate(), model_key="m"*40, odds_key="o"*40, approved_model_versions=("challenger-validated-v1",))
        self.assertEqual(report["decision"], "TAKE")
        self.assertTrue(report["certified"])

    def test_negative_ev_passes(self):
        report = evaluate(self.candidate(price=1.5), model_key="m"*40, odds_key="o"*40, approved_model_versions=("challenger-validated-v1",))
        self.assertEqual(report["decision"], "PASS")

    def test_tampered_odds_holds(self):
        candidate = self.candidate()
        candidate["odds_attestation"]["payload"]["decimal_odds"] = 3.0
        self.assertEqual(evaluate(candidate, model_key="m"*40, odds_key="o"*40)["decision"], "HOLD")

    def test_mismatched_market_holds(self):
        candidate = self.candidate()
        odds = candidate["odds_attestation"]["payload"]
        odds["line"] = 226.5
        candidate["odds_attestation"] = self.signed(odds, "o"*40)
        self.assertIn("EXACT_MARKET_MISMATCH", evaluate(candidate, model_key="m"*40, odds_key="o"*40)["reasons"])

    def test_unapproved_model_release_holds(self):
        report = evaluate(self.candidate(), model_key="m"*40, odds_key="o"*40)
        self.assertEqual(report["decision"], "HOLD")
        self.assertIn("MODEL_RELEASE_NOT_IN_INDEPENDENT_APPROVAL_REGISTRY", report["reasons"])

    def test_same_custodian_holds(self):
        self.assertEqual(evaluate(self.candidate(), model_key="m"*40, odds_key="m"*40)["decision"], "HOLD")

if __name__ == "__main__":
    unittest.main()
