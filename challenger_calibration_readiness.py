"""Fail-closed Challenger-001 calibration dependency diagnostic (research only).

This module examines reports already produced by the archive bridge and the
isotonic runner. It NEVER creates probability rows, validates outside-source
authenticity, fits models, modifies Champion-001, or certifies bets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _nonnegative_count(report, key):
    value = report.get(key, 0)
    if type(value) is not int or value < 0:
        raise ValueError("invalid diagnostic count: " + key)
    return value


def diagnose(bridge, calibration, evidence_exists=False):
    """Explain the actual missing dependency without promoting research data."""
    if not isinstance(bridge, dict) or not isinstance(calibration, dict):
        raise ValueError("expected bridge and calibration reports")
    if bridge.get("stage") != "challenger_native_calibration_evidence_bridge_research_only":
        raise ValueError("unrecognized bridge report")
    if calibration.get("stage") != "challenger_001_daily_isotonic_recalibration_research_only":
        raise ValueError("unrecognized calibration report")
    for name, report in (("bridge", bridge), ("calibration", calibration)):
        if report.get("champion_001_modified") is not False:
            raise ValueError(name + ": Champion safety assertion failed")
        for key in ("certified_champion_001_predictions",
                    "certified_challenger_001_predictions",
                    "certified_positive_ev_bets", "automated_wagers_placed"):
            if _nonnegative_count(report, key) != 0:
                raise ValueError(name + ": betting/certification invariant failed: " + key)

    if bridge.get("calibration_evidence_file_created") is not False:
        raise ValueError("bridge is not allowed to produce trusted calibration input")
    if bridge.get("review_flags_automatically_promoted") is not False:
        raise ValueError("bridge unexpectedly promoted review flags")
    native = _nonnegative_count(bridge, "native_forecast_rows_seen")
    linked = _nonnegative_count(bridge, "linked_rows_seen")
    staged = _nonnegative_count(bridge, "unqualified_native_forecast_outcome_pairs_staged")
    qualified = _nonnegative_count(bridge, "independently_qualified_calibration_rows")
    fitted = _nonnegative_count(calibration, "research_artifacts_written")
    if qualified != 0:
        raise ValueError("bridge has no authority to qualify calibration examples")

    if native == 0:
        blocker = "missing_native_challenger_pregame_forecasts"
        next_step = ("Capture genuine native Challenger model outputs with original "
                     "before-tipoff time, version and input-source receipts. Do not "
                     "substitute an Elo baseline, bookmaker implied odds or hindsight.")
    elif linked == 0:
        blocker = "missing_linked_published_outcomes"
        next_step = ("Collect independently reviewable later outcome receipts for the "
                     "already archived native forecast event IDs.")
    elif staged == 0:
        blocker = "no_valid_native_forecast_outcome_matches"
        next_step = ("Inspect event identity, duplicate rows, original capture times "
                     "and source-integrity rejections; do not backdate forecasts.")
    elif not evidence_exists:
        blocker = "missing_independently_reviewed_calibration_input"
        next_step = ("Independently verify feature timing, source provenance, native "
                     "model execution and settled outcomes before supplying a distinct "
                     "calibration input. Do not copy the review queue.")
    else:
        blocker = "independent_input_and_fit_require_manual_review"
        next_step = ("Audit the separately supplied input, chronological 200/50 split "
                     "and holdout before considering research calibration metrics.")
    return {
        "stage": "challenger_calibration_dependency_diagnostic_research_only",
        "status": "HOLD_RESEARCH_ONLY",
        "primary_blocker": blocker,
        "underlying_bridge_status": bridge.get("status", "unknown"),
        "isotonic_status": calibration.get("status", "unknown"),
        "native_pregame_forecasts_found": native,
        "linked_published_outcomes_found": linked,
        "unqualified_research_pairs_staged": staged,
        "independently_qualified_bridge_rows": qualified,
        "separate_calibration_input_present_not_authenticated": bool(evidence_exists),
        "research_calibrators_written_by_runner": fitted,
        "next_safe_step": next_step,
        "verified_betting_edge": False,
        "independently_authenticated_by_this_diagnostic": False,
        "calibration_input_created": False,
        "review_queue_promoted": False,
        "champion_001_modified": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers_placed": 0,
        "warning": ("A successful GitHub job or a local evidence filename is not "
                    "proof of an independently authenticated prediction or outcome."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-report",
                        default="challenger_results/calibration_evidence/report.json")
    parser.add_argument("--calibration-report",
                        default="challenger_results/isotonic_recalibration/report.json")
    parser.add_argument("--evidence", default="challenger_oos_probabilities.jsonl")
    parser.add_argument("--output-dir", default="challenger_results/calibration_evidence")
    args = parser.parse_args(argv)
    bridge = json.loads(Path(args.bridge_report).read_text(encoding="utf-8"))
    calibration = json.loads(Path(args.calibration_report).read_text(encoding="utf-8"))
    evidence_path = Path(args.evidence)
    report = diagnose(bridge, calibration, evidence_path.is_file() and
                      evidence_path.stat().st_size > 0)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "dependency_diagnostic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = [
        "### Challenger-001 evidence dependency (research only)",
        "- **Status:** HOLD — no certified model or bets",
        "- **Primary blocker:** " + report["primary_blocker"],
        "- **Actual isotonic status:** " + report["isotonic_status"],
        "- **Native pregame forecast rows recovered:** " + str(report["native_pregame_forecasts_found"]),
        "- **Linked published outcomes recovered:** " + str(report["linked_published_outcomes_found"]),
        "- **Unqualified matched review pairs:** " + str(report["unqualified_research_pairs_staged"]),
        "- **Independent bridge-qualified rows:** 0",
        "- **Next safe step:** " + report["next_safe_step"],
        "- **Champion-001:** unchanged and frozen; certified picks / wagers: 0",
        "",
        "A downloaded artifact, a review flag, a file on disk, or a green CI result "
        "does **not** establish authentic pregame predictions or verified odds.",
    ]
    (out / "DEPENDENCY_STATUS.md").write_text("\n".join(markdown) + "\n",
                                               encoding="utf-8")
    print(json.dumps({"primary_blocker": report["primary_blocker"],
                      "research_only": True, "certified_bets": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
