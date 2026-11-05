"""#84 rolling prospective source ledger across independently archived GitHub runs.

Current/new original ESPN schedule bytes are verified per archived event.
Previous scans are optional and must pass identical checks. Repeated captures
of one future event count as ONE research identity, never additional training
examples. Historical feature as-of and outcome labels remain unverified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from challenger_prospective_outcome_validation import instant
from independent_schedule_review import SOURCES

MAX_RUNS = 8
MAX_EVENTS_PER_RUN = 4000
SHA = re.compile(r"[a-f0-9]{64}\Z")


def inspect_capture(folder):
    root = Path(folder)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("invalid_pregame_capture_directory")
    coverage = json.loads((root / "eight_sport_schedule_coverage.json").read_text())
    data = (root / "prospective_event_evidence.jsonl").read_text()
    events = [json.loads(line) for line in data.splitlines() if line.strip()]
    if (len(events) > MAX_EVENTS_PER_RUN
            or set(coverage.get("by_league", {})) != set(SOURCES)
            or coverage.get("archived_games_matching_exact_original_event_fields") != len(events)
            or coverage.get("champion_001_modified") is not False
            or coverage.get("certified_positive_ev_bets") != 0):
        raise ValueError("unreconciled_original_pregame_capture")
    original = root / "espn_original_schedule_bytes"
    if not original.is_dir() or original.is_symlink():
        raise ValueError("missing_same_run_espn_source_bytes")
    raw_files = [p for p in original.rglob("*") if p.is_file()]
    if len(raw_files) > 200 or any(p.is_symlink() or p.stat().st_size > 3_000_000 for p in raw_files):
        raise ValueError("oversized_or_linked_espn_original_source_bytes")
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files}
    checked, keys = [], set()
    for row in events:
        if (not isinstance(row, dict)
                or row.get("record_type") != "prospective_evidence_snapshot_research_only"
                or row.get("league") not in SOURCES
                or row.get("model_probability") is not None
                or row.get("certified_prediction") is not False
                or row.get("qualified_for_challenger_backtest") is not False
                or row.get("bet_ready") is not False
                or row.get("champion_001_modified") is not False):
            raise ValueError("unsafe_pregame_evidence_archive")
        league = row["league"]
        event = row.get("espn_schedule_event_id")
        digest = row.get("espn_original_schedule_sha256_research_only")
        if (not isinstance(event, str) or not event.isdecimal()
                or not isinstance(digest, str) or not SHA.fullmatch(digest)
                or digest not in hashes or (league, event) in keys):
            raise ValueError("source_sha_or_event_identity_unreconciled")
        keys.add((league, event))
        received = instant(row["schedule_observed_at_utc"])
        archived = instant(row["snapshot_completed_at_utc"])
        start = instant(row["event_start_utc"])
        if not received <= archived < start:
            raise ValueError("source_not_captured_before_kickoff")
        home, away = row.get("home_team"), row.get("away_team")
        if (not isinstance(home, str) or not home.strip() or
            not isinstance(away, str) or not away.strip() or
            home == away):
            raise ValueError("malformed_teams_in_pregame_snapshot")
        checked.append({
            "league": league, "espn_event_id": event,
            "home_team": home, "away_team": away,
            "event_start_utc": start.isoformat(),
            "original_espn_sha256": digest,
            "schedule_observed_at_utc": received.isoformat(),
            "archive_completed_utc": archived.isoformat(),
        })
    return checked


def aggregate(captures):
    if not isinstance(captures, dict) or not 1 <= len(captures) <= MAX_RUNS:
        raise ValueError("bounded_pregame_runs_required")
    games, counts = defaultdict(list), Counter()
    for label, rows in captures.items():
        if not isinstance(label, str) or not label or not isinstance(rows, list):
            raise ValueError("invalid_rolling_capture")
        events = set()
        for record in rows:
            if not isinstance(record, dict) or record.get("league") not in SOURCES:
                raise ValueError("invalid_snapshot_in_rolling_ledger")
            key = (record["league"], record.get("espn_event_id"))
            if key in events:
                raise ValueError("duplicate_event_in_one_capture")
            events.add(key)
            games[key].append((label, record))
            counts[label] += 1
    rows, statuses = [], Counter()
    per_sport = {s: Counter() for s in SOURCES}
    for (league, event), observations in sorted(games.items()):
        ordered = sorted(observations, key=lambda pair: (
            pair[1]["archive_completed_utc"], pair[0]))
        team_signatures = {(v["home_team"], v["away_team"]) for _, v in ordered}
        starts = {v["event_start_utc"] for _, v in ordered}
        if len(team_signatures) != 1:
            status = "team_or_orientation_conflict_research_quarantined"
        elif len(starts) != 1:
            status = "kickoff_revision_observed_research_quarantined"
        else:
            status = "unchanged_unique_pregame_identity_research_only"
        statuses[status] += 1
        per_sport[league]["distinct_espn_future_event_ids"] += 1
        per_sport[league]["observed_times_across_captures"] += len(ordered)
        if status != "unchanged_unique_pregame_identity_research_only":
            per_sport[league]["events_with_conflicts_or_revisions"] += 1
        rows.append({
            "league": league, "espn_event_id": event,
            "first_observed_utc": ordered[0][1]["schedule_observed_at_utc"],
            "latest_observed_utc": ordered[-1][1]["schedule_observed_at_utc"],
            "capture_count": len(ordered), "research_status": status,
            "source_sha256_by_capture": [
                {"capture": label, "sha256": r["original_espn_sha256"]}
                for label, r in ordered],
            "publisher_original_publication_authenticated": False,
            "independent_historical_pregame_features_verified": False,
            "official_market_settlement_verified": False,
            "native_model_forecast_generated": False,
            "qualified_for_challenger_training": False,
            "certified_prediction": False, "champion_001_modified": False,
        })
    return rows, {
        "stage": "challenger_84_rolling_original_pregame_research_ledger",
        "capture_runs_checked": len(captures),
        "observations_checked": sum(counts.values()),
        "distinct_future_espn_game_ids": len(rows),
        "duplicates_counted_as_independent_training_games": 0,
        "by_league": {s: dict(sorted(c.items())) for s, c in per_sport.items()},
        "source_revision_status": dict(sorted(statuses.items())),
        "independent_original_feature_publication_authenticated": False,
        "verified_historical_settlement_labels": 0,
        "qualified_training_games": 0,
        "independent_native_model_probabilities": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "durable_external_archive_verified": False,
        "champion_001_modified": False,
        "warning": "SHA matched to the original captured ESPN schedule bytes; no publisher-signed as-of, independent historical feature proof, outcome label or durable archival custody.",
    }


def run(current, previous_dir, output_dir):
    captures = {"current": inspect_capture(current)}
    failures = {}
    if previous_dir:
        base = Path(previous_dir)
        if base.exists():
            candidates = sorted(p for p in base.iterdir() if p.is_dir() and not p.is_symlink())[-(MAX_RUNS-1):]
            for p in candidates:
                try:
                    captures["previous_"+p.name] = inspect_capture(p)
                except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                    failures[p.name] = type(exc).__name__
    rows, report = aggregate(captures)
    report["previous_capture_artifact_failures"] = failures
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rolling_pregame_unique_games.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True)+"\n" for r in rows), encoding="utf8")
    (out / "rolling_pregame_ledger_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current", required=True)
    p.add_argument("--previous-dir")
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.current, args.previous_dir, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
