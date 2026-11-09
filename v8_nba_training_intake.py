"""NBA training intake: real original-capture review packets vs separate audited data.

Collects research lineage *only as a manual-review queue*, NEVER converts it
into training rows or retroactively authenticates publication timestamps.
The existing native NBA trainer is invoked only for a DISTINCT explicitly
supplied review-attested training JSONL file, with 200 training/50 later
holdout games required. Even successfully fitted results are UNVERIFIED
research, not original Champion-001, certified forecasts or bet-ready EV.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from challenger_nba_probability import (
    train_engine, MIN_TRAIN, MIN_TEST, BLOCKED,
)
from challenger_prospective_outcome_validation import instant

RECORD = "challenger_original_bytes_feature_lineage_review_only"
FEATURE_NAMES = (
    "pregame_away_prior_margin_avg",
    "pregame_away_prior_win_rate",
    "pregame_home_prior_margin_avg",
    "pregame_home_prior_win_rate",
)
FILE = "original_bytes_lineage_review.jsonl"
MAX_FILES = 30
MAX_ROWS = 100_000
MAX_FILE_BYTES = 15_000_000


def load_review_packets(root):
    if not root:
        return [], []
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("original_review_directory_required")
    files = sorted(root.rglob(FILE))
    if len(files) > MAX_FILES:
        raise ValueError("too_many_original_review_files")
    packets = []
    for file in files:
        if file.is_symlink() or file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("unsafe_original_review_file")
        if len(packets) >= MAX_ROWS:
            raise ValueError("original_review_row_budget_exceeded")
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                if len(packets) >= MAX_ROWS:
                    raise ValueError("original_review_row_budget_exceeded")
                packets.append(json.loads(line))
    return packets, [str(file) for file in files]


def inspect_packet(row, as_of):
    if not isinstance(row, dict) or row.get("record_type") != RECORD:
        raise ValueError("only_original_bytes_lineage_review_packets_allowed")
    if row.get("league") != "nba":
        return None, "not_nba"
    if (row.get("champion_001_modified") is not False
            or row.get("original_bytes_match_same_run_receipt") is not True
            or row.get("same_run_receipt_independently_authenticated") is not False
            or row.get("qualified_for_challenger_training") is not False
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("model_probability") is not None):
        raise ValueError("upstream_review_packet_improperly_promoted_to_training_or_bet")
    event_id = row.get("event_id")
    if not isinstance(event_id, str) or not event_id.isdecimal():
        return None, "invalid_nba_event_id"
    if not isinstance(row.get("github_run_id_self_reported"), str) or not row["github_run_id_self_reported"].isdigit():
        return None, "missing_original_github_run_reference"
    captured = instant(row.get("snapshot_completed_at_utc"))
    start = instant(row.get("event_start_utc"))
    if not captured < start or captured > as_of:
        return None, "not_valid_original_pregame_capture"
    digest = row.get("source_event_line_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        return None, "missing_original_bytes_digest"
    feature = row.get("asof_features_for_manual_review_only")
    fields_present = isinstance(feature, dict) and set(feature) == set(FEATURE_NAMES)
    feature_ok = fields_present and all(
        type(v) in (int, float) and math.isfinite(v) and abs(v) <= 500
        for v in feature.values()
    )
    if feature_ok and any(
            not 0 <= feature[name] <= 1 for name in
            ("pregame_home_prior_win_rate", "pregame_away_prior_win_rate")):
        feature_ok = False
    final = row.get("published_final_only")
    final_ok = False
    if isinstance(final, dict):
        home, away = final.get("home_score"), final.get("away_score")
        if type(home) is int and type(away) is int and 0 <= home <= 999 and 0 <= away <= 999 and home != away:
            observed = instant(final.get("published_at_observation_utc"))
            label = "home" if home > away else "away"
            final_ok = (start < observed <= as_of and final.get("published_result") == label)
    missing = row.get("missing_evidence")
    if not isinstance(missing, list) or any(not isinstance(i, str) for i in missing):
        return None, "invalid_external_evidence_blocker_list"
    return {
        "event_id": event_id,
        "snapshot_completed_at_utc": captured.isoformat(),
        "start_utc": start.isoformat(),
        "source_event_line_sha256": digest,
        "original_run_id_self_reported": row["github_run_id_self_reported"],
        "pregame_four_feature_values_present_research_only": bool(feature_ok),
        "later_espn_published_final_present_research_only": bool(final_ok),
        "manual_review_of_source_and_settlement_required": sorted(set(missing)),
        "training_eligible": False,
    }, None


def audit(packets, now=None, *, qualified_history=None):
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if not isinstance(packets, list):
        raise ValueError("review_packets_must_be_list")
    accepted = {}
    quarantined_events = set()
    errors = Counter()
    for row in packets:
        try:
            item, why = inspect_packet(row, clock)
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            errors["invalid_or_unsafe_packet_" + str(exc)[:70]] += 1
            continue
        if why:
            if why != "not_nba":
                errors[why] += 1
            continue
        key = item["event_id"]
        if key in quarantined_events:
            errors["previously_conflicted_event_quarantined"] += 1
            continue
        if key in accepted:
            original = accepted[key]
            if (item["snapshot_completed_at_utc"] < original["snapshot_completed_at_utc"]):
                accepted[key] = item
                errors["newer_original_capture_superseded"] += 1
            elif (item["snapshot_completed_at_utc"] == original["snapshot_completed_at_utc"]
                  and item["source_event_line_sha256"] != original["source_event_line_sha256"]):
                accepted.pop(key)
                quarantined_events.add(key)
                errors["conflicting_earliest_capture_quarantined"] += 1
            else:
                errors["duplicate_or_newer_event_snapshot_ignored"] += 1
        else:
            accepted[key] = item
    rows = sorted(accepted.values(), key=lambda x: (x["start_utc"], x["event_id"]))
    ready_to_review = sum(
        r["pregame_four_feature_values_present_research_only"]
        and r["later_espn_published_final_present_research_only"] for r in rows
    )
    report = {
        "version": "v8-nba-original-intake-v1",
        "status": "HOLD_UNQUALIFIED_INDEPENDENT_EVIDENCE",
        "nba_original_review_packet_rows_received": len(packets),
        "nba_unique_original_capture_events": len(rows),
        "nba_manual_review_packets_with_pregame_features_and_published_finals": ready_to_review,
        "excluded_review_packet_reasons": dict(sorted(errors.items())),
        "minimum_qualified_training_games": MIN_TRAIN,
        "minimum_qualified_later_holdout_games": MIN_TEST,
        "independently_qualified_training_games": 0,
        "independently_qualified_holdout_games": 0,
        "additional_independently_qualified_train_games_needed": MIN_TRAIN,
        "additional_independently_qualified_holdout_games_needed": MIN_TEST,
        "external_review_required": [
            "Authenticate original historical publication time for all four pregame features.",
            "Reconcile source to original game identity and independently adjudicated official final.",
            "Approve exact NBA full-game moneyline settlement rules, including overtime.",
            "Provide an externally reviewed, separate, chronological NBA training-history JSONL.",
            "Fit and measure the native model on 200 training/50 disjoint later holdout games.",
            "Independently verify model source, calibration, and executable bookmaker price before releasing picks.",
        ],
        "review_packets_not_trainer_input": True,
        "original_champion_001_modified": False,
        "native_research_training_attempted": qualified_history is not None,
        "native_research_model_fitted": False,
        "native_research_training_report": None,
        "independently_certified_training_examples": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_v8_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "bet_ready": False,
        "warning": (
            "Receipt bytes and GitHub-reported capture timestamps are not "
            "independent publication proof. Review packets are never model "
            "training rows. A distinct review-attested file may produce a "
            "research-only model but is not external certification."
        ),
    }
    fitted = None
    if qualified_history is not None:
        if not isinstance(qualified_history, list):
            raise ValueError("distinct_reviewed_training_history_must_be_list")
        native_report, fitted = train_engine(qualified_history, as_of=clock)
        report["native_research_training_report"] = native_report
        report["native_research_model_fitted"] = fitted is not None
        report["status"] = ("FITTED_UNVERIFIED_RESEARCH_ONLY"
                            if fitted is not None else "HOLD_NATIVE_TRAINING_BLOCKED")
        report["review_attested_rows_not_independently_authenticated"] = native_report[
            "rows_review_attested_and_settled"]
    return rows, report, fitted


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-review-dir", help="Existing original lineage review GitHub artifacts")
    p.add_argument("--reviewed-history", help="Separate authentic manually reviewed NBA history JSONL, never the automatic queue")
    p.add_argument("--output-dir", default="v8_results/nba_training_intake")
    args = p.parse_args(argv)
    packets, paths = load_review_packets(args.original_review_dir)
    qualified = None
    if args.reviewed_history:
        source = Path(args.reviewed_history)
        if not source.is_file() or source.is_symlink() or source.name in (
                FILE, "all_sports_evidence_review_queue.jsonl",
                "historical_published_results.jsonl"):
            raise ValueError("unsafe_or_unreviewed_native_training_file")
        qualified = [json.loads(s) for s in source.read_text(encoding="utf-8").splitlines() if s.strip()]
    rows, report, model = audit(packets, qualified_history=qualified)
    report["original_github_archive_review_files"] = paths
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "NBA_RESEARCH_INTAKE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "nba_original_capture_external_review_worklist.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows), encoding="utf-8")
    if model is not None:
        destination = out / "NBA_UNVERIFIED_RESEARCH_MODEL.json"
        if destination.exists():
            raise FileExistsError("will_not_overwrite_existing_model")
        destination.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "nba_original_events": report["nba_unique_original_capture_events"],
        "nba_packets_ready_for_independent_review":
            report["nba_manual_review_packets_with_pregame_features_and_published_finals"],
        "native_research_model_fitted": report["native_research_model_fitted"],
        "certified_predictions": 0, "certified_positive_ev_bets": 0,
        "output_dir": str(out),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
