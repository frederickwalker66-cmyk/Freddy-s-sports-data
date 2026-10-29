"""Challenger-001: isolated historical moneyline backtest. NEVER alters Champion-001.

A green CI run means code passed, not that genuine outcomes exist or bets are ready.
Only verified-before-the-test-date results may be used for training. Every result
and pregame feature still needs independent source review outside this script.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

# First research stage: binary moneylines only. Soccer 3-way moneylines,
# spreads, totals and props require separate rules/outcome schemas.
LEAGUES = {"nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "wnba"}
BLOCKED = "blocked_no_qualified_historical_data"


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("required timestamp missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps require timezone offsets")
    return parsed.astimezone(timezone.utc)


def source_url(value):
    u = urlparse(value) if isinstance(value, str) else None
    return bool(u and u.scheme == "https" and u.netloc and u.hostname)


def validate_record(row):
    if not isinstance(row, dict):
        raise ValueError("historical example must be an object")
    required = ("event_id", "league", "selection_type", "market_type",
                "snapshot_utc", "features_asof_utc", "start_utc",
                "outcome_verified_at_utc", "event_source_url",
                "outcome_source_url", "feature_source_url")
    if any(not row.get(key) for key in required):
        raise ValueError("missing required historical evidence fields")
    if row["league"] not in LEAGUES or row["market_type"] != "moneyline":
        raise ValueError("only supported binary moneyline leagues may be backtested")
    if row["selection_type"] not in ("home", "away"):
        raise ValueError("moneyline side must be home or away")
    snap, asof, start, settled = (timestamp(row[key]) for key in (
        "snapshot_utc", "features_asof_utc", "start_utc", "outcome_verified_at_utc"))
    if asof > snap or snap >= start or settled <= start:
        raise ValueError("pregame timing or adjudication timing invalid")
    if any(not source_url(row[k]) for k in (
            "event_source_url", "outcome_source_url", "feature_source_url")):
        raise ValueError("missing HTTPS provenance link")
    if type(row.get("outcome")) is not int or row["outcome"] not in (0, 1):
        raise ValueError("outcome must be a settled binary label, 0 or 1")
    features = row.get("features")
    if not isinstance(features, dict) or not 1 <= len(features) <= 12:
        raise ValueError("one to twelve pregame features are required")
    for key, val in features.items():
        if (not isinstance(key, str) or not key.startswith("pregame_")
                or any(w in key.lower() for w in (
                    "odds", "price", "implied", "result", "outcome", "final", "score"))
                or type(val) not in (float, int) or not math.isfinite(val)
                or abs(val) > 1000000):
            raise ValueError("invalid, postgame, or sportsbook-derived feature")
    return row


def sigmoid(x):
    if x >= 0:
        z = math.exp(-min(x, 700))
        return 1 / (1 + z)
    z = math.exp(max(x, -700))
    return z / (1 + z)


def fit_and_score(train, test, names):
    """Deterministic ridge logistic baseline; scale computed on training only."""
    n = len(train)
    mu = [sum(r["features"][k] for r in train) / n for k in names]
    sd = [max((sum((r["features"][k] - m) ** 2 for r in train) / n) ** .5, 1e-9)
          for k, m in zip(names, mu)]
    def xvec(row):
        return [(row["features"][k] - m) / s for k, m, s in zip(names, mu, sd)]
    xs = [xvec(r) for r in train]
    ys = [r["outcome"] for r in train]
    mean = max(.001, min(.999, sum(ys) / n))
    weights = [math.log(mean / (1 - mean))] + [0.0] * len(names)
    for _ in range(600):
        grad = [0.0] * len(weights)
        for x, y in zip(xs, ys):
            err = sigmoid(weights[0] + sum(w * v for w, v in zip(weights[1:], x))) - y
            grad[0] += err
            for j, v in enumerate(x, 1):
                grad[j] += err * v
        weights[0] -= .08 * grad[0] / n
        for j in range(1, len(weights)):
            weights[j] -= .08 * (grad[j] / n + .1 * weights[j])
    p = [sigmoid(weights[0] + sum(w * v for w, v in zip(weights[1:], xvec(r))))
         for r in test]
    ys_test = [r["outcome"] for r in test]
    brier = sum((a - y) ** 2 for a, y in zip(p, ys_test)) / len(test)
    baseline_brier = sum((mean - y) ** 2 for y in ys_test) / len(test)
    logloss = -sum(y * math.log(max(1e-12, a)) +
                   (1-y) * math.log(max(1e-12, 1-a))
                   for a, y in zip(p, ys_test)) / len(test)
    accuracy = sum((a >= .5) == bool(y) for a, y in zip(p, ys_test)) / len(test)
    return {"test_brier": round(brier, 6),
            "training_rate_baseline_brier": round(baseline_brier, 6),
            "test_log_loss": round(logloss, 6),
            "test_accuracy": round(accuracy, 6),
            "beats_training_rate_brier_baseline": brier < baseline_brier,
            "features": names}


def backtest(rows, min_train=200, min_test=50):
    if min_train < 2 or min_test < 2:
        raise ValueError("minimum sample sizes must each be >= 2")
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        validate_record(row)
        # One candidate side per event prevents same-game train/test leakage.
        identity = (row["league"], row["event_id"])
        if identity in seen:
            raise ValueError("duplicate event: cannot separate same game across splits")
        seen.add(identity)
        groups[row["league"]].append(row)
    leagues = {}
    for league, group in sorted(groups.items()):
        group.sort(key=lambda r: (timestamp(r["start_utc"]), r["event_id"]))
        names = sorted(group[0]["features"])
        if any(sorted(r["features"]) != names for r in group):
            leagues[league] = {"status": "blocked_inconsistent_feature_schema", "rows": len(group)}
            continue
        cut = int(len(group) * .8)
        test = group[cut:]
        # Leakage-safe: a result cannot train a prediction made before it was known.
        first_test_snapshot = min((timestamp(r["snapshot_utc"]) for r in test), default=None)
        train = [r for r in group[:cut]
                 if timestamp(r["outcome_verified_at_utc"]) <= first_test_snapshot] if first_test_snapshot else []
        entry = {"rows": len(group), "eligible_train": len(train), "holdout": len(test),
                 "excluded_train_outcomes_not_known_at_cutoff": cut - len(train),
                 "holdout_is_chronologically_later": True}
        if (len(train) < min_train or len(test) < min_test
                or len(set(r["outcome"] for r in train)) < 2
                or len(set(r["outcome"] for r in test)) < 2):
            entry["status"] = "blocked_insufficient_chronological_settled_examples"
        else:
            entry["status"] = "uncertified_offline_backtest_only"
            entry["metrics"] = fit_and_score(train, test, names)
        leagues[league] = entry
    return {"mode": "challenger_001_separate_historical_research",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "historical_examples": len(rows), "minimum_training_examples_per_league": min_train,
            "minimum_holdout_examples_per_league": min_test,
            "leagues": leagues,
            "result": "offline_backtest_uncertified" if any(
                x["status"] == "uncertified_offline_backtest_only" for x in leagues.values()
            ) else BLOCKED,
            "historical_sources_independently_audited": False,
            "draftkings_checkout_prices_verified": 0,
            "certified_champion_001_predictions": 0,
            "certified_challenger_001_predictions": 0,
            "bet_ready_selections": 0, "automated_bets_placed": 0,
            "champion_001_modified": False,
            "warning": "Source links are metadata, NOT proof of independent verification. "
                       "Backtest metrics do not certify calibration, profit or betting readiness."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="historical_results.jsonl")
    p.add_argument("--output", default="challenger_results/backtest_report.json")
    args = p.parse_args(argv)
    path = Path(args.input)
    if path.exists():
        rows = [json.loads(s) for s in path.read_text(encoding="utf8").splitlines() if s.strip()]
    else:
        rows = []
    report = backtest(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
