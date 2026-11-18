"""V9 per-pick six-specialist consensus ledger, read-only and fail-closed.

An untrusted transcript or JSON ballot is not an authenticated vote; a 6/6
reported agreement is NOT independently certified model + sportsbook evidence.
Only reviewed candidate pick IDs are affected by any single staff HOLD/veto.
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

STAFF = (
    ("Bella", "Command Center Manager",
     "Operational coordination and original evidence/source freshness"),
    ("David", "Sports Data Analyst",
     "Schedules, player L5/L10, injuries, event identity and source provenance"),
    ("Cassidy", "Sharp Edge Analyst",
     "Native Champion-001 probability, calibration, verified sportsbook EV"),
    ("Roger", "Parlay Builder",
     "Exact market settlement, correlated legs and joint parlay probability"),
    ("Sarah", "Risk Manager",
     "Assumption challenges, vetoes and exposure management"),
    ("Adam Stone", "Audit Engineer",
     "Run logs, timestamps, workflow integrity and independent verification"),
)
assert tuple(role for _, role, _ in STAFF) == tuple(ROLE_NAMES)
ALLOWED_MARKETS = frozenset((
    "moneyline", "spread", "total", "player_points", "player_rebounds",
    "player_assists", "player_3pm", "player_pr", "player_pa", "player_ra",
    "player_pra", "player_props", "player_combos", "parlay"
))
CHOICES = frozenset(("APPROVE", "REJECT", "HOLD", "ABSTAIN"))
MAX_BYTES = 1_000_000
MAX_CANDIDATES = 80
MAX_BALLOTS = 500


def read_optional(path, key):
    if not path:
        return []
    p = Path(path)
    if not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("oversize_or_missing_manual_" + key)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get(key), list):
        raise ValueError("invalid_" + key + "_schema")
    return obj[key]


def _pick_identity(c):
    if not isinstance(c, dict):
        raise ValueError("reviewed_pick_must_be_object")
    for key in ("league", "event_id", "market", "market_id", "selection",
                "sportsbook", "quote_utc"):
        if not isinstance(c.get(key), str) or not c[key].strip() or len(c[key]) > 160:
            raise ValueError("invalid_pick_identity_" + key)
    if not c["event_id"].isdigit() or c["market"] not in ALLOWED_MARKETS:
        raise ValueError("unsupported_event_or_market")
    if c["sportsbook"] != "DraftKings":
        raise ValueError("sportsbook_must_match_exact_requested_market")
    odds = c.get("american_odds")
    if type(odds) is not int or odds == 0 or -100 < odds < 100 or not -10000 <= odds <= 10000:
        raise ValueError("invalid_american_odds")
    line = c.get("line")
    if line is not None and (type(line) not in (int, float) or not -1000 <= line <= 1000):
        raise ValueError("invalid_line")
    if c["market"] == "parlay" or isinstance(c.get("legs"), list):
        # Parlay certification requires distinct separately verified legs and
        # authenticated correlated joint probability; not available here.
        raise ValueError("parlay_requires_separate_independent_leg_verifier")
    quote_time = stamped(c["quote_utc"])
    if quote_time is None:
        raise ValueError("quote_timestamp_required")
    identity = {key: c[key] for key in (
        "league", "event_id", "market", "market_id", "selection",
        "sportsbook", "quote_utc")}
    identity["line"] = line
    identity["american_odds"] = odds
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return "pick_" + digest[:20], identity


def review(certification, meeting, candidates=None, ballots=None):
    """Output isolated recorded vote claims; never independently certify picks."""
    if not isinstance(certification, dict) or not isinstance(meeting, dict):
        raise ValueError("original_review_documents_required")
    if certification.get("final_team_decision") != "HOLD" or meeting.get("final_team_decision") != "HOLD":
        raise ValueError("unsafe_upstream_claim_of_approved_wager")
    if meeting.get("champion_001_modified") is not False or certification.get("champion_001_modified") is not False:
        raise ValueError("frozen_champion_must_remain_unchanged")
    candidates = [] if candidates is None else candidates
    ballots = [] if ballots is None else ballots
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("bad_or_unbounded_candidate_set")
    if not isinstance(ballots, list) or len(ballots) > MAX_BALLOTS:
        raise ValueError("bad_or_unbounded_ballot_set")
    meeting_time = stamped(meeting.get("meeting_utc"))
    if not meeting_time:
        raise ValueError("meeting_timestamp_required")
    certified_games = certification.get("game_reviews")
    meeting_games = meeting.get("pregame_games")
    if not isinstance(certified_games, list) or not isinstance(meeting_games, list):
        raise ValueError("game_audit_required")
    game_keys = {}
    for g in certified_games:
        if not isinstance(g, dict):
            raise ValueError("invalid_game_review")
        key = (g.get("league"), g.get("event_id"))
        if key in game_keys:
            raise ValueError("duplicate_game_audit")
        game_keys[key] = g
    meeting_keys = {(g.get("league"), g.get("event_id")): g
                    for g in meeting_games if isinstance(g, dict)}
    seen = set()
    pick_rows = []
    for candidate in candidates:
        review_id, identity = _pick_identity(candidate)
        if review_id in seen:
            raise ValueError("duplicate_identical_pick_candidate")
        seen.add(review_id)
        key = (identity["league"], identity["event_id"])
        if key not in game_keys or key not in meeting_keys:
            raise ValueError("candidate_not_present_in_current_pregame_meeting")
        start = stamped(meeting_keys[key].get("start_utc"))
        quote = stamped(identity["quote_utc"])
        if (start is None or meeting_time >= start or quote > meeting_time
                or quote >= start or (meeting_time - quote).total_seconds() > 3600):
            raise ValueError("candidate_quote_outside_pregame_window")
        recorded = {}
        conflicting = False
        for vote in ballots:
            if not isinstance(vote, dict) or vote.get("review_id") != review_id:
                continue
            role = vote.get("employee_role")
            if role not in ROLE_NAMES or role in recorded:
                conflicting = True
                continue
            choice = vote.get("choice")
            if choice not in CHOICES:
                conflicting = True
                continue
            recorded[role] = choice
        approved_count = sum(1 for v in recorded.values() if v == "APPROVE")
        vetoes = sorted(role for role,v in recorded.items() if v in ("HOLD","REJECT"))
        missing = [role for role in ROLE_NAMES if role not in recorded]
        abstain = sorted(role for role,v in recorded.items() if v == "ABSTAIN")
        reported_unanimous = (not conflicting and approved_count == len(ROLE_NAMES)
                             and not vetoes and not abstain and not missing)
        state = ("BALLOT_CONFLICT_HOLD" if conflicting else
                 "REPORTED_VETO_THIS_PICK" if vetoes else
                 "REPORTED_UNANIMOUS_BUT_UNAUTHENTICATED" if reported_unanimous else
                 "PENDING_THIS_PICK_ONLY")
        pick_rows.append({
            "review_id": review_id, "candidate": identity,
            "game": game_keys[key].get("game"),
            "reported_staff_votes": recorded,
            "recorded_approvals_unverified": approved_count,
            "recorded_staff_vetoes": vetoes,
            "recorded_abstentions": abstain,
            "missing_staff_ballots": missing,
            "conflicting_or_invalid_ballots": conflicting,
            "reported_6_of_6": reported_unanimous,
            "independently_authenticated_6_of_6": False,
            "original_champion_and_draftkings_evidence_verified": False,
            "ceo_final_signoff_authenticated": False,
            "vote_review_status": state,
            "final_release": "HOLD_NOT_CERTIFIED",
            "bet_recommendation": None,
        })
    return {
        "title": "Freddy's Picks AI V9 — Unanimous Decision Ledger",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "meeting_utc": meeting["meeting_utc"],
        "policy": ("Each reviewed pick is voted independently by six specialists; "
                   "a single HOLD, REJECT, ABSTAIN or missing ballot blocks only that pick. "
                   "The CEO must also give explicit final signoff."),
        "named_specialists": [{"name":name, "role":role, "expertise":expertise}
                              for name,role,expertise in STAFF],
        "reviewed_pick_count": len(pick_rows),
        "pick_reviews": pick_rows,
        "unreviewed_games_not_rejected": True,
        "unanimous_authenticated_picks": 0,
        "certified_best_bets": [],
        "ceo_approval_required": True,
        "champion_001_modified": False,
        "wagers_placed": 0,
        "paid_api_requests": 0,
        "shadow_stake_usd": 0,
        "meeting_decision": "HOLD",
        "warning": ("Untrusted manual vote JSON is only a record of claimed votes, not agent "
                    "identity proof. No GitHub-run or self-signed file can certify a bet. "
                    "A six-vote agreement is necessary but never sufficient; independent "
                    "Champion-001, market-specific validation and executable DraftKings "
                    "quote proof are missing."),
    }


def markdown(result):
    lines = [
        "# Freddy's Picks AI V9 — Unanimous Pregame Review", "",
        "## Decision rule",
        "**Six out of six verified staff approvals per reviewed pick, plus CEO signoff.** "
        "A veto on one pick does not block another. Still require independent "
        "original model and sportsbook verification.", "",
        "## Named expert employee cards", "",
        "| Employee | Specialist role | Responsibility |",
        "|---|---|---|"
    ]
    for r in result["named_specialists"]:
        lines.append("| " + text_safe(r["name"]) + " | " + text_safe(r["role"]) +
                     " | " + text_safe(r["expertise"]) + " |")
    lines.extend(["", "## Picks discussed in this meeting", "",
                  "| Review ID | Pick | Staff recorded yes | Vetoes | Outcome |",
                  "|---|---|---:|---|---|"])
    for row in result["pick_reviews"]:
        c = row["candidate"]
        lines.append("| " + text_safe(row["review_id"]) + " | " +
                     text_safe(c["league"] + " " + c["selection"] + " (" + c["market"] + ")") +
                     " | " + str(row["recorded_approvals_unverified"]) + "/6 | " +
                     text_safe(", ".join(row["recorded_staff_vetoes"]) or "none recorded") +
                     " | " + text_safe(row["vote_review_status"]) + " — HOLD |")
    if not result["pick_reviews"]:
        lines.append("| — | No individually reviewed picks with exact market identity | 0/6 | — | HOLD |")
    lines.extend(["", "**No certified best bets or wagers.** Unreviewed candidates are not "
                  "vetoed just because another pick failed.", "", result["warning"], ""])
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--certification-json", required=True)
    p.add_argument("--meeting-json", required=True)
    p.add_argument("--candidates-json")
    p.add_argument("--ballots-json")
    p.add_argument("--output-dir", default="v9_results")
    args = p.parse_args(argv)
    cert = json.loads(Path(args.certification_json).read_text(encoding="utf-8"))
    meet = json.loads(Path(args.meeting_json).read_text(encoding="utf-8"))
    result = review(cert, meet, read_optional(args.candidates_json, "candidates"),
                    read_optional(args.ballots_json, "ballots"))
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "V9_UNANIMOUS_PER_PICK.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = markdown(result)
    (root / "V9_UNANIMOUS_PER_PICK.md").write_text(md, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(md + "\n")
    print(json.dumps({"status": "HOLD", "reviewed_picks": result["reviewed_pick_count"],
                      "certified_best_bets": 0, "wagers": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
