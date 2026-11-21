"""One-command, no-paid-API operational preflight for Freddy's Picks AI.

Runs offline validation, checks expected repository components, and emits
machine-readable HOLD reasons. Never calls providers, trains models or bets.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

COMPONENTS = {
    "odds_collector": "collector.py",
    "schedule_crosswalk": "challenger_schedule_crosswalk.py",
    "research_audit": "challenger_audit.py",
    "prop_integrity": "scripts/player_prop_integrity_gate.py",
    "roster_gate": "roster_validation.py",
    "injury_gate": "availability_validation.py",
    "readiness_workflow": ".github/workflows/operational-readiness-monitor.yml",
    "live_nba_workflow": ".github/workflows/nba-live-connection.yml",
}
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="group_readiness.json")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    files = {name: (root / path).is_file() for name, path in COMPONENTS.items()}
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_live_audit_prop_integration.py", "-v"],
        cwd=root, text=True, capture_output=True, timeout=120)
    gate_test = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_player_prop_integrity_gate.py", "-v"],
        cwd=root, text=True, capture_output=True, timeout=120)
    blockers = []
    if not all(files.values()):
        blockers.append("Missing repository components: " + ", ".join(
            k for k, v in files.items() if not v))
    if test.returncode or gate_test.returncode:
        blockers.append("Offline integrity or live-audit integration tests failed")
    blockers.extend([
        "Authenticated automatic roster and injury ingestion not independently verified",
        "Independent DraftKings checkout odds not verified",
        "Original Champion-001 model probabilities and calibration not verified",
        "Settled, timestamped shadow outcomes and validated edge not verified",
    ])
    report = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "offline_group_readiness_no_paid_calls",
        "components_present": files,
        "integrity_tests_passed": test.returncode == 0 and gate_test.returncode == 0,
        "integrity_test_output_tail": (test.stdout + test.stderr + gate_test.stdout + gate_test.stderr)[-4000:],
        "production_model": "Champion-001 frozen",
        "training_started": False,
        "provider_requests": 0,
        "bets_placed": 0,
        "certified_take_count": 0,
        "status": "HOLD",
        "blockers": blockers,
    }
    dest = root / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if test.returncode == 0 and gate_test.returncode == 0 and all(files.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
