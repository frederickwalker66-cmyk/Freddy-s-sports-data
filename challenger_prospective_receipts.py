"""Capture and inspect original pregame research archive bytes for eight sports.

This checks an archive against a same-run SHA-256 receipt and time ordering.
A self-issued receipt is NOT independent authentication, source-publication
evidence, a certified training observation, or a bet authorization.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from challenger_prospective_outcome_validation import instant, validate_snapshot

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls",
           "uefa_champions_league")
SCHEMA = "challenger_prospective_original_bytes_receipt_v1"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _iso(when):
    if not isinstance(when, datetime) or when.tzinfo is None:
        raise ValueError("UTC evidence time must have timezone")
    return when.astimezone(timezone.utc).isoformat()


def _rows(data):
    if not isinstance(data, bytes):
        raise TypeError("snapshot archive must be original bytes")
    lines = [raw for raw in data.splitlines(keepends=True) if raw.strip()]
    rows = []
    for line in lines:
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL snapshots must contain objects")
        rows.append((line, row))
    return rows


def _status(row, time):
    league = row.get("league")
    if league not in LEAGUES:
        return "unsupported_league"
    try:
        (observed_league, identity), captured = validate_snapshot(row, time)
        start = instant(row["event_start_utc"])
        if observed_league != league or not identity.isdigit():
            return "invalid_event_identity"
        if captured > time or time >= start:
            return "receipt_not_before_game"
    except (ValueError, KeyError, TypeError, OverflowError):
        return "invalid_or_late_pregame_capture"
    return "timed_capture_for_review_only"


def make_receipt(source, run_id, receipt_at):
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("GitHub run ID required, numeric only")
    created = instant(_iso(receipt_at))
    lines = _rows(source)
    seen = set()
    records = []
    for position, (raw, row) in enumerate(lines):
        league = row.get("league")
        event_id = str(row.get("espn_schedule_event_id"))
        key = (league, event_id)
        if key in seen:
            raise ValueError("duplicate event in one original archive")
        seen.add(key)
        status = _status(row, created)
        records.append({
            "line": position + 1,
            "league": league,
            "event_id": event_id,
            "raw_jsonl_line_sha256": _sha(raw),
            "status": status,
        })
    return {
        "schema": SCHEMA,
        "github_actions_run_id_self_reported": run_id,
        "receipt_created_utc": _iso(created),
        "raw_file_sha256": _sha(source),
        "raw_file_bytes": len(source),
        "raw_nonempty_lines": len(records),
        "records": records,
        "receipt_independently_authenticated": False,
        "original_source_publication_verified": False,
        "independent_final_adjudication_verified": False,
        "qualified_for_challenger_training": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
    }


def verify_receipt(source, manifest, expected_run_id=None, now=None):
    """Tamper/late/identity checks, never standalone independent source proof."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("invalid receipt manifest schema")
    if expected_run_id is not None and (
            str(expected_run_id) != manifest.get("github_actions_run_id_self_reported")):
        raise ValueError("run ID mismatch against archive directory")
    created = instant(manifest["receipt_created_utc"])
    reference = now or datetime.now(timezone.utc)
    current = instant(_iso(reference))
    if created > current:
        raise ValueError("future-dated receipt")
    if (manifest.get("raw_file_sha256") != _sha(source)
            or manifest.get("raw_file_bytes") != len(source)):
        raise ValueError("original archive raw bytes differ from receipt")
    rows = _rows(source)
    refs = manifest.get("records")
    if not isinstance(refs, list) or len(refs) != len(rows):
        raise ValueError("record count differs from captured receipt")
    if manifest.get("raw_nonempty_lines") != len(rows):
        raise ValueError("line count differs")
    seen = set()
    counts = Counter()
    by_league = {league: Counter() for league in LEAGUES}
    for i, ((raw, row), recorded) in enumerate(zip(rows, refs), 1):
        if not isinstance(recorded, dict):
            raise ValueError("invalid receipt entry")
        league = row.get("league")
        eid = str(row.get("espn_schedule_event_id"))
        key = (league, eid)
        if key in seen:
            raise ValueError("duplicate event identity in archive")
        seen.add(key)
        status = _status(row, created)
        if (recorded.get("line") != i or recorded.get("league") != league
                or recorded.get("event_id") != eid
                or recorded.get("raw_jsonl_line_sha256") != _sha(raw)
                or recorded.get("status") != status):
            raise ValueError("captured event receipt identity/status mismatch")
        counts[status] += 1
        if league in by_league:
            by_league[league][status] += 1
    if any(manifest.get(k) != 0 for k in (
            "certified_champion_001_predictions",
            "certified_challenger_001_predictions",
            "bet_ready_selections", "automated_bets_placed",
    )) or manifest.get("champion_001_modified") is not False:
        raise ValueError("untrusted receipt promotes betting or Champion")
    if any(manifest.get(k) is not False for k in (
            "receipt_independently_authenticated",
            "original_source_publication_verified",
            "independent_final_adjudication_verified",
            "qualified_for_challenger_training",
    )):
        raise ValueError("untrusted source claimed independent certification")
    return {
        "run_id_self_reported": manifest["github_actions_run_id_self_reported"],
        "original_bytes_match_self_issued_receipt": True,
        "timed_research_captures": counts["timed_capture_for_review_only"],
        "record_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "by_league": {league: dict(sorted(c.items())) for league, c in by_league.items()},
        "independently_authenticated_captures": 0,
        "independently_verified_training_examples": 0,
        "no_training_or_wager_promotion": True,
    }


