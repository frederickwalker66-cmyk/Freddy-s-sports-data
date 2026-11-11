"""Fit seven separate Challenger game-winner models from reviewed pregame evidence.

NBA uses its existing specialist trainer. Published-score backfills and automated
review queues are NOT eligible. This code never authenticates its own source
receipts, alters Champion-001, trains props or certifies a wager.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlparse

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from challenger_multisport_native_capture import (CAPTURE_LEAGUES, BINARY,
    MARKETS, SCOPE, SIDES, check_model, digest, predict_game)
from challenger_prospective_outcome_validation import instant

MIN_TRAIN, MIN_HOLDOUT = 200, 50
ROW_TYPE = "challenger_reviewed_pregame_game_evidence_v1"
REQUIRED_REVIEWS = ("independent_feature_asof_review", "independent_outcome_review",
                    "market_settlement_rules_verified")
DISALLOWED_FEATURE_TOKENS = ("odds", "closing", "final", "result", "postgame", "score", "outcome")


def valid_url(s):
    u = urlparse(s) if isinstance(s, str) else None
    return bool(u and u.scheme == "https" and u.hostname and "." in u.hostname)


def valid_hash(s):
    return isinstance(s, str) and re.fullmatch(r"[a-f0-9]{64}", s) is not None


def validate_row(row, now):
    """Manual review attestations are required, but not independent proof."""
    if not isinstance(row, dict) or row.get("record_type") != ROW_TYPE:
        raise ValueError("only_manual_review_evidence_is_accepted")
    league = row.get("league")
    if league not in CAPTURE_LEAGUES or row.get("market_type") != MARKETS[league] or row.get("settlement_scope") != SCOPE[league]:
        raise ValueError("league_or_market_mismatch")
    if not isinstance(row.get("event_id"), str) or not row["event_id"].isdigit():
        raise ValueError("invalid_espn_event_identity")
    if row.get("outcome") not in SIDES[league]:
        raise ValueError("market_outcome_cannot_be_settled")
    if (row.get("qualified_for_challenger_training") is not True
            or row.get("champion_001_modified") is not False
            or any(row.get(flag) is not True for flag in REQUIRED_REVIEWS)
            or any(not valid_hash(row.get(name)) for name in
                   ("feature_snapshot_sha256", "outcome_snapshot_sha256"))
            or any(not valid_url(row.get(name)) for name in
                   ("event_source_url", "feature_source_url", "outcome_source_url"))):
        raise ValueError("independent_review_receipts_or_sources_missing")
    start, snap = instant(row.get("start_utc")), instant(row.get("snapshot_utc"))
    feature_at, observed_outcome = instant(row.get("features_asof_utc")), instant(row.get("outcome_verified_at_utc"))
    if not (feature_at <= snap < start < observed_outcome <= now):
        raise ValueError("future_data_or_unsettled_outcome_leakage")
    features = row.get("features")
    if (not isinstance(features, dict) or not 1 <= len(features) <= 12
            or any(not isinstance(name, str) or not re.fullmatch(r"pregame_[a-z0-9_]+", name)
                   or any(token in name for token in DISALLOWED_FEATURE_TOKENS)
                   for name in features)
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6
                   for v in features.values())):
        raise ValueError("unsafe_or_nonpregame_feature_schema")
    return league


def make_fit(rows, names, league):
    """Fit sklearn logistic regression; return scorer-compatible immutable metadata."""
    X = np.array([[float(row["features"][n]) for n in names] for row in rows])
    y = np.array([row["outcome"] for row in rows])
    scaler = StandardScaler().fit(X)
    scaled = scaler.transform(X)
    clf = LogisticRegression(max_iter=1000, solver="lbfgs", C=1.0).fit(scaled, y)
    if set(clf.classes_) != set(SIDES[league]):
        raise ValueError("insufficient_outcome_class_coverage")
    model = {"feature_names": names, "feature_means": scaler.mean_.tolist(),
             "feature_stds": scaler.scale_.tolist()}
    if league in BINARY:
        if list(clf.classes_) != ["away", "home"]:
            raise ValueError("unexpected_binary_class_order")
        model["binary_logistic_coefficients"] = [float(clf.intercept_[0])] + clf.coef_[0].tolist()
    else:
        model["three_way_softmax_coefficients"] = {
            str(label): [float(clf.intercept_[i])] + clf.coef_[i].tolist()
            for i, label in enumerate(clf.classes_)}
    return model


def metrics(model, rows, league, training):
    classes = SIDES[league]
    label_frequencies = {s: sum(r["outcome"] == s for r in training) / len(training) for s in classes}
    total_brier = total_prior_brier = total_loss = total_prior_loss = 0.0
    for row in rows:
        probs = predict_game(model, league, row["features"])
        label = row["outcome"]
        total_brier += sum((probs[s] - (label == s)) ** 2 for s in classes) / 2
        total_prior_brier += sum((label_frequencies[s] - (label == s)) ** 2 for s in classes) / 2
        total_loss -= math.log(max(probs[label], 1e-12))
        total_prior_loss -= math.log(max(label_frequencies[label], 1e-12))
    count = len(rows)
    return {"games": count, "brier": round(total_brier / count, 6),
            "prior_brier": round(total_prior_brier / count, 6),
            "log_loss": round(total_loss / count, 6),
            "prior_log_loss": round(total_prior_loss / count, 6),
            "brier_improves_prior": total_brier < total_prior_brier,
            "log_loss_improves_prior": total_loss < total_prior_loss}


def train(rows, now=None, min_train=MIN_TRAIN, min_holdout=MIN_HOLDOUT):
    if type(min_train) is not int or type(min_holdout) is not int or min_train < 20 or min_holdout < 10:
        raise ValueError("unsafe_minimums")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("naive_clock")
    now = now.astimezone(timezone.utc)
    by_league, seen = defaultdict(list), set()
    for row in rows:
        league = validate_row(row, now)
        key = (league, row["event_id"])
        if key in seen:
            raise ValueError("duplicate_event_across_evidence")
        seen.add(key)
        by_league[league].append(row)
    artifacts, reports = {}, {}
    for league in sorted(CAPTURE_LEAGUES):
        games = sorted(by_league[league], key=lambda r: (instant(r["start_utc"]), r["event_id"]))
        report = {"games_review_attested": len(games), "status": "blocked_insufficient_evidence"}
        reports[league] = report
        if len(games) < min_train + min_holdout:
            continue
        boundary = instant(games[int(0.8 * len(games))]["start_utc"]).date()
        prior = [r for r in games if instant(r["start_utc"]).date() < boundary]
        holdout = [r for r in games if instant(r["start_utc"]).date() >= boundary]
        earliest_holdout_snapshot = min(instant(r["snapshot_utc"]) for r in holdout)
        training = [r for r in prior if instant(r["outcome_verified_at_utc"]) <= earliest_holdout_snapshot]
        report.update(chronological_train_games=len(training), later_holdout_games=len(holdout),
                      prior_games_not_settled_at_holdout=len(prior)-len(training))
        if (len(training) < min_train or len(holdout) < min_holdout
                or {r["outcome"] for r in training} != set(SIDES[league])
                or {r["outcome"] for r in holdout} != set(SIDES[league])):
            report["status"] = "blocked_split_or_class_coverage"
            continue
        names = sorted(training[0]["features"])
        if any(sorted(r["features"]) != names for r in games):
            report["status"] = "blocked_feature_schema_drift"
            continue
        preliminary = make_fit(training, names, league)
        score = metrics(preliminary, holdout, league, training)
        report["heldout_pre_refit_metrics"] = score
        if not score["brier_improves_prior"] or not score["log_loss_improves_prior"]:
            report["status"] = "blocked_no_out_of_sample_improvement"
            continue
        # Never refit on the untouched holdout: a post-holdout refit would
        # invalidate any claim that this artifact was independently held out.
        fitted = preliminary
        artifact = {"model_version": f"challenger-001-{league}-native-trained-v1",
                    "league": league, "market_type": MARKETS[league],
                    "settlement_scope": SCOPE[league], "lane": "Challenger-001",
                    "status": "unverified_research_model_not_deployed",
                    "qualified_for_real_money_wagers": False,
                    "calibration_independently_certified": False,
                    "champion_001_modified": False,
                    "chronological_training_rows": len(training),
                    "later_holdout_rows": len(holdout),
                    "historical_source_evidence_sha256": digest(training),
                    "trained_at_utc": now.isoformat(), **fitted}
        artifact["artifact_sha256"] = digest(artifact)
        check_model(artifact, league, now)
        artifacts[league] = artifact
        report["status"] = "fitted_research_only_not_certified"
        report["artifact_sha256"] = artifact["artifact_sha256"]
    summary = {"stage": "challenger_multisport_native_research_training",
               "review_attested_records_received": len(rows),
               "trained_research_models": sorted(artifacts), "by_league": reports,
               "independent_source_authentication_performed_by_this_script": False,
               "source_reviews_cannot_self_authenticate": True,
               "holdout_metrics_apply_to_pre_refit_fit_only": True,
               "player_prop_models_created": 0, "certified_champion_001_predictions": 0,
               "certified_challenger_001_predictions": 0, "certified_positive_ev_bets": 0,
               "bet_ready_selections": 0, "automated_bets_placed": 0,
               "champion_001_modified": False}
    return summary, artifacts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="challenger_reviewed_pregame_games.jsonl")
    parser.add_argument("--output-dir", default="challenger_results/native_model_training")
    parser.add_argument("--allow-missing-evidence", action="store_true")
    parser.add_argument("--original-evidence-root", default="external_original_source_bytes")
    parser.add_argument("--pregame-witness-public-key")
    parser.add_argument("--outcome-witness-public-key")
    args = parser.parse_args(argv)
    path = Path(args.evidence)
    if not path.exists() and not args.allow_missing_evidence:
        raise FileNotFoundError(path)
    rows = ([json.loads(x) for x in path.read_text(encoding="utf8").splitlines() if x.strip()]
            if path.is_file() else [])
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if rows:
        # Do not fit or export a model from self-attested rows. External
        # witness keys must be supplied separately from the repository, and
        # original source bytes must be present for independent verification.
        from challenger_authenticated_chronological_dataset import (
            build as authenticate, key_from_path, write_output)
        pre = (key_from_path(args.pregame_witness_public_key)
               if args.pregame_witness_public_key else None)
        outcome = (key_from_path(args.outcome_witness_public_key)
                   if args.outcome_witness_public_key else None)
        admission, admitted = authenticate(rows, args.original_evidence_root, pre, outcome)
        write_output(out / "witnessed_evidence", admission, admitted)
        rows = [game for league in sorted(admitted)
                for part in ("train", "holdout") for game in admitted[league][part]]
    report, models = train(rows)
    if path.is_file() and not rows:
        report["source_status"] = "BLOCKED_NO_EXTERNALLY_WITNESSED_200_50_DATASET"
    if path.is_file():
        for league, model in models.items():
            destination = out / (league + ".json")
            if destination.exists():
                raise FileExistsError("refusing_to_overwrite_existing_model_artifact")
            destination.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    report["evidence_file_present"] = path.is_file()
    (out / "research_training_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"models": report["trained_research_models"],
                      "certified_bets": 0, "report": str(out / "research_training_report.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
