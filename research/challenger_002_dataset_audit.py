"""Fail-closed audit of NBA training-row eligibility.

Metadata supplied by a dataset is NOT independent evidence. Only an
externally verified manifest can authorize research admission. No certification.
"""
import argparse
import json
from pathlib import Path
from research.challenger_002_source_validation import inspect

REQUIRED_EVIDENCE = (
    "provider_response_authenticated",
    "licensed_retention_approved",
    "pregame_capture_independently_verified",
    "outcome_source_independently_verified",
    "market_mapping_independently_verified",
    "feature_availability_independently_verified",
)

def audit(rows, manifest):
    report = inspect(rows)
    blockers = []
    if report["status"] != "SCHEMA_VALID_ONLY_NOT_SOURCE_AUTHENTICATED":
        blockers.append("INVALID_OR_INCOMPLETE_ROWS")
    if not isinstance(manifest, dict):
        blockers.append("MISSING_INDEPENDENT_EVIDENCE_MANIFEST")
    else:
        for key in REQUIRED_EVIDENCE:
            if manifest.get(key) is not True:
                blockers.append("EVIDENCE_MISSING_" + key.upper())
        if not isinstance(manifest.get("auditor"), str) or not manifest["auditor"].strip():
            blockers.append("MISSING_AUDITOR_IDENTITY")
        if not isinstance(manifest.get("evidence_uri"), str) or not manifest["evidence_uri"].strip():
            blockers.append("MISSING_AUDIT_EVIDENCE_REFERENCE")
    return {
        "status": "ELIGIBLE_FOR_RESEARCH_REVIEW_NOT_CERTIFIED" if not blockers else "BLOCKED",
        "rows": len(rows), "schema_validation": report,
        "blockers": blockers, "evidence_self_reported_not_independently_authenticated": True,
        "certified_take_count": 0, "research_only": True,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    manifest = json.loads(Path(args.manifest).read_text())
    result = audit(rows, manifest)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status":result["status"],"rows":result["rows"],"blockers":result["blockers"],"certified_take_count":0}))
    if result["status"] == "BLOCKED":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
