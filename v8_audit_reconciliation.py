"""One-tap, read-only audit of existing V8, SharpAPI, outcome and calibration receipts.

This reconciles independent pipeline *reports*, not betting predictions.
Original source custody, executable DraftKings quotes and frozen Champion-001
model binaries cannot be created by this software. Missing data stay unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from v8_certification_audit import inspect_archives, read_optional

OUTCOME_REPORTS = {
    "release": "prospective_validation/challenger_model_master_diagnostic.json",
    "score_integrity": "prospective_validation/nba_provider_score_integrity_diagnostic.json",
    "research_ledger": "prospective_validation/nba_untrained_moneyline_shadow_ledger_report.json",
}
CALIBRATION_REPORTS = {
    "bridge": "challenger_results/calibration_evidence/report.json",
    "isotonic": "challenger_results/isotonic_recalibration/report.json",
}
SAFETY_COUNTS = {
    "release": ("certified_champion_001_predictions",
                "certified_challenger_001_predictions", "certified_positive_ev_selections",
                "native_trained_probability_models_created", "automatic_wagers_placed",
                "independently_verified_draftkings_checkout_prices"),
    "score_integrity": ("licensed_provider_scores_accepted_for_training",
                        "licensed_provider_odds_accepted_for_positive_ev",
                        "untrusted_provider_scores_auto_corrected"),
    "research_ledger": ("certified_champion_001_predictions",
                        "certified_challenger_001_predictions",
                        "certified_positive_ev_selections"),
    "bridge": ("independently_qualified_calibration_rows",
               "certified_champion_001_predictions",
               "certified_challenger_001_predictions"),
    "isotonic": ("certified_champion_001_predictions",
                 "certified_challenger_001_predictions",
                 "certified_positive_ev_bets"),
}


def _nonnegative(report, key):
    value = report.get(key)
    if type(value) is not int or value < 0:
        raise ValueError("invalid_upstream_count_" + key)
    return value


def inspect_full(source_dir=None, sharp_dir=None, outcome_dir=None,
                 calibration_dir=None, *, source_run_id=None, sharp_run_id=None,
                 outcome_run_id=None, calibration_run_id=None):
    """Return a linked snapshot of *existing* receipts; never issue or grade bets."""
    prior = inspect_archives(source_dir, sharp_dir, source_run_id, sharp_run_id)
    found = {}
    reports = {}
    for key, filename in OUTCOME_REPORTS.items():
        reports[key] = read_optional(outcome_dir, filename)
        found[key] = reports[key] is not None
    for key, filename in CALIBRATION_REPORTS.items():
        reports[key] = read_optional(calibration_dir, filename)
        found[key] = reports[key] is not None
    conflicts = []
    for key, report in reports.items():
        if report is None:
            continue
        if report.get("champion_001_modified") is not False:
            conflicts.append(key + "_champion_integrity_unknown_or_changed")
        for field in SAFETY_COUNTS[key]:
            value = report.get(field)
            if type(value) is not int or value != 0:
                conflicts.append(key + "_untrusted_release_claim_" + field)
    master, suspect = reports["release"], reports["score_integrity"]
    ledger, bridge, isotonic = (reports["research_ledger"], reports["bridge"],
                                reports["isotonic"])
    if master and master.get("release_decision") != "HOLD_NO_CERTIFIED_MODEL_NO_WAGERS":
        conflicts.append("master_release_claim_not_supported")
    if suspect and suspect.get("stage") != "challenger_110_nba_provider_original_score_scramble_integrity":
        conflicts.append("provider_integrity_report_wrong_stage")
    if bridge and bridge.get("stage") != "challenger_native_calibration_evidence_bridge_research_only":
        conflicts.append("native_calibration_bridge_wrong_stage")
    if isotonic and isotonic.get("stage") != "challenger_001_daily_isotonic_recalibration_research_only":
        conflicts.append("calibration_report_wrong_stage")
    suspicious = (_nonnegative(suspect, "suspected_scrambled_score_pattern_days")
                  if suspect else None)
    if suspect:
        dates = suspect.get("dates_with_strong_suspected_transformed_score_pattern")
        if not isinstance(dates, list) or len(dates) != suspicious:
            conflicts.append("suspected_score_day_count_mismatch")
    candidates = (_nonnegative(master, "nba_structurally_valid_research_candidates")
                  if master else None)
    research = (_nonnegative(master, "nba_directional_untrained_heuristic_research_picks")
                if master else None)
    training = (_nonnegative(master, "nba_independently_qualified_training_games")
                if master else None)
    holdout = (_nonnegative(master, "nba_independently_qualified_later_holdout_games")
               if master else None)
    calibrated = (_nonnegative(isotonic, "research_artifacts_written")
                  if isotonic else None)
    if master and (training < 200 or holdout < 50):
        # An explicit model-release blocker, not a test-suite failure.
        native_ready = False
    else:
        native_ready = False  # External release approval is never inferred.
    if master and ledger:
        ledger_selections = _nonnegative(ledger, "directional_nba_research_selections")
        if ledger_selections != research:
            conflicts.append("nba_research_selection_counts_disagree")
    if master and suspect:
        if master.get("suspected_provider_scrambled_score_pattern_days") != suspicious:
            conflicts.append("provider_scramble_days_disagree_with_release")
    if isotonic and bridge and calibrated and not bridge.get("eligible_for_isotonic_fit"):
        conflicts.append("isotonic_artifact_without_native_qualification")
    priority = [
        {
            "priority": 1, "blocker": "FROZEN_CHAMPION_ORIGINAL_MISSING",
            "action": "Recover original Champion-001 executable or weights plus independently authenticated version and reference outputs; keep frozen."
        },
        {
            "priority": 2, "blocker": "NO_AUTHENTICATED_PREGAME_TRAINING_AND_HOLDOUT",
            "action": "Verify original before-start features and outcome source custody; accumulate at least 200 distinct NBA training games and 50 later untouched holdouts."
        },
        {
            "priority": 3, "blocker": "PROVIDER_NUMERIC_DATA_NOT_AUTHENTICATED",
            "action": "Check real-data subscription entitlement and independently compare exact official finals; quarantine suspicious SportsDataIO scores and never rescale them."
        },
        {
            "priority": 4, "blocker": "NO_NATIVE_CHALLENGER_FORECAST_CALIBRATION",
            "action": "Only after independent history qualification fit native Challenger, capture immutable pregame forecasts and measure out-of-sample calibration."
        },
        {
            "priority": 5, "blocker": "NO_EXECUTABLE_SPORTSBOOK_PRICE",
            "action": "Independently verify exact event, market, side, line, time and executable DraftKings price; historical SharpAPI quotes are research only."
        }
    ]
    if conflicts:
        priority.insert(0, {
            "priority": 0, "blocker": "CONTRADICTORY_UPSTREAM_EVIDENCE",
            "action": "Inspect and quarantine the named inconsistent reports before relying on counts."
        })
    return {
        "stage": "v8_read_only_comprehensive_integrity_audit",
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "status": ("HOLD_UPSTREAM_EVIDENCE_CONFLICTS" if conflicts
                   else "HOLD_MISSING_INDEPENDENT_MODEL_AND_PRICE_PROOF"),
        "run_ids": {"source": source_run_id, "sharp": sharp_run_id,
                    "outcome": outcome_run_id, "calibration": calibration_run_id},
        "upstream_reports_found": found,
        "upstream_conflicts": sorted(set(conflicts)),
        "source_pregame_events_archived": prior["source_games_archived"],
        "unverified_sharp_moneyline_pairs": prior["research_moneyline_price_pairs_from_aggregator"],
        "nba_original_research_candidates": candidates,
        "nba_untrained_directional_research_selections": research,
        "suspected_sportsdataio_scrambled_score_dates": suspicious,
        "nba_independently_qualified_training_games": training,
        "nba_independently_qualified_holdout_games": holdout,
        "training_shortfall_to_200": max(0, 200 - training) if training is not None else None,
        "holdout_shortfall_to_50": max(0, 50 - holdout) if holdout is not None else None,
        "native_training_and_calibration_independently_ready": native_ready,
        "calibration_status": isotonic.get("status") if isotonic else None,
        "qualified_calibration_rows": (
            _nonnegative(bridge, "independently_qualified_calibration_rows")
            if bridge else None),
        "uncertified_research_calibration_artifacts": calibrated,
        "original_champion_001_executable_independently_authenticated": False,
        "direct_executable_sportsbook_prices_verified": 0,
        "certified_champion_001_shadow_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
        "champion_001_modified": False,
        "priority_remediation": priority,
        "certification_inventory": prior,
        "warning": ("CI pass != calibrated model or certified betting edge. "
                    "Missing reports are unknown, not zero observed games. "
                    "Historical source receipts and local hashes are not independent provenance."),
    }
