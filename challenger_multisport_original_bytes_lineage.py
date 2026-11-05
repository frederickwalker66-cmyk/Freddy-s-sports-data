"""Eight-sport original-byte lineage review ledger (NO automatic training).

Combines real prospective GitHub archives, same-run original-byte receipts,
and independently unverified published ESPN finals. It refuses missing or
tampered receipts, duplicate event conflicts, late capture and absent features.
Neither internal hashes nor observed score corroboration authenticates the
original source's historical publication time or a sportsbook settlement.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from challenger_multisport_evidence_bridge import (
    LEAGUES, BINARY_RESEARCH, _linked_final_ok, _validate_form)
from challenger_prospective_outcome_validation import instant, validate_snapshot
from challenger_prospective_receipts import verify_receipt

REVIEW_RECORD = "challenger_original_bytes_feature_lineage_review_only"
REQUIRED = ("independent_original_capture_authentication",
            "independent_feature_publication_asof_validation",
            "independent_result_adjudication",
            "bookmaker_market_settlement_verification")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def archive_rows(root, now):
    """Only archives whose original bytes match a same-run receipt can appear."""
    sources = defaultdict(list)
    counts = Counter()
    for file in sorted(Path(root).rglob("prospective_event_evidence.jsonl")):
        counts["original_archives_examined"] += 1
        receipt_file = file.with_name("point_in_time_receipt.json")
        if not file.parent.name.isdecimal() or not receipt_file.is_file():
            counts["archives_missing_receipt_or_numeric_run_id"] += 1
            continue
        raw = file.read_bytes()
        receipt_bytes = receipt_file.read_bytes()
        try:
            manifest = json.loads(receipt_bytes)
            verified = verify_receipt(raw, manifest, expected_run_id=file.parent.name, now=now)
            if not verified["original_bytes_match_self_issued_receipt"]:
                raise ValueError("not a valid self-issued source receipt")
        except (KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
            counts["archives_invalid_receipt_or_bytes"] += 1
            continue
        counts["archives_original_bytes_match_self_issued_receipt"] += 1
        all_lines = [line for line in raw.splitlines(keepends=True) if line.strip()]
        for line, claimed in zip(all_lines, manifest["records"]):
            counts["original_rows_seen"] += 1
            if claimed["status"] != "timed_capture_for_review_only":
                counts["rows_not_timed_pregame_at_capture"] += 1
                continue
            row = json.loads(line)
            try:
                key, captured = validate_snapshot(row, now)
            except (KeyError, TypeError, ValueError, OverflowError):
                counts["rows_invalid_reinspection"] += 1
                continue
            if key[0] not in LEAGUES:
                counts["rows_unsupported_league"] += 1
                continue
            sources[key].append({
                "snapshot": row,
                "captured": captured,
                "line_sha256": sha(line),
                "archive_file_sha256": sha(raw),
                "receipt_sha256": sha(receipt_bytes),
                "run_id_self_reported": file.parent.name,
                "archive_relative_name": file.name,
                "line_number": claimed["line"],
            })
    return sources, counts


def assemble(sources, linked, now, archive_counts=None):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if not isinstance(linked, list):
        raise ValueError("linked results must be a list")
    per = {l: Counter() for l in LEAGUES}
    by_key = defaultdict(list)
    for link in linked:
        if not isinstance(link, dict) or link.get("league") not in LEAGUES:
            continue
        by_key[(link["league"], str(link.get("espn_event_id")))].append(link)
    entries = []
    for key, versions in sorted(sources.items()):
        league, event_id = key
        per[league]["original_receipt_backed_events"] += 1
        at = min(x["captured"] for x in versions)
        first = [v for v in versions if v["captured"] == at]
        if len({v["line_sha256"] for v in first}) != 1:
            per[league]["quarantined_conflicting_earliest_capture"] += 1
            continue
        chosen = min(first, key=lambda x: (x["run_id_self_reported"], x["line_number"]))
        snap = chosen["snapshot"]
        blockers = []
        if len(by_key.get(key, [])) != 1:
            blockers.append("missing_or_ambiguous_published_final_link")
            final = None
        else:
            link = by_key[key][0]
            if _linked_final_ok(link, snap, at, now):
                final = link["published_outcome"]
            else:
                final = None
                blockers.append("published_final_not_consistent_or_unverified")
        fh, fa = snap.get("home_team_form"), snap.get("away_team_form")
        has_features = (
            snap.get("team_form_available_for_both_teams") is True
            and _validate_form(fh, at) and _validate_form(fa, at))
        if not has_features:
            blockers.append("pregame_team_form_missing_or_invalid")
        features = ({"pregame_home_prior_win_rate": float(fh["win_rate"]),
                     "pregame_away_prior_win_rate": float(fa["win_rate"]),
                     "pregame_home_prior_margin_avg": float(fh["margin_average"]),
                     "pregame_away_prior_margin_avg": float(fa["margin_average"])}
                    if has_features else None)
        if final and league in BINARY_RESEARCH and final["result"] == "draw":
            blockers.append("binary_full_game_market_cannot_use_draw")
        if league not in BINARY_RESEARCH:
            blockers.append("soccer_regulation_90_minute_result_unverified")
        blockers.extend(REQUIRED)
        data = {
            "record_type": REVIEW_RECORD,
            "league": league, "event_id": event_id,
            "home_team": snap["home_team"], "away_team": snap["away_team"],
            "event_start_utc": snap["event_start_utc"],
            "snapshot_completed_at_utc": at.isoformat(),
            "schedule_source_url": snap["schedule_source_url"],
            "source_event_line_sha256": chosen["line_sha256"],
            "source_archive_file_sha256": chosen["archive_file_sha256"],
            "same_run_receipt_sha256": chosen["receipt_sha256"],
            "github_run_id_self_reported": chosen["run_id_self_reported"],
            "original_archive_line_number": chosen["line_number"],
            "other_snapshot_versions_not_used": len(versions) - 1,
            "feature_source_urls": (
                list(dict.fromkeys(fh["source_urls"] + fa["source_urls"]))
                if has_features else []),
            "asof_features_for_manual_review_only": features,
            "published_final_only": (
                {"home_score": final["home"], "away_score": final["away"],
                 "published_result": final["result"],
                 "published_at_observation_utc": final["published_retrieved_at_utc"],
                 "source_url": final["source_url"]} if final else None),
            "missing_evidence": sorted(set(blockers)),
            "original_bytes_match_same_run_receipt": True,
            "same_run_receipt_independently_authenticated": False,
            "independent_feature_asof_review": False,
            "independent_outcome_review": False,
            "market_settlement_rules_verified": False,
            "qualified_for_challenger_training": False,
            "model_probability": None, "certified_prediction": False,
            "bet_ready": False, "champion_001_modified": False,
        }
        entries.append(data)
        per[league]["review_packets"] += 1
        if features is not None:
            per[league]["packets_with_asof_team_form"] += 1
        if final:
            per[league]["packets_with_espn_published_final"] += 1
        for item in sorted(set(blockers)):
            per[league]["missing_" + item] += 1
    summary = {
        "stage": "challenger_eight_sport_original_bytes_lineage_review_only",
        "generated_at_utc": now.isoformat(),
        "all_leagues": list(LEAGUES),
        "archive_gate": dict(sorted((archive_counts or {}).items())),
        "per_league": {k: dict(sorted(v.items())) for k, v in per.items()},
        "review_packets": len(entries),
        "independently_authenticated_original_captures": 0,
        "independently_qualified_training_examples": 0,
        "model_artifacts_emitted": 0,
        "player_prop_models_emitted": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("The same-run receipt proves only internal byte consistency. "
                    "Original web publication timing, independent adjudication and "
                    "market settlement are not certified. This review packet is "
                    "incompatible with the native trainer schema by design."),
    }
    return entries, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot-root", required=True)
    ap.add_argument("--linked-results", required=True)
    ap.add_argument("--output-dir", default="prospective_validation")
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    sources, coverage = archive_rows(args.snapshot_root, now)
    path = Path(args.linked_results)
    if not path.is_file():
        raise FileNotFoundError("linked published-result JSONL is required")
    linked = [json.loads(s) for s in path.read_text(encoding="utf8").splitlines() if s.strip()]
    rows, report = assemble(sources, linked, now, coverage)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output/"original_bytes_lineage_review.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True)+"\n" for r in rows), encoding="utf8")
    (output/"original_bytes_lineage_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf8")
    print(json.dumps({"review_packets": len(rows),
                      "qualified_training_examples": 0,
                      "archives_with_matching_self_issued_receipts":
                      coverage["archives_original_bytes_match_self_issued_receipt"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
