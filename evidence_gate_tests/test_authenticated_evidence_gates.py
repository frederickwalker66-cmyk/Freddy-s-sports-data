"""Synthetic tests only. Never interpret fixtures as real betting predictions."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from challenger_authenticated_chronological_dataset import (
    build, canon, expected_outcome, expected_pregame, sha256, write_output)
from challenger_multisport_native_capture import MARKETS, SCOPE
from v8_external_price_receipt_audit import reconcile, expected_checkout_witness

NOW = datetime(2027, 11, 11, tzinfo=timezone.utc)


class AuthenticationGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "pregame.json").write_bytes(b"external-pregame-snapshot-fixture")
        (self.root / "final.json").write_bytes(b"external-final-snapshot-fixture")
        (self.root / "checkout.json").write_bytes(b"external-checkout-snapshot-fixture")
        self.pre = Ed25519PrivateKey.generate()
        self.out = Ed25519PrivateKey.generate()
        self.checkout = Ed25519PrivateKey.generate()

    def sign(self, attestation, signer, file):
        return {
            "attestation": attestation,
            "signature_b64": base64.b64encode(signer.sign(canon(attestation))).decode(),
            "original_path": file,
        }

    def make_row(self, i=0, league="nfl"):
        start = NOW - timedelta(days=350-i)
        feature = (i * 17 % 101) / 101
        row = {
            "record_type": "challenger_reviewed_pregame_game_evidence_v1",
            "league": league, "event_id": str(200000000 + i),
            "market_type": MARKETS[league], "settlement_scope": SCOPE[league],
            "start_utc": start.isoformat(),
            "snapshot_utc": (start - timedelta(hours=3)).isoformat(),
            "features_asof_utc": (start - timedelta(hours=4)).isoformat(),
            "outcome_verified_at_utc": (start + timedelta(hours=2)).isoformat(),
            "outcome": "home" if i % 2 else "away",
            "features": {"pregame_team_strength": feature},
            "event_source_url": "https://site.api.espn.com/schedule",
            "feature_source_url": "https://archive.example.org/pregame",
            "outcome_source_url": "https://league.example.org/final",
            "feature_snapshot_sha256": sha256((self.root / "pregame.json").read_bytes()),
            "outcome_snapshot_sha256": sha256((self.root / "final.json").read_bytes()),
            "independent_feature_asof_review": True,
            "independent_outcome_review": True,
            "market_settlement_rules_verified": True,
            "qualified_for_challenger_training": True,
            "champion_001_modified": False,
        }
        row["pregame_proof"] = self.sign(expected_pregame(row), self.pre, "pregame.json")
        row["outcome_proof"] = self.sign(expected_outcome(row), self.out, "final.json")
        return row

    def gate(self, rows):
        return build(rows, self.root, self.pre.public_key(),
                     self.out.public_key(), NOW)

    def test_unsigned_250_never_promotes(self):
        rows = [self.make_row(i) for i in range(250)]
        for row in rows:
            row.pop("pregame_proof")
        report, splits = self.gate(rows)
        self.assertEqual(report["admitted_games"], 0)
        self.assertFalse(splits)
        self.assertEqual(report["certified_bets"], 0)

    def test_250_separate_dates_stay_research_only(self):
        report, splits = self.gate([self.make_row(i) for i in range(250)])
        self.assertEqual(report["admitted_games"], 250)
        self.assertEqual(len(splits["nfl"]["train"]), 200)
        self.assertEqual(len(splits["nfl"]["holdout"]), 50)
        self.assertFalse(report["bet_ready"])
        self.assertFalse(report["source_custodian_identity_independently_vetted_by_software"])
        outdir = self.root / "output"
        write_output(outdir, report, splits)
        write_output(outdir, report, splits)
        lock = outdir / "nfl_holdout_lock.json"
        self.assertEqual(len(json.loads(lock.read_text())["holdout_event_ids"]), 50)
        lock.write_text("{}")
        with self.assertRaisesRegex(ValueError, "lock_changed"):
            write_output(outdir, report, splits)

    def test_wrong_signature_and_changed_original_rejected(self):
        x = self.make_row()
        x["pregame_proof"]["signature_b64"] = "AAAA"
        report, split = self.gate([x])
        self.assertEqual(report["admitted_games"], 0)
        self.assertFalse(split)
        x = self.make_row()
        (self.root / "pregame.json").write_bytes(b"tampered")
        report, split = self.gate([x])
        self.assertEqual(report["admitted_games"], 0)
        self.assertTrue(any("digest_mismatch" in k for k in report["rejected"]))

    def test_post_start_and_time_leakage(self):
        x = self.make_row()
        x["snapshot_utc"] = x["outcome_verified_at_utc"]
        report, _ = self.gate([x])
        self.assertEqual(report["admitted_games"], 0)
        self.assertTrue(any("leakage" in k for k in report["rejected"]))

    def test_distinct_custodians_and_missing_keys_required(self):
        x = self.make_row()
        with self.assertRaisesRegex(ValueError, "must_differ"):
            build([x], self.root, self.pre.public_key(), self.pre.public_key(), NOW)
        report, groups = build([x], self.root, None, None, NOW)
        self.assertEqual(report["admitted_games"], 0)
        self.assertFalse(groups)

    def test_no_holdout_when_only_249(self):
        report, splits = self.gate([self.make_row(i) for i in range(249)])
        self.assertFalse(splits)
        self.assertEqual(report["by_league"]["nfl"]["status"],
                         "need_250_externally_witnessed_games")

    def test_no_promotion_from_local_receipts(self):
        x = self.make_row()
        x["pregame_proof"]["original_path"] = "../pregame.json"
        report, _ = self.gate([x])
        self.assertEqual(report["admitted_games"], 0)

    def make_forecast(self):
        start = NOW + timedelta(days=1)
        return {
            "league": "nba", "event_id": "12345",
            "market_type": "moneyline", "settlement_scope": "including_overtime",
            "selection": "home", "line": None,
            "start_utc": start.isoformat(),
            "forecast_utc": (NOW - timedelta(minutes=1)).isoformat(),
            "model_version": "v8-elo-research-only",
            "model_probability": 0.56,
            "research_only": True, "bet_ready": False,
            "certified_prediction": False, "champion_001_modified": False,
        }

    def make_quote(self, forecast):
        quote = {
            "source": "draftkings_original_checkout_capture",
            "provider": "DraftKings", "source_scope": "user_visible_exact_checkout",
            "source_url": "https://sportsbook.draftkings.com/event/fictional",
            "league": forecast["league"], "event_id": forecast["event_id"],
            "market_type": forecast["market_type"],
            "selection": forecast["selection"], "line": forecast["line"],
            "settlement_scope": forecast["settlement_scope"],
            "start_utc": forecast["start_utc"],
            "captured_at_utc": (NOW - timedelta(seconds=40)).isoformat(),
            "price_american": -110,
            "original_sha256": sha256((self.root / "checkout.json").read_bytes()),
        }
        quote["external_witness"] = self.sign(
            expected_checkout_witness(quote), self.checkout, "checkout.json")
        return quote

    def test_no_unsigned_or_aggregator_price_promotion(self):
        forecast = self.make_forecast()
        quote = self.make_quote(forecast)
        unsigned = dict(quote)
        unsigned.pop("external_witness")
        a = reconcile([forecast], [unsigned], self.root, self.checkout.public_key(), NOW)
        self.assertEqual(a["externally_witnessed_quote_pairs_research_only"], 0)
        quote["source"] = "sharpapi_rest"
        a = reconcile([forecast], [quote], self.root, self.checkout.public_key(), NOW)
        self.assertEqual(a["externally_witnessed_quote_pairs_research_only"], 0)

    def test_witnessed_exact_market_remains_hold(self):
        forecast = self.make_forecast()
        quote = self.make_quote(forecast)
        a = reconcile([forecast], [quote], self.root, self.checkout.public_key(), NOW)
        self.assertEqual(a["first_pregame_forecasts_preserved"], 1)
        self.assertEqual(a["externally_witnessed_quote_pairs_research_only"], 1)
        self.assertEqual(a["certified_positive_ev_picks"], 0)
        self.assertFalse(a["bet_ready"])
        self.assertTrue(a["quote_candidates"][0]["research_ev_not_certified"] > 0)
        self.assertFalse(a["quote_candidates"][0]["sportsbook_signed_original_verified"])

    def test_quote_must_match_exact_selection_and_time(self):
        forecast = self.make_forecast()
        quote = self.make_quote(forecast)
        quote["selection"] = "away"
        quote["external_witness"] = self.sign(
            expected_checkout_witness(quote), self.checkout, "checkout.json")
        a = reconcile([forecast], [quote], self.root, self.checkout.public_key(), NOW)
        self.assertEqual(a["externally_witnessed_quote_pairs_research_only"], 0)
        quote = self.make_quote(forecast)
        quote["captured_at_utc"] = (NOW - timedelta(minutes=4)).isoformat()
        quote["external_witness"] = self.sign(
            expected_checkout_witness(quote), self.checkout, "checkout.json")
        a = reconcile([forecast], [quote], self.root, self.checkout.public_key(), NOW)
        self.assertEqual(a["externally_witnessed_quote_pairs_research_only"], 0)


if __name__ == "__main__":
    unittest.main()
