"""Record-level MLB/NBA evidence cross-check. Research only; no certification."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def utc(value):
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_missing")
    return dt.astimezone(timezone.utc)

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inspect(record, archive_root):
    """Check independently retained bytes and chronological identity claims.

    Does NOT verify external signatures, licensed real-data entitlement,
    bookmaker settlement rules, or official league adjudication.
    """
    problems = []
    if not isinstance(record, dict):
        return {"status": "HOLD", "reasons": ["record_not_object"]}
    league = record.get("league")
    if league not in ("mlb", "nba"):
        problems.append("unsupported_league")
    ids = record.get("event_ids")
    if not isinstance(ids, dict) or any(not isinstance(ids.get(k), str) or not ids[k].strip()
                                        for k in ("historical", "pregame", "odds", "outcome")):
        problems.append("missing_source_game_identity")
    elif len(set(ids.values())) != 1:
        # Only identical canonical IDs are accepted here; provider crosswalks
        # require a separately verified mapping and are not inferred.
        problems.append("game_identity_mismatch")
    try:
        pregame = utc(record["pregame_received_at_utc"])
        odds = utc(record["odds_received_at_utc"])
        start = utc(record["event_start_utc"])
        outcome = utc(record["outcome_received_at_utc"])
        if not (pregame < start and odds < start and outcome > start):
            problems.append("invalid_receipt_chronology")
    except (ValueError, TypeError, KeyError, OverflowError):
        problems.append("invalid_receipt_timestamps")
    receipts = record.get("receipts")
    if not isinstance(receipts, dict):
        problems.append("missing_receipts")
    else:
        for kind in ("pregame", "odds", "outcome"):
            item = receipts.get(kind)
            if not isinstance(item, dict):
                problems.append("missing_" + kind + "_receipt")
                continue
            rel = item.get("path")
            digest = item.get("sha256")
            if not isinstance(rel, str) or not rel or not isinstance(digest, str) or len(digest) != 64:
                problems.append("invalid_" + kind + "_receipt")
                continue
            root = Path(archive_root).resolve()
            candidate = (root / rel).resolve()
            if not candidate.is_relative_to(root) or not candidate.is_file():
                problems.append("missing_or_unsafe_" + kind + "_bytes")
            elif sha256_file(candidate) != digest:
                problems.append("hash_mismatch_" + kind)
    if record.get("independent_official_outcome_attestation") is not True:
        problems.append("official_outcome_not_independently_attested")
    if record.get("independent_bookmaker_settlement_attestation") is not True:
        problems.append("bookmaker_settlement_not_independently_attested")
    if record.get("independent_odds_source_attestation") is not True:
        problems.append("odds_source_not_independently_attested")
    # Self-declared attestations are not verified cryptographically. This
    # validator never authorizes model training or betting.
    problems.append("external_attestation_signatures_not_verified")
    return {"status": "HOLD", "reasons": sorted(set(problems)),
            "local_receipt_integrity_passed": not any(
                p.startswith(("missing_", "invalid_", "hash_mismatch_", "game_identity_", "unsupported_"))
                for p in problems),
            "independent_authentication_complete": False,
            "qualified_training_rows": 0, "certified_take_predictions": 0}

def audit(rows, root):
    results = [inspect(row, root) for row in rows]
    return {"stage": "mlb_nba_record_level_receipt_verification",
            "records_inspected": len(results),
            "local_receipt_integrity_passed": sum(x["local_receipt_integrity_passed"] for x in results),
            "independently_authenticated_records": 0,
            "qualified_training_rows": 0, "certified_take_predictions": 0,
            "champion_001_modified": False, "nfl_collection_modified": False,
            "status": "HOLD", "records": results}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--archive-root", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    rows = [json.loads(line) for line in Path(args.manifest).read_text().splitlines() if line.strip()]
    result = audit(rows, args.archive_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))

if __name__ == "__main__":
    main()
