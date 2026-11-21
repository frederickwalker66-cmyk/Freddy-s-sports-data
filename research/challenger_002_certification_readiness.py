"""Fail-closed certification readiness ledger; never upgrades research evidence."""
import json
from pathlib import Path

REQUIRED = (
    "production_odds_entitlement_verified",
    "unscrambled_prices_verified",
    "draftkings_identity_verified",
    "pregame_timestamp_provenance_verified",
    "independent_outcomes_verified",
    "champion_001_artifact_recovered",
    "champion_001_native_probabilities_verified",
    "independent_calibration_passed",
)

def assess(evidence=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    # Boolean flags must be accompanied by independently verifiable receipts.
    checks = {}
    for key in REQUIRED:
        item = evidence.get(key)
        checks[key] = bool(isinstance(item, dict) and item.get("verified") is True
                           and isinstance(item.get("receipt_sha256"), str)
                           and len(item["receipt_sha256"]) == 64
                           and all(c in "0123456789abcdef" for c in item["receipt_sha256"]))
    return {
        "status": "CERTIFICATION_REVIEW_REQUIRED" if all(checks.values()) else "HOLD",
        "checks": checks,
        "missing": [k for k, v in checks.items() if not v],
        "automated_certification_granted": False,
        "certified_take_count": 0,
        "champion_001_frozen": True,
        "challenger_002_research_only": True,
    }

if __name__ == "__main__":
    import sys
    data = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else {}
    print(json.dumps(assess(data), sort_keys=True))
