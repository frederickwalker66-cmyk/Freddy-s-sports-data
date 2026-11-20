"""Explicit certification gap diagnostics for the universal Sharp Edge board.

No external requests, model substitution, or self-attested certification.
"""
from collections import Counter


REQUIRED_GATES = (
    "authenticated_sportsbook_quote",
    "verified_event_and_roster",
    "native_champion_001_probability",
    "independent_model_verification",
    "verified_positive_expected_value",
    "pregame_timestamp",
)


def assess(report):
    if not isinstance(report, dict):
        raise TypeError("report must be a dictionary")
    board = report.get("universal_sharp_edge_board") or {}
    rows = board.get("rows") or []
    if not isinstance(rows, list):
        raise TypeError("board rows must be a list")
    statuses = Counter(row.get("decision", "HOLD") for row in rows if isinstance(row, dict))
    readiness = report.get("sharp_edge_source_readiness") or {}
    authenticated = readiness.get("archive_market_receipts_authenticated") or 0
    return {
        "certification_status": "BLOCKED_UNTIL_INDEPENDENTLY_VERIFIED",
        "authenticated_market_receipts_in_this_run": authenticated,
        "native_champion_001_certified_forecasts_in_this_run": 0,
        "certified_takes_in_this_run": 0,
        "displayed_research_candidates": len(rows),
        "displayed_decisions": {"TAKE": 0, "HOLD": statuses["HOLD"], "PASS": statuses["PASS"]},
        "required_gates": [{"gate": gate, "status": "NOT_VERIFIED"} for gate in REQUIRED_GATES],
        "next_action": "Connect trusted, independently authenticated market and native-model receipts before TAKE can be issued",
        "no_self_attested_take": True,
    }
