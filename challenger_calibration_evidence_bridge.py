"""Fail-closed link of archived prospective Challenger research and published finals.

This creates only an UNQUALIFIED review queue. ESPN-published finals are not
independent settlement adjudication, and a forecast's SHA/flags do not prove
native model provenance. Untrained research baselines are never Challenger
model probabilities. The output is NEVER accepted calibration input, and this
module never changes Champion-001, generates bets, or promotes source flags.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlparse

ALLOWED_MODEL = "challenger-001-nba-home-moneyline-v1"
ARCHIVED_FORECAST_NAME = "native_challenger_forecasts.jsonl"
LINKED_NAME = "linked_pregame_outcomes.jsonl"
BASELINE_SCORECARD_NAME = "research_shadow_scorecard.json"


def utc(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if x.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return x.astimezone(timezone.utc)


def valid_linked(row, now):
    if not isinstance(row, dict) or row.get("league") != "nba":
        raise ValueError("not NBA linked outcome")
    if (row.get("status") != "linked_to_espn_published_final_only"
            or row.get("independent_league_outcome_verified") is not False
            or row.get("qualified_for_challenger_backtest") is not False
            or row.get("model_prediction_at_capture") is not None
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("linkage not safely quarantined")
    event_id = str(row.get("espn_event_id", ""))
    final = row.get("published_outcome")
    if not event_id.isdigit() or not isinstance(final, dict):
        raise ValueError("missing event or published result")
    if final.get("result") not in ("home", "away"):
        raise ValueError("ambiguous or unsupported result")
    src = urlparse(final.get("source_url") or "")
    if src.scheme != "https" or src.hostname != "site.api.espn.com":
        raise ValueError("published result source not ESPN")
    captured = utc(row.get("snapshot_completed_at_utc"))
    start = utc(row.get("event_start_utc"))
    observed = utc(final.get("published_retrieved_at_utc"))
    if not captured < start < observed <= now:
        raise ValueError("linked result chronology invalid")
    if not all(isinstance(row.get(k), str) and row[k].strip()
               for k in ("home_team", "away_team")):
        raise ValueError("incomplete team identity")
    return event_id, start, observed


def valid_native(row, now):
    # Only the existing real Challenger NBA probability-engine output format;
    # never the fixed-form research baseline or sportsbook implied probability.
    if not isinstance(row, dict) or row.get("stage") != "challenger_001_prospective_research_only":
        raise ValueError("not genuine Challenger forecast format")
    if (row.get("market") != "nba_moneyline"
            or row.get("selection") != "home"
            or row.get("model_version") != ALLOWED_MODEL
            or row.get("market_implied_probability_used_as_model") is not False
            or row.get("certified_prediction") is not False
            or row.get("qualified_for_shadow_ledger") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("not eligible native research format")
    digest = row.get("model_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("missing model fingerprint")
    eid = row.get("event_id")
    if not isinstance(eid, str) or not eid.isdigit():
        raise ValueError("native event not crosswalked to ESPN event id")
    p = row.get("research_probability_home_win")
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("native research probability missing")
    snapshot = utc(row.get("snapshot_utc"))
    created = utc(row.get("scored_at_utc"))
    if snapshot > created or created > now:
        raise ValueError("native forecast timestamp invalid")
    return eid, snapshot, created, float(p)


def stage_review_queue(linked_rows, native_rows, baseline_scorecard=None, as_of=None):
    """Link only format-valid research receipts; output ZERO calibration-qualified rows."""
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("as_of requires timezone")
    now = now.astimezone(timezone.utc)
    rejected = Counter()
    linked = {}
    for row in linked_rows:
        try:
            eid, start, observed = valid_linked(row, now)
            if eid in linked:
                # Conflicting/duplicate archive records cannot be silently promoted.
                rejected["duplicate_linked_event"] += 1
                linked[eid] = None
            else:
                linked[eid] = (row, start, observed)
        except (ValueError, TypeError, KeyError, OverflowError):
            rejected["unverified_or_unusable_published_final"] += 1
    native = {}
    for row in native_rows:
        try:
            eid, snapshot, created, p = valid_native(row, now)
            if eid in native:
                rejected["duplicate_native_event"] += 1
                native[eid] = None
            else:
                native[eid] = (row, snapshot, created, p)
        except (ValueError, TypeError, KeyError, OverflowError):
            rejected["not_native_challenger_forecast_or_bad_receipt"] += 1
    staged = []
    for event_id, record in sorted(native.items()):
        if record is None:
            continue
        if event_id not in linked or linked[event_id] is None:
            rejected["no_unambiguous_linked_published_final"] += 1
            continue
        forecast, snapshot, created, p = record
        game, start, observed = linked[event_id]
        if not (snapshot <= created < start and
                utc(game["snapshot_completed_at_utc"]) < start < observed):
            rejected["pregame_forecast_or_result_timing_mismatch"] += 1
            continue
        final = game["published_outcome"]
        # Intentionally NOT a calibrator input: provenance/settlement is only
        # research-stage and the external independent review is absent.
        staged.append({
            "record_type": "unverified_challenger_calibration_review_candidate",
            "league": "nba", "market_type": "moneyline",
            "selection_key": "home", "model_version": ALLOWED_MODEL,
            "event_id": event_id,
            "native_forecast_value_claimed": p,
            "native_forecast_version_fingerprint_unverified": forecast["model_sha256"],
            "prediction_timestamp_utc": created.isoformat(),
            "model_snapshot_timestamp_utc": snapshot.isoformat(),
            "event_start_utc": start.isoformat(),
            "published_final_retrieved_at_utc": observed.isoformat(),
            "published_result_home_win_research_only": final["result"] == "home",
            "published_result_source_url": final["source_url"],
            "independent_pregame_receipt_verified": False,
            "historical_pregame_features_verified": False,
            "model_output_before_event_verified": False,
            "independent_outcome_verified": False,
            "chronological_holdout": False,
            "model_training_excludes_holdout": False,
            "eligible_for_calibration": False,
            "independent_provenance_review_required": True,
            "qualified_for_challenger_backtest": False,
            "bet_ready": False, "champion_001_modified": False,
        })
    baseline_count = 0
    if isinstance(baseline_scorecard, dict) and baseline_scorecard.get("stage") == "untrained_challenger_shadow_baseline_descriptive_scorecard":
        value = baseline_scorecard.get("unique_valid_forecasts", 0)
        if type(value) is int and value >= 0:
            baseline_count = value
    status = ("blocked_no_archived_linked_finals" if not linked_rows
              else "blocked_no_native_challenger_forecasts" if not native_rows
              else "blocked_no_valid_native_forecast_outcome_links" if not staged
              else "research_review_only_external_authentication_required")
    report = {
        "stage": "challenger_native_calibration_evidence_bridge_research_only",
        "as_of_utc": now.isoformat(),
        "status": status,
        "linked_rows_seen": len(linked_rows),
        "native_forecast_rows_seen": len(native_rows),
        "untrained_fixed_rule_forecasts_excluded": baseline_count,
        "unqualified_native_forecast_outcome_pairs_staged": len(staged),
        "independently_qualified_calibration_rows": 0,
        "eligible_for_isotonic_fit": False,
        "review_flags_automatically_promoted": False,
        "calibration_evidence_file_created": False,
        "source_independently_adjudicated": False,
        "rejected": dict(sorted(rejected.items())),
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_wagers_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "ESPN-published finals are not independent league settlement adjudication. "
            "An archived model hash or format is not independent proof of model provenance. "
            "Untrained heuristic forecasts are excluded. Review queue is NEVER a training "
            "or calibration dataset; separately authenticated native predictions and outcomes "
            "are required before any recalibration."
        ),
    }
    return staged, report


def read_rows(folder, filename):
    paths = sorted(Path(folder).rglob(filename))
    if not paths:
        return []
    if len(paths) != 1:
        raise ValueError("ambiguous duplicate archive files: " + filename)
    path = paths[0]
    if filename.endswith(".jsonl"):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive-root", default="calibration_sources")
    ap.add_argument("--output-dir", default="challenger_results/calibration_evidence")
    args = ap.parse_args(argv)
    linked = read_rows(args.archive_root, LINKED_NAME)
    native = read_rows(args.archive_root, ARCHIVED_FORECAST_NAME)
    baseline = read_rows(args.archive_root, BASELINE_SCORECARD_NAME)
    staged, report = stage_review_queue(linked, native, baseline)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "review_queue.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in staged),
        encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                                      encoding="utf-8")
    print(json.dumps({"stage": report["stage"], "status": report["status"],
                      "unqualified_review_pairs": len(staged),
                      "qualified_calibration_rows": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
