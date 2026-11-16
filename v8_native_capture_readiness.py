"""Read-only native forecast readiness audit for Freddy's Picks AI V8.

Distinct from a successful GitHub job or historical research shadow. Reviews
actual pregame run files to expose missing fitted model and feature artifacts.
It never trains, promotes flags, asserts independent attestation, or bets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls",
           "uefa_champions_league")
ZERO_FLAGS = ("certified_champion_001_predictions",
              "certified_challenger_001_predictions",
              "certified_positive_ev_bets",
              "bet_ready_selections", "automated_bets_placed")


def _nonnegative(value, name):
    if type(value) is not int or value < 0:
        raise ValueError("invalid_counter_" + name)
    return value


def _safe_report(report, name):
    if not isinstance(report, dict) or report.get("champion_001_modified") is not False:
        raise ValueError("unsafe_or_missing_" + name + "_report")
    for flag in ZERO_FLAGS:
        if report.get(flag) != 0:
            raise ValueError("unverified_promotion_in_" + name + "_" + flag)


def _safe_forecast(row):
    return (isinstance(row, dict)
            and row.get("certified_prediction") is False
            and row.get("bet_ready") is False
            and row.get("champion_001_modified") is False
            and row.get("market_implied_probability_used_as_model") is False)


def assess(snapshots, nba_report, multi_report, nba_forecasts, multi_forecasts):
    if not all(isinstance(x, list) for x in
               (snapshots, nba_forecasts, multi_forecasts)):
        raise ValueError("missing_native_capture_evidence_arrays")
    _safe_report(nba_report, "nba")
    _safe_report(multi_report, "multisport")
    nba_count = _nonnegative(
        nba_report.get("actual_native_research_forecasts_written"), "nba")
    multi_count = _nonnegative(
        multi_report.get("market_selections_captured_uncertified"), "multisport")
    if nba_count != len(nba_forecasts) or multi_count != len(multi_forecasts):
        raise ValueError("forecast_report_does_not_match_original_output")
    if not all(_safe_forecast(x) for x in nba_forecasts + multi_forecasts):
        raise ValueError("unsafe_or_implied_native_forecast")
    model_gates = multi_report.get("per_league_model_gate")
    present = multi_report.get("models_present")
    if (not isinstance(model_gates, dict)
            or set(model_gates) != set(LEAGUES)
            or model_gates["nba"] != "delegated_to_existing_nba_specialist_recorder"
            or not isinstance(present, list)
            or any(x not in LEAGUES or x == "nba" for x in present)
            or len(present) != len(set(present))):
        raise ValueError("incomplete_or_conflicting_model_inventory")
    snapshots_by_league = Counter()
    for row in snapshots:
        if not isinstance(row, dict) or row.get("league") not in LEAGUES:
            raise ValueError("invalid_source_snapshot_league")
        if row.get("bet_ready") is not False or row.get("champion_001_modified") is not False:
            raise ValueError("unsafe_source_snapshot")
        snapshots_by_league[row["league"]] += 1
    nba_model_ok = nba_report.get("research_model_artifact_present_and_format_valid") is True
    # A file merely existing does not make a trained model independently proven.
    model_files = {"nba": nba_report.get("model_path_exists") is True}
    for league in LEAGUES[1:]:
        model_files[league] = league in present
    unavailable = [league for league in LEAGUES
                   if not (nba_model_ok if league == "nba" else model_files[league])]
    with_candidates = {
        "nba": _nonnegative(nba_report.get("candidate_rows_supplied"), "nba_candidates")}
    # Multi-sport candidate total is not a per-sport model-ready count.
    multi_candidates = _nonnegative(
        multi_report.get("candidate_rows_received"), "multisport_candidates")
    status = ("blocked_missing_or_invalid_native_model_artifacts"
              if unavailable else
              "research_native_capture_uncertified")
    per_league = {}
    for league in LEAGUES:
        per_league[league] = {
            "original_pregame_source_snapshots": snapshots_by_league[league],
            "model_file_present": model_files[league],
            "model_gate": nba_report.get("status") if league == "nba"
                          else model_gates[league],
            "native_model_artifact_usable_for_research":
                nba_model_ok if league == "nba" else (
                    league in present
                    and model_gates[league] == "unverified_research_model_format_passed"),
            "independent_model_fit_certified": False,
            "certified_predictions": 0,
        }
    return {
        "stage": "v8_eight_sport_native_capture_readiness_research_only",
        "status": status,
        "by_league": per_league,
        "missing_or_invalid_model_leagues": unavailable,
        "nba_native_feature_candidates_seen": with_candidates["nba"],
        "multisport_native_feature_candidates_seen": multi_candidates,
        "actual_native_nba_forecasts": nba_count,
        "actual_native_multisport_selections": multi_count,
        "independently_authenticated_training_examples": 0,
        "minimum_earlier_calibration_predictions_per_exact_market": 200,
        "minimum_later_untouched_evaluations_per_exact_market": 50,
        "calibration_qualified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "next_action": (
            "Independently authenticate historical feature publication, "
            "settled labels and chronological training provenance before "
            "fitting separate immutable Challenger model artifacts. Do not "
            "substitute odds, synthetic forecasts or retrospective predictions."
        ),
    }


def _read_jsonl(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="prospective_pregame")
    p.add_argument("--output", default="prospective_pregame/native_capture_readiness.json")
    args = p.parse_args(argv)
    root = Path(args.root)
    report = assess(
        _read_jsonl(root / "prospective_event_evidence.jsonl"),
        json.loads((root / "native_forecast_capture_report.json").read_text()),
        json.loads((root / "multisport_native_capture_report.json").read_text()),
        _read_jsonl(root / "native_challenger_forecasts.jsonl"),
        _read_jsonl(root / "native_multisport_forecasts.jsonl"),
    )
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "missing_models": report["missing_or_invalid_model_leagues"],
                      "native_forecasts": report["actual_native_nba_forecasts"]
                                          + report["actual_native_multisport_selections"],
                      "certified_predictions": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
