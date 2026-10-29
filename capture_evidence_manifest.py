"""Timestamp and hash existing official-source research artifacts.

A manifest proves what the workflow stored, not when an external website first
published a fact or that any player was available before an event.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

MANIFEST = "source_evidence_manifest.json"
REPORT = "source_refresh_report.json"

def aware_utc(value):
    if not isinstance(value, str):
        raise ValueError("missing scan timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("scan timestamp lacks timezone")
    return stamp.astimezone(timezone.utc)

def build_manifest(folder, now=None):
    root = Path(folder)
    if not root.is_dir() or not (root / REPORT).is_file():
        raise ValueError("missing official-source report")
    report = json.loads((root / REPORT).read_text(encoding="utf8"))
    if not isinstance(report, dict):
        raise ValueError("invalid official-source report")
    captured = now or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise ValueError("capture time must have timezone")
    captured = captured.astimezone(timezone.utc)
    started = aware_utc(report.get("retrieved_at_utc"))
    if started > captured + timedelta(minutes=5):
        raise ValueError("source refresh timestamp is in the future")
    if (report.get("champion_001_modified") is not False
            or report.get("player_props_cleared") != 0
            or report.get("model_probabilities_generated") != 0):
        raise ValueError("source report unexpectedly promotes model or bets")
    sources = report.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("invalid source status inventory")
    files = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name == MANIFEST:
            continue
        raw = path.read_bytes()
        files.append({"name": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                      "size_bytes": len(raw)})
    if not files:
        raise ValueError("no evidence files to archive")
    return {
        "stage": "prospective_official_source_evidence_archive_research_only",
        "scan_started_at_utc": started.isoformat(),
        "manifest_created_at_utc": captured.isoformat(),
        "game_date_et": report.get("game_date_et"),
        "source_statuses": {key: value.get("status") if isinstance(value, dict) else None
                            for key, value in sources.items()},
        "file_hashes": files,
        "pregame_event_timestamp_alignment_verified": False,
        "historical_as_of_source_publication_verified": False,
        "verified_training_examples": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "champion_001_modified": False,
        "warning": ("Hashes authenticate archived file bytes, not independent source "
                    "truth, historical publication time, or player participation. "
                    "Some scans can occur after games start. Remain quarantined.")
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="official_sources")
    args = parser.parse_args()
    root = Path(args.outdir)
    manifest = build_manifest(root)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                 encoding="utf8")
    print(json.dumps({"archived_files": len(manifest["file_hashes"]),
                      "source_statuses": manifest["source_statuses"],
                      "verified_training_examples": 0, "bet_ready_selections": 0},
                     sort_keys=True))

if __name__ == "__main__":
    main()
