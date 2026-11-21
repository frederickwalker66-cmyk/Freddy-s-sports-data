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
        "sportsdataio_key_configured": bool(os.getenv("SPORTSDATAIO_API_KEY")),
        "independent_model_artifact_present": (root / "model" / "validated_model.json").exists(),
        "verified_market_snapshot_present": (root / "inputs" / "verified_markets.json").exists(),
        "verified_roster_snapshot_present": (root / "inputs" / "verified_rosters.json").exists(),
        "verified_injury_snapshot_present": (root / "inputs" / "verified_injuries.json").exists(),
    }
    blockers = [k for k,v in components.items() if not v]
    blockers += [
        "Independent model calibration and prospective shadow performance not certified",
        "DraftKings checkout odds not independently verified",
    ]
    report = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": "Freddy's Sharp Edge Pro",
        "mode": "offline automated preflight",
        "components": components,
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
