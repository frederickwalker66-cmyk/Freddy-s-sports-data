"""Integrate local receipt checks with externally signed statement checks.

Independent signing authority, bookmaker prices, and official settlement must
be established out of band; this module NEVER promotes training or TAKE.
"""
import argparse
import json
from pathlib import Path
from mlb_nba_record_receipt_verification import inspect
from research.external_source_attestation_gate import verify

def reconcile(record, signed_bundle, archive_root, trusted_public_key):
    local = inspect(record, archive_root)
    signed = verify(signed_bundle, archive_root, trusted_public_key)
    blockers = list(local["reasons"]) + list(signed["blocking_reasons"])
    statement = signed_bundle.get("statement", {}) if isinstance(signed_bundle, dict) else {}
    if not isinstance(statement, dict):
        statement = {}
    ids = record.get("event_ids", {}) if isinstance(record, dict) else {}
    if not isinstance(ids, dict) or ids.get("historical") != statement.get("canonical_game_id"):
        blockers.append("signed_statement_game_identity_mismatch")
    if record.get("league") != statement.get("league"):
        blockers.append("signed_statement_league_mismatch")
    if record.get("event_start_utc") != statement.get("event_start_utc"):
        blockers.append("signed_statement_start_time_mismatch")
    local_receipts = record.get("receipts", {})
    signed_receipts = statement.get("receipts", {})
    for kind in ("pregame", "odds", "outcome"):
        a = local_receipts.get(kind, {}) if isinstance(local_receipts, dict) else {}
        b = signed_receipts.get(kind, {}) if isinstance(signed_receipts, dict) else {}
        if not isinstance(a, dict) or not isinstance(b, dict) or any(
                a.get(field) != b.get(field) for field in ("path", "sha256")):
            blockers.append("signed_statement_" + kind + "_bytes_mismatch")
        if record.get(kind + "_received_at_utc") != b.get("received_at_utc"):
            blockers.append("signed_statement_" + kind + "_receipt_time_mismatch")
    return {"status": "HOLD", "local_receipt_integrity_passed": local["local_receipt_integrity_passed"],
            "external_signature_valid": signed["external_signature_valid"],
            "record_receipts_verified": signed["record_receipts_verified"],
            "blocking_reasons": sorted(set(blockers)),
            "qualified_training_rows": 0, "certified_take_predictions": 0,
            "champion_001_modified": False, "nfl_collection_modified": False}

def main():
    p = argparse.ArgumentParser()
    for arg in ("record", "signed-bundle", "archive-root", "trusted-public-key", "output"):
        p.add_argument("--" + arg, required=True)
    a = p.parse_args()
    report = reconcile(json.loads(Path(a.record).read_text()),
                       json.loads(Path(a.signed_bundle).read_text()),
                       a.archive_root, Path(a.trusted_public_key).read_bytes())
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
