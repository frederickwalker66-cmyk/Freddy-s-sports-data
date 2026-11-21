"""Deterministic readiness gate for Freddy's Picks AI.

No API calls, no credentials, no implied certification. External evidence must
be supplied by independently verified systems; missing evidence fails closed.
"""
import argparse
import json
from pathlib import Path

REQUIREMENTS = (
    "champion_001_checkpoint_recovered",
    "champion_001_checksum_verified",
    "licensed_historical_storage_configured",
    "pregame_odds_custody_independently_verified",
    "draftkings_market_mapping_verified",
    "final_results_independently_verified",
    "roster_injury_freshness_verified",
    "training_and_holdout_complete",
    "market_specific_calibration_passed",
    "forward_shadow_validation_passed",
    "live_price_freshness_verified",
    "independent_certification_approved",
)

def assess(evidence=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    # Boolean assertions alone are not independently verifiable evidence.
    missing = [key for key in REQUIREMENTS if evidence.get(key) is not True]
    return {
        "system":"Freddys Picks AI",
        "status":"HOLD",
        "certified_take_count":0,
        "research_only":True,
        "missing_or_unverified":missing,
        "self_attested_flags_not_certification":True,
        "reason":"INDEPENDENT_VERIFICATION_ENGINE_NOT_CONNECTED",
        "note":"No supplied JSON flags can promote this model to certified TAKE.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",help="Optional self-attested diagnostic JSON; cannot certify")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    evidence=json.loads(Path(args.evidence).read_text()) if args.evidence else {}
    report=assess(evidence)
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