def check_archive_root(root, now=None):
    """Inspect saved original Github-run folders without re-fetching any scores."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError("missing research archive root")
    counters = Counter()
    coverage = {league: Counter() for league in LEAGUES}
    for snapshot in sorted(root.rglob("prospective_event_evidence.jsonl")):
        counters["source_archives_found"] += 1
        receipt = snapshot.parent / "point_in_time_receipt.json"
        if not receipt.is_file():
            counters["archive_missing_receipt"] += 1
            continue
        try:
            manifest = json.loads(receipt.read_text(encoding="utf-8"))
            directory_id = snapshot.parent.name
            expected = directory_id if directory_id.isdecimal() else None
            checked = verify_receipt(snapshot.read_bytes(), manifest, expected, now)
        except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError):
            counters["receipt_invalid_or_mismatch"] += 1
            continue
        counters["archive_bytes_checked"] += 1
        counters["events_with_self_issued_receipt_and_valid_timing"] += checked[
            "timed_research_captures"]
        for league, statuses in checked["by_league"].items():
            coverage[league].update(statuses)
    return {
        "stage": "all_sports_original_archive_receipt_integrity_only",
        "supported_leagues": list(LEAGUES),
        "archive_coverage": dict(sorted(counters.items())),
        "by_league": {league: dict(sorted(c.items()))
                      for league, c in coverage.items()},
        "github_actions_run_id_crosschecked_with_platform": False,
        "original_raw_bytes_checked_against_self_issued_receipts_only": True,
        "independently_verified_training_examples": 0,
        "trained_models_created": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "Same-run hash detects subsequent byte changes but is NOT "
            "independently timestamped, platform-signed, or proof of source "
            "publication at game time. Missing receipts and unchecked market "
            "settlement remain research-only blockers."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("capture", "inspect"), required=True)
    parser.add_argument("--snapshots")
    parser.add_argument("--run-id")
    parser.add_argument("--snapshot-root")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.mode == "capture":
        if not args.snapshots or not args.run_id:
            parser.error("capture requires --snapshots and --run-id")
        result = make_receipt(
            Path(args.snapshots).read_bytes(),
            str(args.run_id),
            datetime.now(timezone.utc))
    else:
        if not args.snapshot_root:
            parser.error("inspect requires --snapshot-root")
        result = check_archive_root(args.snapshot_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
