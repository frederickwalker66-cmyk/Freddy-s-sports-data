"""One-command five-gate pregame audit for all sports, fail-closed.

Usage: python -m research.pregame_five_gate --input snapshot.json --output preflight.json
Input is a research snapshot, never authenticated by mere JSON assertions.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from research.sharp_edge_source_contract import validate_pair
from research.universal_sharp_edge_board import break_even_percent


def run(snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("selections"), list):
        raise ValueError("Expected selections list")
    rows = []
    for item in snapshot["selections"]:
        if not isinstance(item, dict):
            raise ValueError("Each selection must be an object")
        quote = item.get("quote") or {}
        forecast = item.get("forecast") or {}
        contract = validate_pair(quote, forecast, now=now)
        injury = item.get("injury_and_roster_evidence")
        # Caller-supplied injury evidence is not independently verified.
        checks = {
            "1_current_sportsbook_quote": "SCHEMA_OK_AUTHENTICATION_PENDING" if contract["ready_for_authentication"] else "HOLD",
            "2_roster_injury_starters": "HOLD_UNAUTHENTICATED" if injury else "HOLD_MISSING",
            "3_native_champion_forecast": "HOLD_UNAUTHENTICATED",
            "4_verified_ev": "HOLD_PENDING_AUTHENTICATED_PROBABILITY",
            "5_final_pregame_recheck": "HOLD_PENDING_TRUSTED_REFRESH",
        }
        odds = quote.get("american_odds")
        rows.append({
            "sport": item.get("sport"),
            "selection": item.get("selection") or quote.get("selection_id"),
            "sportsbook": quote.get("sportsbook"),
            "american_odds": odds if type(odds) is int else None,
            "break_even_probability_percent": break_even_percent(odds),
            "champion_001_probability_percent": None,
            "verified_ev_percent": None,
            "decision": "HOLD",
            "gates": checks,
            "source_issues": contract["issues"],
            "certification": "NOT_AUTHENTICATED",
        })
    return {
        "status": "HOLD_UNTIL_TRUSTED_FEEDS_AND_MODEL_RECEIPTS",
        "evaluated_at": now.isoformat(),
        "requested_sport": snapshot.get("sport", "all"),
        "counts": {"TAKE": 0, "HOLD": len(rows), "PASS": 0},
        "rows": rows,
        "warning": "Untrusted snapshot values and flags cannot certify wagers. No bets placed.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run(snapshot)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "counts": result["counts"], "output": str(output)}))


if __name__ == "__main__":
    main()
