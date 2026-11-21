"""Bind Challenger-002 metadata to locally retained raw SportsDataIO response bytes.

Offline verification only: a matching digest proves integrity relative to the
supplied bytes, NOT provider authenticity or historical point-in-time custody.
Raw receipts must be obtained through an independently audited ingestion path.
"""
import argparse
import hashlib
import json
from pathlib import Path
from research.challenger_002_source_validation import inspect

def verify(rows, receipt_directory):
    report = inspect(rows)
    failures = list(report["rejected"])
    checked = 0
    root = Path(receipt_directory).resolve()
    if not root.is_dir():
        failures.append({"row": None, "reason": "receipt_directory_missing"})
    else:
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            receipt_id = row.get("source_record_id")
            if not isinstance(receipt_id, str) or not receipt_id or not all(
                c.isascii() and (c.isalnum() or c in "_-.") for c in receipt_id
            ) or receipt_id in (".", ".."):
                failures.append({"row": i, "reason": "unsafe_receipt_id"})
                continue
            path = (root / (receipt_id + ".json")).resolve()
            if path.parent != root or not path.is_file() or path.is_symlink():
                failures.append({"row": i, "reason": "raw_receipt_missing"})
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row.get("source_payload_sha256"):
                failures.append({"row": i, "reason": "raw_receipt_digest_mismatch"})
                continue
            checked += 1
    return {"status": "LOCAL_DIGESTS_MATCH_NOT_AUTHENTICATED" if rows and not failures else "BLOCKED",
            "rows": len(rows), "receipts_matched": checked, "failures": failures,
            "provider_authenticated": False, "point_in_time_custody_verified": False,
            "certified_take_count": 0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(s) for s in Path(args.input).read_text().splitlines() if s.strip()]
    report = verify(rows, args.receipts)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    if report["status"] == "BLOCKED":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
