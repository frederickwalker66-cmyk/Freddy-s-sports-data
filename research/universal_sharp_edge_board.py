"""Every-command Sharp Edge decision and probability display, research-only.

Do not equate market-implied odds with Champion-001 forecasts.
"""
from research.sharp_edge_decision_labels import classify


def break_even_percent(odds):
    if type(odds) is not int or odds == 0 or -100 < odds < 100:
        return None
    return round(100 * ((-odds) / ((-odds) + 100) if odds < 0 else 100 / (odds + 100)), 2)


def build_universal_board(report):
    command = report.get("command", "unknown")
    candidates = report.get("research_edge_candidates") or []
    if not isinstance(candidates, list):
        candidates = []
    rows = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        odds = candidate.get("american_odds")
        # V8 research rows are not authenticated certification evidence.
        # Caller-supplied flags cannot authorize a TAKE.
        decision = classify({"decision": "PASS" if candidate.get("decision") == "PASS" else "HOLD"})
        rows.append({
            "leg": index + 1,
            "sport": candidate.get("sport") or candidate.get("league"),
            "selection": candidate.get("selection") or candidate.get("selection_id"),
            "market": candidate.get("market"),
            "sportsbook": candidate.get("sportsbook"),
            "american_odds": odds if type(odds) is int else None,
            "break_even_probability_percent": break_even_percent(odds),
            "champion_001_probability_percent": None,
            "verified_ev_percent": None,
            "decision": decision["decision"],
            "reason": decision["reason"],
        })
    return {
        "command": command,
        "requested_leagues": report.get("requested_leagues", []),
        "status": "RESEARCH_ONLY_NO_AUTHENTICATED_CERTIFICATION",
        "probability_fields": {
            "break_even_probability_percent": "market-derived, not model prediction",
            "champion_001_probability_percent": "N/A until native model output independently verified",
            "verified_ev_percent": "N/A until verified odds and native probability",
        },
        "decision_counts": {"TAKE": 0, "HOLD": sum(r["decision"] == "HOLD" for r in rows),
                            "PASS": sum(r["decision"] == "PASS" for r in rows)},
        "rows": rows,
        "no_candidates_reason": None if rows else "No authenticated or compatible market selections in this run",
    }
