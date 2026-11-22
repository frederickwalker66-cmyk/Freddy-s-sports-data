"""Independent Sharp Edge Pro fail-closed automation; no paid requests or wagers."""
import datetime as dt
import json
import os
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    out = root / "output"
    out.mkdir(exist_ok=True)
    components = {
        "sharpapi_key_configured": bool(os.getenv("SHARPAPI_KEY")),
        "sportsdataio_key_configured": bool(os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO_API_KEY")),
        "independent_model_artifact_present": (root / "model" / "validated_model.json").exists(),
        "verified_market_snapshot_present": (root / "inputs" / "verified_markets.json").exists(),
        "verified_roster_snapshot_present": (root / "inputs" / "verified_rosters.json").exists(),
        "verified_injury_snapshot_present": (root / "inputs" / "verified_injuries.json").exists(),
    }
    # Presence is only a staging signal. Never promote a file to verified evidence
    # without independent provenance, freshness, identity and model checks.
    evidence_gates = {
        "independent_model_provenance_verified": False,
        "market_snapshot_provenance_and_freshness_verified": False,
        "roster_snapshot_identity_and_freshness_verified": False,
        "injury_snapshot_official_clearance_verified": False,
        "draftkings_checkout_price_verified": False,
        "prospective_calibration_certified": False,
    }
    blockers = [k for k,v in components.items() if not v]
    blockers += [k for k,v in evidence_gates.items() if not v]
    blockers += [
        "Independent model calibration and prospective shadow performance not certified",
        "DraftKings checkout odds not independently verified",
    ]
    report = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": "Freddy's Sharp Edge Pro",
        "mode": "offline automated preflight",
        "components": components,
        "evidence_gates": evidence_gates,
        "credential_checks_are_presence_only": True,
        "snapshot_checks_are_file_presence_only": True,
        "status": "HOLD",
        "certified_take_count": 0,
        "shadow_stake_usd": 0,
        "bets_placed": 0,
        "paid_api_requests": 0,
        "blockers": blockers,
    }
    (out / "status.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
if __name__ == "__main__":
    main()
