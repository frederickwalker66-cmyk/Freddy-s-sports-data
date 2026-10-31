"""Reproducible Challenger-001 NBA moneyline research probability engine.

This does not train from odds, infer historical as-of proof from a URL, modify
Champion-001, certify shadow bets, provide player props, or place wagers.
Historical review flags and hashes are attestations, NOT independent proof.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from challenger_backtest import sigmoid, source_url, timestamp, validate_record

VERSION = "challenger-001-nba-home-moneyline-v1"
MIN_TRAIN = 200
MIN_TEST = 50
BLOCKED = "blocked_no_qualified_nba_training_data"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def qualified_history(row):
    """A recorded review is required, but cannot authenticate itself."""
    validate_record(row)
    if row["league"] != "nba" or row["selection_type"] != "home":
        raise ValueError("NBA HOME moneyline perspective only")
    if (row.get("qualified_for_challenger_backtest") is not True
            or row.get("independent_asof_review") is not True
            or row.get("independent_outcome_review") is not True
            or not valid_digest(row.get("feature_snapshot_sha256"))
            or not valid_digest(row.get("outcome_snapshot_sha256"))):
        raise ValueError("qualified historical source-review evidence missing")
    return row


def fit(rows, names):
    """Ridge logistic fit; scaling and prior rate use training rows only."""
    if not rows or sorted(rows[0]["features"]) != names:
        raise ValueError("empty or inconsistent training features")
    n = len(rows)
    means = [sum(row["features"][name] for row in rows) / n for name in names]
    stds = [
        max((sum((row["features"][name] - mean) ** 2
                 for row in rows) / n) ** 0.5, 1e-9)
        for name, mean in zip(names, means)
    ]
    xx = [[(row["features"][name] - mean) / std
           for name, mean, std in zip(names, means, stds)]
          for row in rows]
    yy = [row["outcome"] for row in rows]
    rate = min(0.999, max(0.001, sum(yy) / n))
    weights = [math.log(rate / (1 - rate))] + [0.0] * len(names)
    for _ in range(500):
        grads = [0.0] * len(weights)
        for features, label in zip(xx, yy):
            prediction = sigmoid(weights[0] + sum(
                v * w for v, w in zip(features, weights[1:])))
            err = prediction - label
            grads[0] += err
            for index, feature in enumerate(features, 1):
                grads[index] += err * feature
        weights[0] -= 0.09 * grads[0] / n
        for index in range(1, len(weights)):
            weights[index] -= 0.09 * (grads[index] / n + 0.1 * weights[index])
    return {
        "features": names,
        "means": means,
        "standard_deviations": stds,
        "coefficients": weights,
        "training_home_win_rate": rate,
        "training_rows": n,
    }


def predict_probability(model, features):
    if not isinstance(features, dict) or sorted(features) != model["features"]:
        raise ValueError("forecast feature schema must match training exactly")
    vector = []
    for name, mean, std in zip(
            model["features"], model["means"], model["standard_deviations"]):
        val = features[name]
        if (type(val) not in (int, float) or not math.isfinite(val)
                or abs(val) > 1e6):
            raise ValueError("invalid feature value")
        vector.append((val - mean) / std)
    score = model["coefficients"][0] + sum(
        a * b for a, b in zip(model["coefficients"][1:], vector))
    return max(1e-6, min(1 - 1e-6, sigmoid(score)))


def holdout_metrics(model, test):
    probs = [predict_probability(model, row["features"]) for row in test]
    labels = [row["outcome"] for row in test]
    prior = model["training_home_win_rate"]
    brier = sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(test)
    base_brier = sum((prior - y) ** 2 for y in labels) / len(test)
    logloss = -sum(
        y * math.log(p) + (1 - y) * math.log(1 - p)
        for p, y in zip(probs, labels)) / len(test)
    base_logloss = -sum(
        y * math.log(prior) + (1 - y) * math.log(1 - prior)
        for y in labels) / len(test)
    # Grouped calibration has limited power on small holdouts.
    bins = []
    for low, high in ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6),
                      (0.6, 0.8), (0.8, 1.000001)):
        indices = [i for i, p in enumerate(probs) if low <= p < high]
        if indices:
            bins.append({
                "range": [low, min(high, 1.0)], "count": len(indices),
                "mean_predicted": round(sum(probs[i] for i in indices) /
                                        len(indices), 6),
                "actual_rate": round(sum(labels[i] for i in indices) /
                                     len(indices), 6),
            })
    return {
        "holdout_games": len(test),
        "brier": round(brier, 6),
        "training_rate_baseline_brier": round(base_brier, 6),
        "log_loss": round(logloss, 6),
        "training_rate_baseline_log_loss": round(base_logloss, 6),
        "accuracy_at_0_5": round(sum((p >= 0.5) == bool(y)
                                   for p, y in zip(probs, labels)) /
                                   len(test), 6),
        "beats_prior_brier": brier < base_brier,
        "beats_prior_log_loss": logloss < base_logloss,
        "calibration_bins_exploratory": bins,
    }


def train_engine(rows, as_of=None, min_train=MIN_TRAIN, min_test=MIN_TEST):
    """Train research model only on review-attested, point-in-time rows.

    The holdout model is fitted without knowledge of test-period outcomes;
    only after evaluation is a separate final research artifact refitted.
    """
    if type(min_train) is not int or type(min_test) is not int or min_train < 2 or min_test < 2:
        raise ValueError("invalid sample thresholds")
    now = as_of or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("as_of must be a timezone-aware datetime")
    now = now.astimezone(timezone.utc)
    accepted, withheld, not_qualified = [], 0, 0
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("historical row must be object")
        if row.get("qualified_for_challenger_backtest") is not True:
            not_qualified += 1
            continue
        qualified_history(row)
        key = row["event_id"]
        if key in seen:
            raise ValueError("duplicate NBA game in training evidence")
        seen.add(key)
        if (timestamp(row["start_utc"]) >= now or
                timestamp(row["snapshot_utc"]) > now or
                timestamp(row["outcome_verified_at_utc"]) > now):
            withheld += 1
            continue
        accepted.append(row)
    accepted.sort(key=lambda row: (timestamp(row["start_utc"]), row["event_id"]))
    report = {
        "stage": "challenger_001_nba_moneyline_probability_research",
        "as_of_utc": iso(now),
        "rows_received": len(rows),
        "rows_review_attested_and_settled": len(accepted),
        "unqualified_rows_excluded": not_qualified,
        "future_or_unsettled_rows_excluded": withheld,
        "minimum_training_games": min_train,
        "minimum_holdout_games": min_test,
        "result": BLOCKED,
        "source_review_flags_do_not_prove_independent_verification": True,
        "independently_certified_training_records": 0,
        "calibration_independently_certified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
    }
    if len(accepted) < min_train + min_test:
        report["blocker"] = "not_enough_point_in_time_review_attested_settled_nba_games"
        return report, None
    names = sorted(accepted[0]["features"])
    if any(sorted(row["features"]) != names for row in accepted):
        report["blocker"] = "inconsistent_feature_schema"
        return report, None
    split_index = int(len(accepted) * 0.8)
    split_day = timestamp(accepted[split_index]["start_utc"]).date()
    prior = [r for r in accepted if timestamp(r["start_utc"]).date() < split_day]
    test = [r for r in accepted if timestamp(r["start_utc"]).date() >= split_day]
    earliest_snapshot = min(timestamp(r["snapshot_utc"]) for r in test)
    eligible_train = [r for r in prior
                      if timestamp(r["outcome_verified_at_utc"]) <= earliest_snapshot]
    report["chronological_train_games"] = len(eligible_train)
    report["chronological_holdout_games"] = len(test)
    report["excluded_prior_unsettled_at_holdout_cutoff"] = len(prior)-len(eligible_train)
    report["holdout_first_snapshot_utc"] = iso(earliest_snapshot)
    if (len(eligible_train) < min_train or len(test) < min_test
            or len({r["outcome"] for r in eligible_train}) < 2
            or len({r["outcome"] for r in test}) < 2):
        report["blocker"] = "insufficient_disjoint_chronological_train_or_test_evidence"
        return report, None
    held_model = fit(eligible_train, names)
    report["out_of_sample_exploratory_metrics"] = holdout_metrics(held_model, test)
    # The artifact fitted on *all already settled evidence* is a new model.
    # Holdout metrics above refer only to the pre-refit model, not this artifact.
    final = fit(accepted, names)
    model = {
        "version": VERSION,
        "lane": "Challenger-001",
        "market_type": "nba_home_moneyline",
        "status": "unverified_research_model_not_deployed",
        "trained_at_utc": iso(now),
        "historical_source_evidence_digest": digest(accepted),
        "last_training_event_start_utc": accepted[-1]["start_utc"],
        "holdout_metrics_apply_to_pre_refit_model_only": True,
        "fit": final,
        "qualified_for_real_money_wagers": False,
        "champion_001_modified": False,
    }
    model["artifact_sha256"] = digest(model)
    report["result"] = "fitted_unverified_research_model"
    report["fit_artifact_sha256"] = model["artifact_sha256"]
    report["retrained_artifact_has_independent_forward_performance"] = False
    report["warning"] = (
        "Dataset review flags and hashes alone do not validate real source "
        "history. Holdout results were measured on a separate earlier fit. "
        "No independent certification, player prop probabilities or EV."
    )
    return report, model


def score_future_event(model, candidate, now=None):
    """Score only a genuinely future event with a reproducible research model."""
    observed = now or datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ValueError("score time must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    if not isinstance(model, dict) or not isinstance(candidate, dict):
        raise ValueError("model and candidate must be objects")
    check = dict(model)
    stored_digest = check.pop("artifact_sha256", None)
    if (not valid_digest(stored_digest) or digest(check) != stored_digest
            or model.get("version") != VERSION or model.get("lane") != "Challenger-001"
            or model.get("status") != "unverified_research_model_not_deployed"
            or model.get("champion_001_modified") is not False):
        raise ValueError("model artifact signature or safety metadata invalid")
    if (candidate.get("league") != "nba" or candidate.get("market_type") != "moneyline"
            or candidate.get("selection_type") != "home"
            or not isinstance(candidate.get("event_id"), str)
            or not candidate["event_id"].strip()):
        raise ValueError("future NBA home moneyline identity required")
    snapshot = timestamp(candidate.get("snapshot_utc"))
    start = timestamp(candidate.get("start_utc"))
    featured = timestamp(candidate.get("features_asof_utc"))
    status_time = timestamp(candidate.get("availability_checked_at_utc"))
    trained = timestamp(model["trained_at_utc"])
    if (not trained <= snapshot <= observed < start or featured > snapshot
            or not snapshot - timedelta(hours=2) <= status_time <= snapshot):
        raise ValueError("historical replay, unavailable status, or future-data leakage")
    if (candidate.get("availability_reviewed") is not True
            or any(not source_url(candidate.get(k)) for k in (
                "event_source_url", "feature_source_url", "availability_source_url"))):
        raise ValueError("source and injury/availability review attestations required")
    p = predict_probability(model["fit"], candidate.get("features"))
    return {
        "stage": "challenger_001_prospective_research_only",
        "event_id": candidate["event_id"],
        "selection": "home",
        "market": "nba_moneyline",
        "model_version": VERSION,
        "model_sha256": stored_digest,
        "scored_at_utc": iso(observed),
        "snapshot_utc": iso(snapshot),
        "research_probability_home_win": round(p, 6),
        "market_implied_probability_used_as_model": False,
        "injury_review_attestation_is_not_independent_live_verification": True,
        "certified_prediction": False,
        "qualified_for_shadow_ledger": False,
        "bet_ready": False,
        "wager_stake": 0,
        "champion_001_modified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="historical_results.jsonl")
    parser.add_argument("--output-dir", default="challenger_results/nba_probability")
    parser.add_argument("--candidate", help="single future NBA event JSON; research only")
    args = parser.parse_args(argv)
    history_path = Path(args.history)
    rows = ([json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()
             if line.strip()] if history_path.is_file() else [])
    report, model = train_engine(rows)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    if model is not None:
        (dest / "research_model.json").write_text(
            json.dumps(model, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if args.candidate:
        if model is None:
            report["forecast_status"] = "blocked_no_qualified_model"
        else:
            candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
            projection = score_future_event(model, candidate)
            (dest / "research_forecast.json").write_text(
                json.dumps(projection, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            report["forecast_status"] = "uncertified_research_projection_only"
    (dest / "report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
