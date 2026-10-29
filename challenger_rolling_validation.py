"""Leakage-gated, expanding-window research validation for Challenger-001.

This is NOT the frozen Champion-001, a deployment, calibrated betting forecast,
or independently audited evidence. No training rows exist in this repository.
Each fold trains the existing deterministic logistic baseline on earlier,
already-known binary HOME-win examples only. Nothing is saved as a live model.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from challenger_backtest import fit_and_score, timestamp, validate_record

BLOCKED = "blocked_insufficient_rolling_origin_evidence"
EXPLORATORY = "uncertified_rolling_origin_research_only"


def _metrics_baseline(train, test):
    """Training-only home-win frequency; never use later outcomes as a prior."""
    rate = sum(r["outcome"] for r in train) / len(train)
    rate = max(1e-12, min(1 - 1e-12, rate))
    brier = sum((rate - r["outcome"]) ** 2 for r in test) / len(test)
    log_loss = -sum(r["outcome"] * math.log(rate) +
                    (1 - r["outcome"]) * math.log(1 - rate)
                    for r in test) / len(test)
    return round(brier, 6), round(log_loss, 6)


def _rolling_folds(group, names, minimum_train, minimum_test, maximum_folds):
    by_day = defaultdict(list)
    for row in group:
        by_day[timestamp(row["start_utc"]).date().isoformat()].append(row)
    dates = sorted(by_day)
    prior = []
    idx = 0
    folds = []
    while idx < len(dates) and len(folds) < maximum_folds:
        # Never put games on the same UTC event date on opposite sides of a split.
        if len(prior) < minimum_train:
            prior.extend(by_day[dates[idx]])
            idx += 1
            continue
        end = idx
        test = []
        while end < len(dates) and len(test) < minimum_test:
            test.extend(by_day[dates[end]])
            end += 1
        if len(test) < minimum_test:
            break
        first_snapshot = min(timestamp(r["snapshot_utc"]) for r in test)
        eligible = [
            r for r in prior
            if timestamp(r["outcome_verified_at_utc"]) <= first_snapshot
            and timestamp(r["start_utc"]) < first_snapshot
        ]
        # Wait until sufficient completed/known history exists. Do not pull
        # any result from the prospective test period into an earlier fold.
        if (len(eligible) < minimum_train or
                len({r["outcome"] for r in eligible}) < 2):
            prior.extend(by_day[dates[idx]])
            idx += 1
            continue
        stats = fit_and_score(eligible, test, names)
        baseline_brier, baseline_logloss = _metrics_baseline(eligible, test)
        folds.append({
            "fold": len(folds) + 1,
            "training_examples": len(eligible),
            "test_examples": len(test),
            "excluded_prior_results_not_known_at_cutoff": len(prior) - len(eligible),
            "first_test_event_date": dates[idx],
            "last_test_event_date": dates[end - 1],
            "first_test_snapshot_utc": first_snapshot.isoformat(),
            "test_dates_disjoint_from_other_folds": True,
            "metric_type": "uncertified_exploratory",
            "metrics": {**stats,
                        "training_rate_baseline_log_loss": baseline_logloss,
                        "training_rate_baseline_brier": baseline_brier,
                        "beats_training_rate_log_loss_baseline":
                            stats["test_log_loss"] < baseline_logloss},
        })
        # Future folds may train on earlier holdout results only once
        # their result-verification times precede the future fold's cutoff.
        for d in dates[idx:end]:
            prior.extend(by_day[d])
        idx = end
    return folds


def rolling_validate(rows, minimum_train=200, minimum_test=50,
                     minimum_folds=3, maximum_folds=4, as_of=None):
    if (not 2 <= minimum_train or not 2 <= minimum_test or
            not 1 <= minimum_folds <= maximum_folds <= 12):
        raise ValueError("invalid rolling sample and fold thresholds")
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("as_of must include timezone")
    now = now.astimezone(timezone.utc)
    groups = defaultdict(list)
    seen = set()
    withheld_future = 0
    for row in rows:
        validate_record(row)
        # A downstream parser must not promote explicitly quarantined rows.
        if row.get("qualified_for_challenger_backtest") is False:
            raise ValueError("quarantined research row is not a historical training example")
        identity = (row["league"], row["event_id"])
        if identity in seen:
            raise ValueError("duplicate game across data partitions")
        seen.add(identity)
        if (timestamp(row["start_utc"]) >= now or
                timestamp(row["outcome_verified_at_utc"]) > now or
                timestamp(row["snapshot_utc"]) > now):
            withheld_future += 1
            continue
        groups[row["league"]].append(row)
    leagues = {}
    for league, group in sorted(groups.items()):
        group.sort(key=lambda r: (timestamp(r["start_utc"]), r["event_id"]))
        names = sorted(group[0]["features"])
        reason = None
        if any(r["selection_type"] != "home" for r in group):
            # Existing generic row schema permits away labels, but generic
            # feature directions are not proved reversible. Reject them here.
            reason = "blocked_requires_home_perspective_labels"
        elif any(sorted(r["features"]) != names for r in group):
            reason = "blocked_inconsistent_pregame_feature_schema"
        if reason is not None:
            leagues[league] = {"status": reason, "rows": len(group), "folds": []}
            continue
        folds = _rolling_folds(group, names, minimum_train, minimum_test, maximum_folds)
        scored = sum(f["test_examples"] for f in folds)
        summary = {}
        if scored:
            for field in ("test_brier", "test_log_loss", "test_accuracy",
                          "training_rate_baseline_brier", "training_rate_baseline_log_loss"):
                summary[field] = round(sum(
                    f["metrics"][field] * f["test_examples"] for f in folds) / scored, 6)
            summary["beats_training_rate_brier_baseline"] = (
                summary["test_brier"] < summary["training_rate_baseline_brier"])
            summary["beats_training_rate_log_loss_baseline"] = (
                summary["test_log_loss"] < summary["training_rate_baseline_log_loss"])
        leagues[league] = {
            "status": EXPLORATORY if len(folds) >= minimum_folds else BLOCKED,
            "rows": len(group), "fold_count": len(folds),
            "disjoint_test_examples": scored,
            "features": names, "folds": folds, "summary_metrics": summary,
            "independently_verified": False,
            "eligible_for_model_promotion": False,
        }
    successful = sum(v.get("status") == EXPLORATORY for v in leagues.values())
    return {
        "stage": "challenger_001_expanding_origin_research",
        "result": EXPLORATORY if successful else BLOCKED,
        "generated_utc": now.isoformat(),
        "input_rows": len(rows),
        "withheld_future_or_not_yet_settled_rows": withheld_future,
        "minimum_train": minimum_train, "minimum_test": minimum_test,
        "minimum_folds": minimum_folds, "maximum_folds": maximum_folds,
        "leagues": leagues, "leagues_with_exploratory_folds": successful,
        "historical_sources_independently_audited": False,
        "out_of_sample_calibration_validated": False,
        "draftkings_checkout_prices_verified": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("An expanding-window fitted research baseline is NOT a trained "
                    "production model, live betting edge, independent evidence audit, "
                    "or B+ model performance grade. No sportsbook EV validation."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="historical_results.jsonl")
    p.add_argument("--output", default="challenger_results/rolling_validation_report.json")
    args = p.parse_args(argv)
    path = Path(args.input)
    rows = ([json.loads(s) for s in path.read_text(encoding="utf8").splitlines()
             if s.strip()] if path.is_file() else [])
    report = rolling_validate(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
