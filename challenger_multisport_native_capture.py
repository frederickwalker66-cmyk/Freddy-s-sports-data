"""Fail-closed native Challenger game probabilities across eight sports (research only).

The existing NBA model is scored by challenger_native_pregame_capture.py.
This extension supports NFL, MLB, NHL, NCAAF, NCAAB (binary), and
MLS/UEFA Champions League (90-minute home/draw/away). It NEVER fits a
model, substitutes a sportsbook price or fixed-rule research baseline,
or creates a player prop model. No eligible model artifacts are currently
supplied by the repository: missing models produce explicit blocked reports.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from challenger_prospective_outcome_validation import instant, validate_snapshot
from challenger_multisport_evidence_bridge import LEAGUES

BINARY = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab"))
THREE_WAY = frozenset(("mls", "uefa_champions_league"))
CAPTURE_LEAGUES = frozenset(LEAGUES) - {"nba"}  # NBA has the existing specialist engine.
MARKETS = {league: ("moneyline" if league in BINARY else "three_way_result") for league in LEAGUES}
SCOPE = {league: ("including_overtime" if league in BINARY
                  else "regulation_90_minutes_including_stoppage") for league in LEAGUES}
SIDES = {league: (("home", "away") if league in BINARY
                  else ("home", "draw", "away")) for league in LEAGUES}
FORECAST_FILE = "native_multisport_forecasts.jsonl"
MIN_TRAIN, MIN_HOLDOUT = 200, 50


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode("utf-8")).hexdigest()


def _url(value):
    u = urlparse(value) if isinstance(value, str) else None
    return bool(u and u.scheme == "https" and u.hostname)


def check_model(model, league, as_of=None):
    """Check cryptographic consistency + asserted training metadata, NOT provenance."""
    if not isinstance(model, dict) or league not in CAPTURE_LEAGUES:
        raise ValueError("model_missing_or_unsupported_sport")
    unsigned = dict(model)
    signature = unsigned.pop("artifact_sha256", None)
    version = model.get("model_version")
    if (not isinstance(signature, str) or len(signature) != 64
            or digest(unsigned) != signature
            or not isinstance(version, str)
            or not version.startswith(f"challenger-001-{league}-")
            or model.get("league") != league
            or model.get("market_type") != MARKETS[league]
            or model.get("settlement_scope") != SCOPE[league]
            or model.get("lane") != "Challenger-001"
            or model.get("status") != "unverified_research_model_not_deployed"
            or model.get("qualified_for_real_money_wagers") is not False
            or model.get("champion_001_modified") is not False
            or model.get("calibration_independently_certified") is not False):
        raise ValueError("model_fingerprint_version_or_lane_invalid")
    if (type(model.get("chronological_training_rows")) is not int
            or type(model.get("later_holdout_rows")) is not int
            or model["chronological_training_rows"] < MIN_TRAIN
            or model["later_holdout_rows"] < MIN_HOLDOUT):
        raise ValueError("model_training_holdout_requirements_not_met")
    evidence_hash = model.get("historical_source_evidence_sha256")
    if not isinstance(evidence_hash, str) or len(evidence_hash) != 64 or any(c not in "0123456789abcdef" for c in evidence_hash):
        raise ValueError("historical_research_evidence_digest_missing")
    trained = instant(model.get("trained_at_utc"))
    if as_of is not None and trained > as_of:
        raise ValueError("model_was_trained_in_the_future")
    names = model.get("feature_names")
    means, stds = model.get("feature_means"), model.get("feature_stds")
    if (not isinstance(names, list) or not 1 <= len(names) <= 12
            or any(not isinstance(n, str) or not n.startswith("pregame_") for n in names)
            or len(set(names)) != len(names) or names != sorted(names)
            or not isinstance(means, list) or not isinstance(stds, list)
            or len(means) != len(names) or len(stds) != len(names)
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6 for v in means)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 1e-9 <= v <= 1e6 for v in stds)):
        raise ValueError("model_feature_schema_invalid")
    k = len(names) + 1
    if league in BINARY:
        coef = model.get("binary_logistic_coefficients")
        if (not isinstance(coef, list) or len(coef) != k
                or any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 100 for v in coef)):
            raise ValueError("binary_logistic_coefficients_invalid")
    else:
        coefs = model.get("three_way_softmax_coefficients")
        if (not isinstance(coefs, dict) or set(coefs) != set(SIDES[league])
                or any(not isinstance(coefs[side], list) or len(coefs[side]) != k
                       or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100
                              for v in coefs[side]) for side in SIDES[league])):
            raise ValueError("three_way_softmax_coefficients_invalid")
    return trained


def predict_game(model, league, features):
    """Raw native-model mathematical scoring, not fitted here and not calibrated."""
    names = model["feature_names"]
    if not isinstance(features, dict) or set(features) != set(names):
        raise ValueError("candidate_feature_schema_mismatch")
    vals = []
    for n, avg, std in zip(names, model["feature_means"], model["feature_stds"]):
        v = features[n]
        if type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6:
            raise ValueError("candidate_feature_invalid")
        vals.append((v - avg) / std)
    def linear(coef):
        return coef[0] + sum(v * weight for v, weight in zip(vals, coef[1:]))
    if league in BINARY:
        z = linear(model["binary_logistic_coefficients"])
        home = 1 / (1 + math.exp(-max(-100, min(100, z))))
        return {"home": home, "away": 1 - home}
    scores = {side: linear(model["three_way_softmax_coefficients"][side]) for side in SIDES[league]}
    highest = max(scores.values())
    weights = {side: math.exp(value - highest) for side, value in scores.items()}
    total = sum(weights.values())
    return {side: weights[side] / total for side in SIDES[league]}


def capture_multisport(snapshots, candidates, models, now=None, run_id=None):
    """Only genuine matching pregame events; every result remains unqualified."""
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    clock = clock.astimezone(timezone.utc)
    schedule, duplicate = {}, set()
    for snap in snapshots:
        try:
            key, captured = validate_snapshot(snap, clock)
            if key[0] not in CAPTURE_LEAGUES or not clock < instant(snap["event_start_utc"]):
                continue
            if key in schedule:
                duplicate.add(key)
            else:
                schedule[key] = (snap, captured)
        except (TypeError, KeyError, ValueError, OverflowError):
            continue
    model_status = {}
    trained_by_league = {}
    for league in LEAGUES:
        if league == "nba":
            model_status[league] = "delegated_to_existing_nba_specialist_recorder"
            continue
        try:
            trained_by_league[league] = check_model(models.get(league), league, clock)
            model_status[league] = "unverified_research_model_format_passed"
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            model_status[league] = "blocked_" + str(exc)
    excluded, output, seen = Counter(), [], set()
    for c in candidates:
        try:
            if not isinstance(c, dict):
                raise ValueError("candidate_not_object")
            league, event_id = c.get("league"), c.get("event_id")
            if league not in CAPTURE_LEAGUES:
                raise ValueError("unsupported_league_or_nba_delegated")
            if not isinstance(event_id, str) or not event_id.isdigit():
                raise ValueError("invalid_espn_game_id")
            key = (league, event_id)
            if key in seen:
                raise ValueError("duplicate_candidate_event")
            seen.add(key)
            if league not in trained_by_league:
                raise ValueError("qualified_research_model_unavailable")
            if key in duplicate or key not in schedule:
                raise ValueError("missing_or_ambiguous_same_run_event")
            snap, captured = schedule[key]
            model = models[league]
            trained = trained_by_league[league]
            if (c.get("market_type") != MARKETS[league]
                    or c.get("settlement_scope") != SCOPE[league]
                    or c.get("home_team") != snap["home_team"]
                    or c.get("away_team") != snap["away_team"]
                    or c.get("event_source_url") != snap["schedule_source_url"]
                    or instant(c.get("start_utc")) != instant(snap["event_start_utc"])
                    or c.get("availability_reviewed") is not True
                    or any(not _url(c.get(name)) for name in
                           ("event_source_url", "feature_source_url", "availability_source_url"))
                    or c.get("probability_source") in ("sportsbook_implied", "market_break_even", "untrained_fixed_rule")):
                raise ValueError("identity_market_source_or_availability_invalid")
            forecast_time = instant(c.get("snapshot_utc"))
            features_at = instant(c.get("features_asof_utc"))
            availability_at = instant(c.get("availability_checked_at_utc"))
            if not (trained <= captured <= forecast_time <= clock < instant(c["start_utc"])
                    and forecast_time - captured <= timedelta(hours=2)
                    and features_at <= forecast_time
                    and forecast_time - timedelta(hours=2) <= availability_at <= forecast_time):
                raise ValueError("pregame_timestamp_feature_leak_or_stale_availability")
            probabilities = predict_game(model, league, c.get("features"))
            if abs(sum(probabilities.values()) - 1) > 1e-9:
                raise ValueError("invalid_probability_sum")
            for side in SIDES[league]:
                output.append({
                    "stage": "challenger_001_multisport_prospective_research_only",
                    "league": league, "event_id": event_id,
                    "home_team": snap["home_team"], "away_team": snap["away_team"],
                    "market_type": MARKETS[league], "settlement_scope": SCOPE[league],
                    "selection_key": side, "research_probability": round(probabilities[side], 9),
                    "model_version": model["model_version"],
                    "model_sha256": model["artifact_sha256"],
                    "source_snapshot_sha256": digest(snap),
                    "candidate_claim_sha256": digest(c),
                    "snapshot_utc": forecast_time.isoformat(),
                    "scored_at_utc": clock.isoformat(),
                    "event_start_utc": c["start_utc"],
                    "archive_run_id_self_reported": str(run_id) if run_id else None,
                    "probability_source": "native_challenger_model_unverified_research",
                    "market_implied_probability_used_as_model": False,
                    "source_evidence_independently_authenticated": False,
                    "model_fit_independently_certified": False,
                    "qualified_for_calibration": False,
                    "certified_prediction": False, "bet_ready": False,
                    "wager_stake": 0, "champion_001_modified": False,
                })
        except (KeyError, ValueError, TypeError, OverflowError) as e:
            excluded[str(e)[:100]] += 1
    report = {
        "stage": "challenger_001_eight_sport_native_research_capture",
        "as_of_utc": clock.isoformat(),
        "supported_leagues": list(LEAGUES),
        "binary_full_game_leagues": sorted(BINARY),
        "soccer_regulation_three_way_leagues": sorted(THREE_WAY),
        "per_league_model_gate": model_status,
        "candidate_rows_received": len(candidates),
        "market_selections_captured_uncertified": len(output),
        "unique_games_scored_uncertified": len({(r["league"], r["event_id"]) for r in output}),
        "rejected": dict(sorted(excluded.items())),
        "player_prop_probability_models_available": 0,
        "source_independent_provenance_authenticated": False,
        "models_independently_calibrated": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Model metadata and archive SHA are self-attested only. "
                    "No trained models or live pregame feature candidates are shipped for "
                    "the non-NBA leagues. NBA uses its separate native scorer. "
                    "Soccer markets are three-way regulation results; no player props "
                    "or real-money forecasts are certified."),
    }
    return output, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshots", default="prospective_pregame/prospective_event_evidence.jsonl")
    ap.add_argument("--candidates", default="prospective_pregame/multisport_game_candidates.jsonl")
    ap.add_argument("--model-dir", default="challenger_results/multisport_models")
    ap.add_argument("--output-dir", default="prospective_pregame")
    ap.add_argument("--run-id")
    args = ap.parse_args(argv)
    snapshots_path, candidate_path = Path(args.snapshots), Path(args.candidates)
    snapshots = ([json.loads(x) for x in snapshots_path.read_text().splitlines() if x.strip()]
                 if snapshots_path.is_file() else [])
    candidates = ([json.loads(x) for x in candidate_path.read_text().splitlines() if x.strip()]
                  if candidate_path.is_file() else [])
    models = {}
    for league in CAPTURE_LEAGUES:
        path = Path(args.model_dir) / (league + ".json")
        if path.is_file():
            models[league] = json.loads(path.read_text(encoding="utf-8"))
    receipts, report = capture_multisport(snapshots, candidates, models, run_id=args.run_id)
    report["models_present"] = sorted(models)
    report["candidate_file_present"] = candidate_path.is_file()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / FORECAST_FILE).write_text("".join(canonical(x) + "\n" for x in receipts), encoding="utf-8")
    (out / "multisport_native_capture_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": report["stage"],
                      "research_selections": len(receipts),
                      "certified_positive_ev_bets": 0,
                      "model_sports_available": len(models),
                      "report": str(out/"multisport_native_capture_report.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
