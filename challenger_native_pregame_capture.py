"""Prospective native Challenger-001 NBA probability receipt capture; research only.

Generates receipts ONLY from a previously fitted, immutable research model,
an independently sourced future-event feature candidate, and the same-run
archived ESPN schedule. This does NOT train, invent pregame features, verify
upstream provenance, certify probabilities, or place wagers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from challenger_nba_probability import VERSION, digest, score_future_event
from challenger_prospective_outcome_validation import instant, validate_snapshot

FORECAST_FILE = "native_challenger_forecasts.jsonl"


def _sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def _approved_model(model):
    if not isinstance(model, dict):
        return False
    unsigned = dict(model)
    signature = unsigned.pop("artifact_sha256", None)
    return (isinstance(signature, str) and digest(unsigned) == signature
            and model.get("version") == VERSION
            and model.get("lane") == "Challenger-001"
            and model.get("status") == "unverified_research_model_not_deployed"
            and model.get("champion_001_modified") is False
            and model.get("qualified_for_real_money_wagers") is False
            and isinstance(model.get("fit"), dict)
            and type(model["fit"].get("training_rows")) is int
            and model["fit"]["training_rows"] >= 200)


def _read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()
            if x.strip()] if Path(path).is_file() else []


def capture(snapshots, candidates, model, now=None, run_id=None):
    """Return (immutable research receipts, honest fail-closed diagnostic).

    Only the existing future-event NBA HOME moneyline scorer generates p.
    Same-run snapshot and candidate are cross-checked; flags are not verified
    by an external independent authority. Never uses sportsbook odds.
    """
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    clock = clock.astimezone(timezone.utc)
    excluded = Counter()
    schedule = {}
    for snap in snapshots:
        try:
            key, captured = validate_snapshot(snap, clock)
            if key[0] != "nba" or not clock < instant(snap["event_start_utc"]):
                excluded["not_current_nba_pregame_snapshot"] += 1
                continue
            if key in schedule:
                schedule[key] = None
                excluded["duplicate_pregame_event"] += 1
            else:
                schedule[key] = (snap, captured)
        except (ValueError, TypeError, KeyError, OverflowError):
            excluded["invalid_archived_pregame_snapshot"] += 1

    receipts = []
    seen = set()
    valid_model = _approved_model(model)
    if not valid_model:
        status = "blocked_missing_or_invalid_research_model"
    elif not candidates:
        status = "blocked_missing_fresh_native_feature_candidates"
    elif not schedule:
        status = "blocked_no_usable_nba_pregame_snapshots"
    else:
        status = "research_scored_uncertified"

    if valid_model and candidates and schedule:
        for candidate in candidates:
            try:
                if not isinstance(candidate, dict):
                    raise ValueError("candidate_not_object")
                eid = candidate.get("event_id")
                if not isinstance(eid, str) or not eid.isdigit():
                    raise ValueError("missing_espn_event_id")
                key = ("nba", eid)
                if key in seen:
                    raise ValueError("duplicate_candidate")
                seen.add(key)
                record = schedule.get(key)
                if record is None:
                    raise ValueError("no_unique_archived_event_identity")
                snap, captured = record
                if (candidate.get("home_team") != snap["home_team"] or
                        candidate.get("away_team") != snap["away_team"]):
                    raise ValueError("teams_mismatch")
                if (candidate.get("event_source_url") != snap["schedule_source_url"]
                        or instant(candidate["start_utc"]) != instant(snap["event_start_utc"])):
                    raise ValueError("start_or_schedule_source_mismatch")
                snapshot = instant(candidate["snapshot_utc"])
                features_asof = instant(candidate["features_asof_utc"])
                if (not captured <= snapshot <= clock < instant(snap["event_start_utc"])
                        or snapshot - captured > timedelta(hours=2)
                        or not snapshot - timedelta(days=2) <= features_asof <= snapshot):
                    raise ValueError("source_feature_or_capture_time_mismatch")
                if candidate.get("probability_source") in ("sportsbook_implied", "market_break_even"):
                    raise ValueError("market_probability_disallowed")
                prediction = score_future_event(model, candidate, now=clock)
                prediction.update({
                    "league": "nba",
                    "source_snapshot_sha256": _sha(snap),
                    "candidate_claim_sha256": _sha(candidate),
                    "archive_run_id_self_reported": str(run_id) if run_id else None,
                    "source_evidence_independently_authenticated": False,
                    "native_model_fit_independently_certified": False,
                    "eligible_for_isotonic_fit": False,
                    "wager_stake": 0,
                    "bet_ready": False,
                    "champion_001_modified": False,
                })
                receipts.append(prediction)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                name = str(exc).replace(" ", "_")[:80] or "invalid_candidate"
                excluded[name] += 1

    if valid_model and candidates and schedule and not receipts:
        status = "blocked_no_valid_fresh_native_model_forecasts"

    report = {
        "stage": "challenger_001_native_nba_pregame_forecast_capture",
        "generated_at_utc": clock.isoformat(),
        "status": status,
        "nba_pregame_archived_event_count": sum(v is not None for v in schedule.values()),
        "candidate_rows_supplied": len(candidates),
        "research_model_artifact_present_and_format_valid": valid_model,
        "actual_native_research_forecasts_written": len(receipts),
        "rejections": dict(sorted(excluded.items())),
        "source_independent_provenance_verified": False,
        "forecast_qualified_for_isotonic_recalibration": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "Only the original Challenger NBA moneyline model may emit research probabilities; "
            "no odds-implied conversion, invented feature values, reconstructed older forecasts, "
            "or auto-certification. Receipts and SHA checks are self-attested, not independent "
            "provenance, and require separate postgame outcome adjudication."
        ),
    }
    return receipts, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", default="prospective_pregame/prospective_event_evidence.jsonl")
    parser.add_argument("--model", default="challenger_results/nba_probability/research_model.json")
    parser.add_argument("--candidates", default="prospective_pregame/nba_home_research_candidates.jsonl")
    parser.add_argument("--output-dir", default="prospective_pregame")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    model_path = Path(args.model)
    model = json.loads(model_path.read_text(encoding="utf-8")) if model_path.is_file() else None
    snapshots = _read_jsonl(args.snapshots)
    candidates = _read_jsonl(args.candidates)
    forecasts, report = capture(snapshots, candidates, model, run_id=args.run_id)
    report["model_path_exists"] = model_path.is_file()
    report["candidate_path_exists"] = Path(args.candidates).is_file()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / FORECAST_FILE).write_text(
        "".join(json.dumps(x, sort_keys=True, allow_nan=False) + "\n" for x in forecasts),
        encoding="utf-8")
    (out / "native_forecast_capture_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "native_research_forecasts": len(forecasts),
        "certified_predictions": 0,
        "champion_001_modified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
