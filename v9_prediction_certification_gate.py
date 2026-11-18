"""V9 per-game certification evidence gap review (read-only, never self-certifies).

The outputs are a structured audit of *why* an archived game cannot be
advertised as a certified Champion-001 Sharp Edge selection. Authenticating
source-owned receipts and a frozen native model requires independent custody
outside this GitHub repository; JSON fields claiming success are not proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from v9_sharp_edge_evidence_board import ROLE_NAMES, stamped, text_safe

REQUIRED_GATES = (
    "original_frozen_champion_001_provenance",
    "independent_native_model_probability",
    "market_specific_forward_calibration",
    "independent_same_game_identity",
    "exact_sportsbook_market_and_settlement",
    "executable_sportsbook_quote_at_review",
    "current_player_injury_and_active_status",
    "independent_model_release_review",
)
MAX_GAMES = 200
MAX_ROWS = 400
MAX_REPORT_BYTES = 2_000_000


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def archive_report(root, relative):
    """Return optional upstream JSON provenance without authenticating its author."""
    p = Path(root) / relative
    if not p.is_file() or p.stat().st_size > MAX_REPORT_BYTES:
        return None
    raw = p.read_bytes()
    try:
        doc = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    return {"data": doc, "path": relative, "downloaded_sha256": _sha(raw),
            "original_independent_source_authentication": False}


def _source_status(board, meeting):
    source = board.get("source_manifest", {}).get("schedule")
    if not isinstance(source, dict) or source.get("status") != "READ_EXISTING_ARCHIVE_ONLY":
        return "NO_READABLE_SCHEDULE_ARCHIVE"
    run_id = source.get("run_id")
    if (type(run_id) is not int or run_id <= 0 or
            run_id != meeting.get("source_run_id")):
        return "MEETING_ARCHIVE_RUN_MISMATCH"
    t = stamped(source.get("run_created_at_utc"))
    meeting_time = stamped(meeting.get("meeting_utc"))
    if t is None or meeting_time is None:
        return "UNKNOWN_SOURCE_OR_MEETING_CLOCK"
    mins = (meeting_time-t).total_seconds()/60
    if mins < -5 or mins > 120:
        return "SOURCE_STALE_OR_FUTURE"
    return "RECENT_RESEARCH_ARCHIVE_NOT_INDEPENDENTLY_AUTHENTICATED"


def _valid_game(g):
    if not isinstance(g, dict):
        return False
    s = stamped(g.get("start_utc"))
    observed = stamped(g.get("source_observed_utc"))
    if s is None or observed is None or observed >= s:
        return False
    return (isinstance(g.get("game"), str) and bool(g["game"].strip())
            and isinstance(g.get("league"), str) and bool(g["league"].strip())
            and isinstance(g.get("event_id"), str) and g["event_id"].isdigit())


def inspect(board, meeting, champion=None, release=None):
    if not isinstance(board, dict) or not isinstance(meeting, dict):
        raise ValueError("v9_evidence_board_and_pregame_meeting_required")
    if board.get("classification") != "RESEARCH_ONLY_HOLD":
        raise ValueError("uncertified_v9_evidence_board_required")
    if meeting.get("final_team_decision") != "HOLD":
        raise ValueError("premature_meeting_certification_not_accepted")
    if board.get("champion_001_modified") is not False or meeting.get("champion_001_modified") is not False:
        raise ValueError("frozen_champion_invariant_violated")
    games = meeting.get("pregame_games")
    rows = board.get("game_and_prop_display_rows")
    if not isinstance(games, list) or len(games) > MAX_GAMES:
        raise ValueError("bounded_game_records_required")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("bounded_research_rows_required")
    source_status = _source_status(board, meeting)
    seen = set()
    reviews = []
    for g in games:
        if not _valid_game(g):
            raise ValueError("invalid_original_source_game_identity_or_time")
        key = (g["league"].lower(), g["event_id"])
        if key in seen:
            raise ValueError("duplicate_pregame_event_not_certifiable")
        seen.add(key)
        game_time = stamped(g["start_utc"])
        met_at = stamped(meeting.get("meeting_utc"))
        if met_at is None or game_time <= met_at:
            raise ValueError("post_tipoff_game_must_not_be_pregame_certified")
        # Display exact-name context as context only. The V8 display archive does
        # not contain a reliably joined native event ID + verified sportsbook ID.
        # A matching game string is NOT evidence of exact market identity.
        name_only = [r for r in rows
                     if isinstance(r, dict) and
                     str(r.get("league") or "").lower() == key[0] and
                     r.get("game") == g["game"]]
        counts = dict(Counter(str(r.get("category") or "unknown") for r in name_only))
        research_ref = [{"source_run_id": r.get("evidence", {}).get("run_id")
                          if isinstance(r.get("evidence"), dict) else None,
                         "json_array_pointer": r.get("evidence", {}).get("json_array_pointer")
                          if isinstance(r.get("evidence"), dict) else None}
                        for r in name_only[:15]]
        reviews.append({
            "league": g["league"], "event_id": g["event_id"],
            "game": g["game"], "start_eastern": g.get("start_eastern"),
            "source_run_id": g.get("source_run_id"),
            "meeting_time_utc": meeting.get("meeting_utc"),
            "source_status": source_status,
            "name_only_research_market_count": len(name_only),
            "name_only_research_categories": counts,
            "unverified_research_pointers": research_ref,
            "name_only_market_identity_verified": False,
            "certification_evidence_gates": {
                name: "BLOCKED_MISSING_EXTERNAL_ORIGINAL_PROOF" for name in REQUIRED_GATES},
            "player_prop_injury_available_verified": False,
            "native_champion_001_probability": None,
            "executable_draftkings_odds": None,
            "certified_expected_value": None,
            "proposed_certified_selection": None,
            "qualified_shadow_prediction": False,
            "decision": "HOLD",
        })
    champion_data = champion.get("data") if isinstance(champion, dict) else None
    release_data = release.get("data") if isinstance(release, dict) else None
    # Even self-authored upstream claims of verification must not authenticate
    # themselves; these are context only, never release gates.
    source_context = {
        "champion_original_executable_reported": (champion_data.get("original_executable_verified")
                                               if isinstance(champion_data, dict) else None),
        "champion_provenance_independently_authenticated_here": False,
        "champion_authentication_status_reported": (champion_data.get("result")
                                                    if isinstance(champion_data, dict) else None),
        "model_release_reported": (release_data.get("release_decision")
                                   if isinstance(release_data, dict) else None),
        "independent_release_approval_verified_here": False,
        "archive_report_sha256_not_publisher_signature": {
            "champion": champion.get("downloaded_sha256") if isinstance(champion, dict) else None,
            "release": release.get("downloaded_sha256") if isinstance(release, dict) else None,
        },
    }
    meeting_reviews = [{
        "employee": name, "decision": "HOLD",
        "finding": (
            "Check original schedule and event identity" if i == 0 else
            "Cross-check injury, active status and game sources" if i == 1 else
            "Require frozen Champion output and calibrated market probability" if i == 2 else
            "Do not calculate parlay probability from unqualified legs" if i == 3 else
            "Veto prices without current executable sportsbook evidence" if i == 4 else
            "Retain report hashes, original-run pointers and blockers")
    } for i, name in enumerate(ROLE_NAMES)]
    return {
        "title": "Freddy's Picks AI V9 - Game-Level Prediction Certification Readiness",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "type": "read_only_certification_gap_audit",
        "research_source_status": source_status,
        "league_game_count": len(reviews),
        "six_employee_reviews": meeting_reviews,
        "game_reviews": reviews,
        "required_original_evidence": list(REQUIRED_GATES),
        "upstream_research_context_not_approval": source_context,
        "champion_001_modified": False, "challenger_promoted": False,
        "certified_predictions": 0, "qualified_shadow_predictions": 0,
        "certified_positive_ev": 0, "qualified_parlays": 0,
        "automated_wagers": 0, "paid_api_requests": 0, "shadow_stake_usd": 0,
        "final_team_decision": "HOLD",
        "warning": ("GitHub-run metadata, archive hashes, DraftKings-labelled aggregator odds, "
                    "research probabilities, timestamps and six-role consensus cannot independently "
                    "authenticate native Champion-001 forecasts or executable checkout quotes. "
                    "No certification until a separately controlled evidence-verification process exists."),
    }


def markdown(board):
    lines = [
        "# Freddy's Picks AI V9 - Game-Level Prediction Certification",
        "", "**Final decision: HOLD. No certified picks, EV or parlays.**",
        "Source: " + text_safe(board["research_source_status"]), "",
        "## Evidence gates", "",
        "| Required original proof | Gate |", "|---|---|",
    ]
    for gate in board["required_original_evidence"]:
        lines.append("| " + text_safe(gate.replace("_", " ")) +
                     " | BLOCKED - external evidence not authenticated |")
    lines.extend(["", "## Six-employee meeting", "", "| Employee | Review |",
                  "|---|---|"])
    for role in board["six_employee_reviews"]:
        lines.append("| " + text_safe(role["employee"]) + " | " +
                     text_safe(role["finding"]) + " |")
    lines.extend(["", "## Games reviewed individually", "",
                  "| League | Matchup | Kickoff (Eastern) | Name-only research rows | Decision |",
                  "|---|---|---|---:|---|"])
    for game in board["game_reviews"]:
        lines.append("| " + text_safe(game["league"]) + " | " +
                     text_safe(game["game"]) + " | " +
                     text_safe(game["start_eastern"]) + " | " +
                     str(game["name_only_research_market_count"]) + " | HOLD |")
    if not board["game_reviews"]:
        lines.append("| -- | No pregame event in the meeting's approved window | -- | 0 | HOLD |")
    lines.extend([
        "", "## Native model and bookmaker evidence",
        "The upstream archives can be indexed, but cannot prove original model authenticity, "
        "live DraftKings checkout availability or market-specific expected value.",
        "No claim of 0% win probability is implied by missing evidence.",
        "", board["warning"], "",
    ])
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--board-json", required=True)
    p.add_argument("--meeting-json", required=True)
    p.add_argument("--archive-root", default="v9_results/_cached_source/schedule")
    p.add_argument("--output-dir", default="v9_results")
    args = p.parse_args(argv)
    board = json.loads(Path(args.board_json).read_text(encoding="utf-8"))
    meeting = json.loads(Path(args.meeting_json).read_text(encoding="utf-8"))
    run_id = meeting.get("source_run_id")
    origin = Path(args.archive_root) / str(run_id) if type(run_id) is int and run_id > 0 else None
    champion = archive_report(origin, "model_completion/champion_authentication.json") if origin else None
    release = archive_report(origin, "model_completion/release_readiness.json") if origin else None
    result = inspect(board, meeting, champion=champion, release=release)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "V9_PREDICTION_CERTIFICATION_GAPS.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    page = markdown(result)
    (output / "V9_PREDICTION_CERTIFICATION_GAPS.md").write_text(page, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as target:
            target.write(page + "\n")
    print(json.dumps({"status": "HOLD", "games": len(result["game_reviews"]),
                      "certified_predictions": 0, "wagers": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
