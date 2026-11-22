"""Verify externally signed historical source receipts without promoting training.

The trusted Ed25519 public key must be provisioned independently of the
evidence bundle. Signatures prove key possession, not bookmaker legitimacy:
the operator must independently verify issuer identity and custody policy.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REQUIRED_KINDS = ("pregame", "odds", "outcome")
ALLOWED_LEAGUES = ("nba", "mlb")

def instant(value):
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("naive_timestamp")
    return parsed.astimezone(timezone.utc)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def verify(bundle, archive_root, public_key_pem):
    """Never authorize training; record verifiable evidence and remaining gates."""
    report = {"status": "HOLD", "external_signature_valid": False,
              "record_receipts_verified": 0, "independently_authenticated_records": 0,
              "qualified_training_rows": 0, "certified_take_predictions": 0,
              "champion_001_modified": False, "nfl_collection_modified": False,
              "blocking_reasons": []}
    errors = report["blocking_reasons"]
    if not isinstance(bundle, dict) or not isinstance(bundle.get("statement"), dict):
        errors.append("invalid_signed_statement")
        return report
    statement = bundle["statement"]
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("not_ed25519_key")
        signature = base64.b64decode(bundle["signature_base64"], validate=True)
        key.verify(signature, canonical(statement))
        report["external_signature_valid"] = True
    except (ImportError, ValueError, TypeError, KeyError, Exception) as exc:
        # Deliberately fail closed for missing dependencies, invalid signatures,
        # malformed input or unsupported key types.
        errors.append("signature_verification_failed")
        return report
    if statement.get("schema") != "freddys_external_source_receipt_v1":
        errors.append("unsupported_statement_schema")
        return report
    if statement.get("league") not in ALLOWED_LEAGUES:
        errors.append("unsupported_league")
        return report
    if not isinstance(statement.get("canonical_game_id"), str) or not statement["canonical_game_id"].strip():
        errors.append("missing_canonical_game_id")
        return report
    root = Path(archive_root).resolve()
    receipts = statement.get("receipts")
    if not isinstance(receipts, dict):
        errors.append("missing_receipts")
        return report
    timestamps = {}
    for kind in REQUIRED_KINDS:
        receipt = receipts.get(kind)
        if not isinstance(receipt, dict):
            errors.append("missing_" + kind + "_receipt")
            continue
        try:
            if receipt.get("canonical_game_id") != statement["canonical_game_id"]:
                raise ValueError("identity_mismatch")
            rel = receipt["path"]
            if not isinstance(rel, str) or not rel:
                raise ValueError("invalid_path")
            path = (root / rel).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
                raise ValueError("missing_or_unsafe_bytes")
            digest = receipt["sha256"]
            if not isinstance(digest, str) or len(digest) != 64 or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("digest_mismatch")
            timestamps[kind] = instant(receipt["received_at_utc"])
            report["record_receipts_verified"] += 1
        except (ValueError, TypeError, KeyError, OSError) as exc:
            errors.append(kind + "_receipt_invalid")
    try:
        start = instant(statement["event_start_utc"])
        if not (timestamps["pregame"] < start and timestamps["odds"] < start < timestamps["outcome"]):
            errors.append("invalid_point_in_time_chronology")
    except (KeyError, ValueError, TypeError):
        errors.append("missing_or_invalid_event_chronology")
    # A signed assertion still does not prove provider entitlement, historical
    # market rules, independent settlement or key-holder trustworthiness.
    errors.extend(("signer_identity_and_custody_not_independently_approved",
                   "sportsbook_market_price_and_rules_not_independently_reconciled",
                   "official_outcome_and_settlement_not_independently_reconciled"))
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", required=True)
    p.add_argument("--archive-root", required=True)
    p.add_argument("--trusted-public-key", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = verify(json.loads(Path(a.bundle).read_text()), a.archive_root,
                    Path(a.trusted_public_key).read_bytes())
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
