"""Sanitized, observed research-run evidence status; never certifies a wager."""
from __future__ import annotations
import json
from pathlib import Path

def summarize(report):
    if not isinstance(report, dict):
        raise ValueError("report_must_be_object")
    gate = report.get("nba_live_price_research_gate")
    gate = gate if isinstance(gate, dict) else {}
    return {
        "report_type": "FREDDYS_RUN_EVIDENCE_STATUS",
        "source": "actual_one_command_report",
        "command": report.get("command") if isinstance(report.get("command"), str) else "UNKNOWN",
        "nba_price_gate_present": bool(gate),
        "nba_price_candidates_examined": gate.get("candidate_count", 0) if type(gate.get("candidate_count")) is int else 0,
        "verified_player_crosswalks_loaded": gate.get("verified_player_crosswalks_loaded", 0) if type(gate.get("verified_player_crosswalks_loaded")) is int else 0,
        "certified_positive_ev_bets": 0,
        "live_draftkings_checkout_verified": False,
        "native_champion_001_probabilities_verified": 0,
        "decision": "HOLD",
        "champion_001_modified": False,
        "evidence_limit": "Research report is not authenticated checkout or native-model certification",
    }

def main():
    path = Path("v8_results/one_command/ONE_COMMAND_REPORT.json")
    report = json.loads(path.read_text()) if path.is_file() else {}
    output = Path("v8_results/one_command/RUN_EVIDENCE_STATUS.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summarize(report), indent=2, sort_keys=True) + "\n")
    print(output.read_text())

if __name__ == "__main__":
    main()
