"""Research-only, chronological isotonic recalibration for Freddy's Challenger-001.

Input: JSONL of genuine PRE-GAME, OUT-OF-SAMPLE Challenger probabilities,
with independently verified provenance and subsequently settled outcomes.
Sportsbook break-even probabilities are NOT model predictions.

The validation flags in input are assertions, not cryptographic proof. This
module never changes Champion-001, places a wager, or certifies an EV edge.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path
import re

from sklearn.isotonic import IsotonicRegression

MIN_CALIBRATION = 200
MIN_EVALUATION = 50
EPS = 1e-6
REQUIRED_EVIDENCE_FLAGS = (
    "independent_outcome_verified",
    "historical_pregame_features_verified",
    "model_output_before_event_verified",
    "chronological_holdout",
    "model_training_excludes_holdout",
    "independent_pregame_receipt_verified",
)


def _date(value):
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def _json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(obj):
    return hashlib.sha256(_json(obj).encode("utf-8")).hexdigest()


def _read_row(row, now):
    if not isinstance(row, dict):
        raise ValueError("not_an_object")
    if any(row.get(flag) is not True for flag in REQUIRED_EVIDENCE_FLAGS):
        raise ValueError("independent_evidence_flag_missing")
    if row.get("champion_001_modified") is not False:
        raise ValueError("champion_safety_flag_missing")
    if row.get("probability_source") != "native_challenger_model":
        raise ValueError("not_a_native_challenger_probability")
    version = row.get("model_version")
    if not isinstance(version, str) or not version.lower().startswith("challenger-"):
        raise ValueError("not_a_challenger_model_version")
    group = tuple(row.get(k) for k in ("league", "market_type", "selection_key", "model_version"))
    if not all(isinstance(x, str) and x.strip() and len(x) <= 160 for x in group):
        raise ValueError("market_group_incomplete")
    if not re.fullmatch(r"[a-z0-9_]+", group[0]) or not re.fullmatch(r"[a-z0-9_]+", group[1]):
        raise ValueError("invalid_league_or_market")
    event_id = row.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id_missing")
    p = row.get("model_probability")
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("invalid_model_probability")
    if row.get("settlement") not in ("WIN", "LOSS"):
        raise ValueError("requires_settled_win_or_loss")
    y = int(row["settlement"] == "WIN")
    if "outcome" in row and (type(row["outcome"]) is not int or row["outcome"] != y):
        raise ValueError("settlement_outcome_mismatch")
    captured = _date(row.get("prediction_timestamp_utc"))
    started = _date(row.get("event_start_utc"))
    verified = _date(row.get("outcome_verified_at_utc"))
    if not (captured < started < verified <= now):
        raise ValueError("not_valid_pregame_or_settled_timing")
    return {"group": group, "event_id": event_id, "p": float(p), "y": y,
            "captured": captured, "started": started, "verified": verified}


def _metrics(probs, outcomes):
    n = len(probs)
    brier = sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n
    logloss = -sum(y * math.log(min(1-EPS, max(EPS, p))) +
                   (1-y) * math.log(min(1-EPS, max(EPS, 1-p)))
                   for p, y in zip(probs, outcomes)) / n
    bins = []
    ece = 0.0
    for k in range(10):
        chosen = [(p, y) for p, y in zip(probs, outcomes)
                  if k/10 <= p < (k+1)/10 or (k == 9 and p == 1)]
        if chosen:
            pred = sum(v[0] for v in chosen) / len(chosen)
            actual = sum(v[1] for v in chosen) / len(chosen)
            ece += len(chosen) / n * abs(pred - actual)
            bins.append({"range": [k/10, (k+1)/10], "count": len(chosen),
                         "predicted": round(pred, 6), "observed": round(actual, 6)})
    return {"brier": round(brier, 6), "log_loss": round(logloss, 6),
            "ece_10_bins": round(ece, 6), "reliability_bins": bins}


def _artifact_name(group):
    return "_".join(re.sub(r"[^A-Za-z0-9_-]+", "_", x)[:48] for x in group) + "_" + _sha(group)[:10] + ".json"


def recalibrate(rows, as_of=None, min_calibration=MIN_CALIBRATION,
                min_evaluation=MIN_EVALUATION):
    """Return (honest diagnostic report, research-only artifact dictionaries).

    Isotonic fit uses earlier settled OOS predictions. Untouched later games
    evaluate whether calibration improves BOTH Brier score and log loss.
    Entire UTC event dates remain in one partition; every calibration result
    must have been known before the earliest evaluation pregame capture.
    """
    if (type(min_calibration) is not int or type(min_evaluation) is not int
            or min_calibration < 30 or min_evaluation < 30):
        raise ValueError("minimum samples must each be >= 30")
    now = as_of or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    now = now.astimezone(timezone.utc)
    groups = defaultdict(list)
    excluded = Counter()
    for row in rows:
        try:
            item = _read_row(row, now)
            groups[item["group"]].append(item)
        except (ValueError, TypeError) as exc:
            excluded[str(exc)] += 1
    artifacts = {}
    reports = []
    for group, items in sorted(groups.items()):
        items.sort(key=lambda x: (x["started"], x["event_id"]))
        report = {"league": group[0], "market_type": group[1],
                  "selection_key": group[2], "model_version": group[3],
                  "valid_rows": len(items), "status": "blocked_insufficient_evidence"}
        if len({i["event_id"] for i in items}) != len(items):
            report["status"] = "blocked_duplicate_event_or_forecast"
            reports.append(report)
            continue
        if len(items) < min_calibration + min_evaluation:
            reports.append(report)
            continue
        # Chronological 80/20 cutoff, expanded to include all games on the
        # first evaluation date; prevents same-day outcomes crossing the split.
        split_day = items[int(len(items) * .8)]["started"].date()
        initial = [i for i in items if i["started"].date() < split_day]
        holdout = [i for i in items if i["started"].date() >= split_day]
        first_capture = min(i["captured"] for i in holdout)
        fit_rows = [i for i in initial if i["verified"] <= first_capture]
        report.update({"calibration_rows": len(fit_rows),
                       "evaluation_rows": len(holdout),
                       "excluded_prior_outcomes_not_known_at_cutoff": len(initial)-len(fit_rows),
                       "evaluation_first_utc_day": split_day.isoformat()})
        if (len(fit_rows) < min_calibration or len(holdout) < min_evaluation
                or len({i["y"] for i in fit_rows}) < 2
                or len({i["y"] for i in holdout}) < 2
                or len({i["p"] for i in fit_rows}) < 8):
            report["status"] = "blocked_insufficient_chronological_split_or_classes"
            reports.append(report)
            continue
        calibrator = IsotonicRegression(y_min=EPS, y_max=1-EPS, out_of_bounds="clip")
        calibrator.fit([i["p"] for i in fit_rows], [i["y"] for i in fit_rows])
        truth = [i["y"] for i in holdout]
        raw = [i["p"] for i in holdout]
        calibrated = [float(p) for p in calibrator.predict(raw)]
        baseline, revised = _metrics(raw, truth), _metrics(calibrated, truth)
        improved = revised["brier"] < baseline["brier"] and revised["log_loss"] < baseline["log_loss"]
        report.update({"raw_holdout": baseline, "isotonic_holdout": revised,
                       "improves_brier_and_log_loss": improved,
                       "status": "research_artifact_saved_not_certified" if improved
                                 else "blocked_recalibration_degrades_a_primary_metric"})
        if improved:
            artifact = {
                "version": "challenger-isotonic-research-v1",
                "lane": "Challenger-001", "group": list(group),
                "status": "research_only_not_deployed",
                "calibration_evidence_rows": len(fit_rows),
                "held_out_evaluation_rows": len(holdout),
                "latest_calibration_settlement_utc": max(i["verified"] for i in fit_rows).isoformat(),
                "evaluated_on_later_disjoint_games": True,
                "knots_x": [float(x) for x in calibrator.X_thresholds_],
                "knots_y": [float(y) for y in calibrator.y_thresholds_],
                "independent_provenance_not_proved_by_flags": True,
                "certified_prediction": False,
                "bet_ready": False, "champion_001_modified": False,
            }
            artifact["sha256"] = _sha(artifact)
            artifacts[_artifact_name(group)] = artifact
            report["artifact_filename"] = _artifact_name(group)
        reports.append(report)
    summary = {
        "stage": "challenger_001_daily_isotonic_recalibration_research_only",
        "as_of_utc": now.isoformat(), "rows_received": len(rows),
        "excluded": dict(sorted(excluded.items())), "minimum_calibration_rows": min_calibration,
        "minimum_later_holdout_rows": min_evaluation,
        "groups": reports, "research_artifacts_written": len(artifacts),
        "independent_external_source_authentication_performed": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers_placed": 0, "champion_001_modified": False,
        "warning": ("Input provenance flags are self-declarations, not source authentication. "
                    "Research calibrators may only transform predictions from the same native "
                    "Challenger market/version; they cannot establish an EV edge or be deployed "
                    "without independent review and prospective validation."),
    }
    return summary, artifacts


def apply_research_calibrator(artifact, raw_probability, *, league, market_type, selection_key, model_version):
    """Apply a research artifact only to its exact league/market/version group."""
    if type(raw_probability) not in (float, int) or not math.isfinite(raw_probability) or not 0 < raw_probability < 1:
        raise ValueError("invalid raw probability")
    content = dict(artifact)
    stored = content.pop("sha256", None)
    if (_sha(content) != stored or content.get("lane") != "Challenger-001"
            or content.get("status") != "research_only_not_deployed"
            or content.get("champion_001_modified") is not False):
        raise ValueError("artifact integrity or lane invalid")
    if content.get("group") != [league, market_type, selection_key, model_version]:
        raise ValueError("calibration group mismatch")
    xs, ys = content["knots_x"], content["knots_y"]
    if not xs or len(xs) != len(ys) or any(x >= y for x, y in zip(xs, xs[1:])):
        raise ValueError("invalid isotonic knots")
    if raw_probability <= xs[0]:
        return ys[0]
    if raw_probability >= xs[-1]:
        return ys[-1]
    j = bisect_right(xs, raw_probability)
    return ys[j-1] + (raw_probability-xs[j-1]) * (ys[j]-ys[j-1]) / (xs[j]-xs[j-1])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", required=True, help="JSONL, pregame model probabilities with independently reviewed outcomes")
    p.add_argument("--output-dir", default="challenger_results/isotonic_recalibration")
    p.add_argument("--allow-missing-evidence", action="store_true",
                   help="Write a blocked report instead of failing when qualified forecast evidence is absent")
    args = p.parse_args(argv)
    source = Path(args.evidence)
    if not source.is_file() and not args.allow_missing_evidence:
        print(f"Evidence file not found: {source}. No calibration was fitted.")
        return 2
    rows = ([json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
             if line.strip()] if source.is_file() else [])
    report, artifacts = recalibrate(rows)
    report["status"] = (
        "blocked_missing_prediction_evidence_file" if not source.is_file()
        else "blocked_empty_prediction_evidence" if not rows
        else "uncertified_research_artifacts_created" if artifacts
        else "blocked_no_approved_research_calibrator"
    )
    report["evidence_path"] = str(source)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (out / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": report["stage"],
                      "valid_groups": len(report["groups"]),
                      "research_artifacts_written": len(artifacts),
                      "certified_positive_ev_bets": 0,
                      "report": str(out / "report.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())