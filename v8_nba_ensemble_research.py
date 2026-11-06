"""V8 Elite NBA ensemble: point-in-time, chronological research evaluation only.

Input consists of externally reviewed pregame forecasts from distinct models.
This does not build missing forecasts, authenticate self-reported reviews, train
from outcomes after kickoff, certify model probabilities, or place bets.
All probabilities and results remain research-only pending external audit.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

COMPONENTS = ("elo", "logistic", "tree")
MIN_CALIBRATION = 50
MIN_HOLDOUT = 50


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_required")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def valid_probability(p):
    return type(p) in (float, int) and math.isfinite(p) and 0 < p < 1


def validate_row(row):
    if not isinstance(row, dict) or row.get("league") != "nba":
        raise ValueError("nba_only")
    if row.get("market") != "home_moneyline" or row.get("champion_001_modified") is not False:
        raise ValueError("invalid_market_or_champion_state")
    if row.get("season_type") != 2:
        raise ValueError("regular_season_only")
    if row.get("independent_pregame_review") is not True or row.get("independent_outcome_review") is not True:
        raise ValueError("independent_reviews_missing")
    event = row.get("event_id")
    if not isinstance(event, str) or not event.strip():
        raise ValueError("event_identity_missing")
    start, captured, settled = (parse_utc(row.get(x)) for x in
                                ("start_utc", "forecast_recorded_utc", "outcome_verified_utc"))
    if not captured < start < settled:
        raise ValueError("temporal_leakage")
    predictions = row.get("probabilities")
    if not isinstance(predictions, dict) or set(predictions) != set(COMPONENTS):
        raise ValueError("missing_component_forecast")
    if not all(valid_probability(predictions[c]) for c in COMPONENTS):
        raise ValueError("invalid_component_probability")
    if type(row.get("home_won")) is not bool:
        raise ValueError("binary_outcome_required")
    return start, captured


def brier(predictions, labels):
    return sum((p - y) ** 2 for p, y in zip(predictions, labels)) / len(labels)


def logloss(predictions, labels):
    return -sum(y * math.log(max(p, 1e-12)) + (1 - y) * math.log(max(1 - p, 1e-12))
                for p, y in zip(predictions, labels)) / len(labels)


def mix(row, weights):
    return sum(row["probabilities"][name] * weight for name, weight in zip(COMPONENTS, weights))


def candidate_weights():
    # Fixed 10% grid: no hyperparameter fishing on the untouched holdout.
    for a in range(11):
        for b in range(11 - a):
            yield (a / 10, b / 10, (10 - a - b) / 10)


def evaluate(rows, min_calibration=MIN_CALIBRATION, min_holdout=MIN_HOLDOUT):
    if type(min_calibration) is not int or min_calibration < 10 or type(min_holdout) is not int or min_holdout < 10:
        raise ValueError("unsafe_minimum_samples")
    report = {
        "version": "v8-nba-ensemble-research-v1",
        "champion_001_modified": False,
        "certified_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
        "status": "blocked_insufficient_independent_evidence",
        "rows_received": len(rows),
        "caution": "Self-reported review booleans are NOT independently authenticated.",
    }
    seen, prepared = set(), []
    for row in rows:
        start, capture = validate_row(row)
        if row["event_id"] in seen:
            raise ValueError("duplicate_event_id")
        seen.add(row["event_id"])
        prepared.append((start, capture, row))
    prepared.sort(key=lambda x: (x[0], x[2]["event_id"]))
    if len(prepared) < min_calibration + min_holdout:
        return report
    # Chronological split by whole UTC start date; never split games on same date.
    pivot = prepared[-min_holdout][0].date()
    cal = [x[2] for x in prepared if x[0].date() < pivot]
    test = [x[2] for x in prepared if x[0].date() >= pivot]
    # Every calibration outcome must have been verified before ANY test forecast.
    earliest_test_forecast = min(parse_utc(x["forecast_recorded_utc"]) for x in test)
    cal = [x for x in cal if parse_utc(x["outcome_verified_utc"]) < earliest_test_forecast]
    report.update(calibration_games=len(cal), holdout_games=len(test),
                  split_start_utc=pivot.isoformat())
    if len(cal) < min_calibration or len(test) < min_holdout:
        report["status"] = "blocked_chronology_or_sample_size"
        return report
    labels_cal = [int(x["home_won"]) for x in cal]
    weights = min(candidate_weights(),
                  key=lambda w: (logloss([mix(r, w) for r in cal], labels_cal), w))
    labels = [int(x["home_won"]) for x in test]
    probs = [mix(row, weights) for row in test]
    baseline = sum(labels_cal) / len(labels_cal)
    # Bound baseline before log to handle rare all-win/all-loss calibration windows.
    baseline = min(.999999, max(.000001, baseline))
    model_brier, base_brier = brier(probs, labels), brier([baseline] * len(test), labels)
    model_loss, base_loss = logloss(probs, labels), logloss([baseline] * len(test), labels)
    report.update(
        status="evaluated_research_only",
        ensemble_weights=dict(zip(COMPONENTS, weights)),
        holdout_brier=round(model_brier, 6),
        training_rate_baseline_brier=round(base_brier, 6),
        holdout_log_loss=round(model_loss, 6),
        training_rate_baseline_log_loss=round(base_loss, 6),
        improves_baseline_brier=model_brier < base_brier,
        improves_baseline_log_loss=model_loss < base_loss,
        externally_certified=False,
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-forecasts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    rows = [json.loads(line) for line in Path(args.reviewed_forecasts).read_text(encoding="utf-8").splitlines() if line.strip()]
    report = evaluate(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
