"""Fail-closed NBA historical archive provenance gap report.

An inventory hash is not an independently authenticated pregame timestamp.
This report inventories evidence gaps without qualifying records for training.
"""
import argparse
import json
from pathlib import Path

REQUIRED = (
    "independently_authenticated_source_publication_time",
    "pregame_feature_snapshot_verified",
    "historical_market_snapshot_verified",
    "independently_verified_final_outcome",
)

def audit(root):
    root = Path(root)
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()) if root.is_dir() else []
    rows = []
    for path in files:
        if path.suffix != ".jsonl":
            continue
        count = 0
        malformed = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("not an object")
                count += 1
            except (ValueError, TypeError):
                malformed += 1
        rows.append({"file": path.relative_to(root).as_posix(), "parseable_rows": count, "malformed_rows": malformed})
    return {
        "stage": "nba_archive_provenance_gap_diagnostic",
        "files_found": len(files),
        "jsonl_inventory": rows,
        "required_independent_evidence": list(REQUIRED),
        "independent_publication_time_authenticated": False,
        "qualified_training_examples": 0,
        "training_release": "HOLD",
        "certified_take_count": 0,
        "champion_001_modified": False,
        "note": "Parsing archived scores and hashing bytes cannot authenticate historical pregame availability. Obtain independent source publication records and original pregame features before qualification.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.root)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
