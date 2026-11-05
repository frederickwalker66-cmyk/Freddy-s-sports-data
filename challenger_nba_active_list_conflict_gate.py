"""NBA game-day roster versus injury-PDF contradiction gate (research ONLY).

Read the exact already archived, *scheduled-state*, NBA-owned pregame liveData
boxscores. Never treat roster 'ACTIVE' as authenticated FINAL game Active List.
Flags are manual-review signals, not active/inactive certification or bets.
No network access: source bytes originate from earlier actual pregame capture.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from challenger_nba_injury_pdf_player_rows import TEAM_CODES, TEAMS, STATUSES
from challenger_nba_player_two_source_review import canonical
from challenger_nba_pregame_roster_identity import (
    MAX_BOX_BYTES, RESULT_TYPE, MAX_GAMES, decode_json, parse_pregame_nba_box,
)
from challenger_nba_schedule_clock import nba_team_name, NBA_SCHEDULE_URL, official_nba_events
from challenger_prospective_outcome_validation import instant

EASTERN = ZoneInfo("America/New_York")
MAX_ROWS = 300
MAX_SNAPSHOT_AGE = 90 * 60
MAX_INJURY_AGE_BEFORE_ROSTER = 3 * 3600
PRELIMINARY_STATUSES = {"ACTIVE", "INACTIVE"}
OUTPUT_TYPE = "challenger_nba_injury_vs_scheduled_roster_status_review_only"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _blocked_report(reason, count):
    return {
        "stage": "challenger_nba_game_day_active_list_conflict_gate_review_only",
        "status": reason, "source_rows_reviewed": count,
        "source_statuses": {}, "reported_out_vs_roster_active_conflicts": 0,
        "reported_available_vs_roster_inactive_conflicts": 0,
        "near_tipoff_manual_conflicts": 0,
        "independently_confirmed_game_day_active_players": 0,
        "independently_confirmed_game_day_inactive_players": 0,
        "official_complete_active_list_authenticated": False,
        "verified_nba_espn_draftkings_player_id_crosswalks": 0,
        "qualified_player_prop_training_observations": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("LiveData status is a preliminary game-roster observation, "
                    "NOT the authenticated official final Active List. "
                    "An injury report status is not a DNP settlement or active "
                    "roster proof, and omitted players have unknown status."),
    }


def _validate(report, rows):
    if (not isinstance(report, dict)
        or report.get("stage") != "challenger_nba_scheduled_roster_identity_review_only"
        or report.get("independently_confirmed_active_players") != 0
        or report.get("verified_nba_to_espn_to_draftkings_player_id_crosswalks") != 0
        or report.get("qualified_player_prop_training_observations") != 0
        or report.get("certified_champion_001_predictions") != 0
        or report.get("certified_challenger_001_predictions") != 0
        or report.get("certified_positive_ev_bets") != 0
        or report.get("bet_ready_selections") != 0
        or report.get("automated_bets_placed") != 0
        or report.get("champion_001_modified") is not False
        or not isinstance(rows, list) or len(rows) > MAX_ROWS):
        raise ValueError("untrusted_or_promoted_nba_roster_research_report")
    hashes = report.get("original_source_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("original_nba_source_hash_manifest_missing")
    for filename, digest in hashes.items():
        if (not re.fullmatch(r"nba_official_schedule\.json|nba_pregame_box_\d{10}\.json", filename)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("invalid_original_roster_source_manifest")
    if report.get("official_schedule_source_available") is True:
        if (hashes.get("nba_official_schedule.json") !=
            report.get("official_nba_schedule_original_sha256")):
            raise ValueError("scheduled_nba_source_hash_not_in_manifest")
    elif hashes:
        raise ValueError("unavailable_schedule_has_source_bytes")
    ids = set()
    for r in rows:
        if (not isinstance(r, dict) or r.get("record_type") != RESULT_TYPE
            or r.get("league") != "nba"
            or r.get("nba_roster_match_is_identity_candidate_only") is not True
            or r.get("independently_authenticated_player_id_crosswalk") is not False
            or r.get("current_game_active_inactive_verified") is not False
            or r.get("roster_status_is_final_active_list") is not False
            or r.get("draftkings_player_id_verified") is not False
            or r.get("qualified_for_player_prop_training") is not False
            or r.get("certified_prediction") is not False
            or r.get("bet_ready") is not False
            or r.get("champion_001_modified") is not False
            or r.get("nba_report_designation") not in STATUSES):
            raise ValueError("unsafe_nba_injury_roster_match_record")
        game = r.get("nba_game_id_candidate")
        pid = r.get("nba_person_id_candidate")
        if game is not None and (not isinstance(game, str) or
                                re.fullmatch(r"\d{10}", game) is None):
            raise ValueError("invalid_early_nba_game_identity")
        if pid is not None:
            if (game is None or not isinstance(pid, str) or not pid.isdecimal()
                or r.get("crosscheck_status") not in (
                    "nba_person_id_candidate_from_exact_scheduled_roster_research_only",
                    "nba_person_id_candidate_with_espn_game_crosswalk_research_only")):
                raise ValueError("unverified_nba_person_id_promotion")
            unique = (game, pid)
            if unique in ids:
                raise ValueError("duplicate_same_game_nba_person_id")
            ids.add(unique)
    return hashes


def _read_sources(root, hashes):
    source_root = root / "nba_roster_original_source_bytes"
    loaded = {}
    for filename, expected in hashes.items():
        raw = (source_root / filename).read_bytes()
        if sha(raw) != expected:
            raise ValueError("captured_original_nba_roster_bytes_changed")
        limit = MAX_BOX_BYTES if filename.startswith("nba_pregame_box_") else 18_000_000
        loaded[filename] = decode_json(raw, limit)
    if "nba_official_schedule.json" in loaded:
        # The original NBA schedule itself must still be parsable and contain
        # unique NBA-operated game identifiers.
        games = official_nba_events(loaded["nba_official_schedule.json"])
        ids = [x["official_nba_game_id"] for x in games]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_official_game_in_schedule")
    return loaded


def _planned(raw, game_id, row):
    g = raw.get("game")
    if not isinstance(g, dict):
        raise ValueError("missing_captured_nba_scheduled_game")
    start = instant(g.get("gameTimeUTC"))
    home, away = g.get("homeTeam"), g.get("awayTeam")
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise ValueError("missing_captured_nba_game_clubs")
    teams = {}
    for side, item in (("home", home), ("away", away)):
        teams[side] = nba_team_name(
            str(item.get("teamCity") or "") + " " + str(item.get("teamName") or ""))
        if teams[side] not in TEAMS:
            raise ValueError("unrecognized_captured_nba_club")
    if teams["home"] == teams["away"]:
        raise ValueError("same_nba_team_two_sides")
    if (start.astimezone(EASTERN).date().isoformat() != row.get("game_date_et")
        or TEAMS[teams["away"]] + "@" + TEAMS[teams["home"]] != row.get("matchup")
        or row.get("nba_report_team") not in teams.values()):
        raise ValueError("wrong_nba_game_or_team_for_injury_row")
    return {"game_id": game_id, "start": start,
            "home": teams["home"], "away": teams["away"]}


def evaluate(root, at=None):
    at = at or datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("must_observe_roster_reconciliation_with_aware_time")
    at = at.astimezone(timezone.utc)
    root = Path(root)
    r = json.loads((root / "nba_pregame_roster_identity_report.json").read_text())
    rows = [json.loads(line) for line in
            (root / "nba_pregame_roster_identity_review.jsonl").read_text().splitlines()
            if line.strip()]
    hashes = _validate(r, rows)
    if not rows:
        return [], _blocked_report("no_injury_players_with_roster_evidence", 0)
    if r.get("official_schedule_source_available") is not True:
        result = _blocked_report("official_nba_schedule_or_roster_unavailable", len(rows))
        return [_make_blocked_row(x, "no_verified_scheduled_roster_source") for x in rows], result
    original = _read_sources(root, hashes)
    records = []
    counts = Counter()
    cached = {}
    for entry in rows:
        game, pid = entry.get("nba_game_id_candidate"), entry.get("nba_person_id_candidate")
        out = _make_blocked_row(entry, "nba_person_id_or_game_not_matched")
        if pid is None or game is None:
            records.append(out)
            counts[out["reconciliation_status"]] += 1
            continue
        filename = "nba_pregame_box_" + game + ".json"
        raw = original.get(filename)
        if raw is None:
            out["reconciliation_status"] = "original_scheduled_nba_boxscore_not_archived"
            records.append(out)
            counts[out["reconciliation_status"]] += 1
            continue
        observed = instant(entry.get("roster_original_observed_at_utc"))
        injury_at = instant(entry.get("nba_report_original_observed_at_utc"))
        if not injury_at <= observed <= at:
            raise ValueError("nba_injury_and_roster_observations_out_of_order")
        planned = _planned(raw, game, entry)
        scheduled = official_nba_events(original["nba_official_schedule.json"])
        official_matches = [x for x in scheduled if x["official_nba_game_id"] == game]
        if (len(official_matches) != 1
            or abs((official_matches[0]["start"]-planned["start"]).total_seconds()) > 60
            or official_matches[0]["home"] != planned["home"]
            or official_matches[0]["away"] != planned["away"]):
            raise ValueError("nba_boxscore_and_schedule_start_disagree")
        if observed >= planned["start"]:
            raise ValueError("postgame_or_live_nba_roster_in_pregame_archive")
        if filename not in cached:
            cached[filename] = parse_pregame_nba_box(
                (root / "nba_roster_original_source_bytes" / filename).read_bytes(),
                planned, observed)
        sides = cached[filename]
        side = "home" if entry["nba_report_team"] == planned["home"] else "away"
        key = canonical(entry.get("nba_report_name"))
        source = sides[side].get(key)
        if (source is None or source["person_id"] != pid
            or source["team_id"] != entry.get("official_nba_team_id_candidate")
            or source["raw_game_roster_status"] != entry.get("source_nba_roster_raw_status")
            or source["raw_not_playing_reason"] != entry.get("source_nba_not_playing_reason")):
            raise ValueError("nba_person_roster_source_identity_or_status_disagreement")
        if (entry.get("roster_original_raw_sha256") != hashes[filename]):
            raise ValueError("nba_person_original_source_row_hash_mismatch")
        seconds = (planned["start"] - observed).total_seconds()
        rec_status = (entry.get("source_nba_roster_raw_status") or "").strip().upper()
        out.update({
            "nba_person_id_candidate": pid,
            "nba_official_game_id_candidate": game,
            "roster_source_status_raw": entry.get("source_nba_roster_raw_status"),
            "roster_snapshot_observed_utc": observed.isoformat(),
            "source_game_start_utc": planned["start"].isoformat(),
            "minutes_before_game_when_observed": round(seconds / 60, 2),
            "roster_status_category_preliminary": (
                rec_status.lower() if rec_status in PRELIMINARY_STATUSES else "unknown"),
        })
        if seconds > MAX_SNAPSHOT_AGE:
            status = "roster_source_observed_more_than_90min_before_tipoff"
        elif (observed - injury_at).total_seconds() > MAX_INJURY_AGE_BEFORE_ROSTER:
            status = "injury_document_older_than_three_hours_at_roster_observation"
        elif rec_status not in PRELIMINARY_STATUSES:
            status = "nba_game_roster_status_unknown_or_not_explicit"
        elif entry["nba_report_designation"] == "Out" and rec_status == "ACTIVE":
            status = "reported_out_vs_preliminary_roster_active_conflict"
        elif entry["nba_report_designation"] == "Available" and rec_status == "INACTIVE":
            status = "reported_available_vs_preliminary_roster_inactive_conflict"
        elif entry["nba_report_designation"] == "Out" and rec_status == "INACTIVE":
            status = "two_source_out_inactive_agreement_not_final_active_list"
        else:
            status = "provisional_game_roster_status_not_final_active_list"
        out["reconciliation_status"] = status
        out["potential_roster_injury_disagreement_for_manual_review"] = status in (
            "reported_out_vs_preliminary_roster_active_conflict",
            "reported_available_vs_preliminary_roster_inactive_conflict")
        counts[status] += 1
        records.append(out)
    report = _blocked_report("research_reconciliation_completed_no_active_list_certification",
                             len(rows))
    report.update({
        "source_statuses": dict(sorted(counts.items())),
        "reported_out_vs_roster_active_conflicts":
            counts["reported_out_vs_preliminary_roster_active_conflict"],
        "reported_available_vs_roster_inactive_conflicts":
            counts["reported_available_vs_preliminary_roster_inactive_conflict"],
        "near_tipoff_manual_conflicts":
            sum(x["potential_roster_injury_disagreement_for_manual_review"] for x in records),
        "original_nba_roster_sha256": hashes,
    })
    return records, report


def _make_blocked_row(entry, status):
    return {
        "record_type": OUTPUT_TYPE,
        "league": "nba",
        "nba_report_team": entry.get("nba_report_team"),
        "nba_report_player": entry.get("nba_report_name"),
        "nba_injury_designation": entry.get("nba_report_designation"),
        "nba_official_game_id_candidate": entry.get("nba_game_id_candidate"),
        "nba_person_id_candidate": None,
        "reconciliation_status": status,
        "roster_status_category_preliminary": "unknown",
        "potential_roster_injury_disagreement_for_manual_review": False,
        "official_complete_active_list_verified": False,
        "current_game_active_inactive_independently_confirmed": False,
        "independent_pregame_player_minutes_verified": False,
        "draftkings_player_identity_verified": False,
        "player_participation_or_dnp_verified": False,
        "bookmaker_void_or_settlement_verified": False,
        "qualified_for_player_prop_training": False,
        "model_player_prop_probability": None,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster-dir", required=True)
    p.add_argument("--output-dir", default="nba_active_list_conflicts")
    args = p.parse_args(argv)
    reviewed, report = evaluate(args.roster_dir)
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "nba_active_list_conflict_review.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in reviewed), encoding="utf8")
    (root / "nba_active_list_conflict_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"rows": len(reviewed), "conflicts_for_manual_review":
                      report["near_tipoff_manual_conflicts"], "confirmed_active": 0,
                      "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
