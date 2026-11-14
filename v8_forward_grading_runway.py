"""Audit NBA original-forecast grading backlog; no performance or betting claims.

Forecast maturity and grade completeness are workflow quality measurements,
NOT win accuracy or calibrated expected value. Uses the durable ledger's
existing first-receipt history, never reconstructs missing predictions.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from math import ceil, floor, isfinite

from historical_outcomes import parse_time

GRADE = "GRADED_ESPN_PUBLISHED_FINAL_RESEARCH_ONLY"
PENDING = "PENDING_48H_RESULT_MATURITY"
DUE = "HOLD_NO_GRADED_PUBLISHED_RESULT"
QUARANTINED = "QUARANTINED_CONFLICT_NOT_GRADED"
ALLOWED = frozenset((GRADE, PENDING, DUE, QUARANTINED))
RESEARCH_BRIER_MIN_GAMES = 50
RESEARCH_ECE_MIN_GAMES = 100


def _pct(n, d):
    return round(n / d * 100, 1) if d else None


def _quantile(vals, q):
    if not vals:
        return None
    x = sorted(vals)
    i = (len(x) - 1) * q
    lo = floor(i)
    hi = ceil(i)
    return round(x[lo] + (x[hi] - x[lo]) * (i - lo), 2)


def grade_runway(history, *, now=None, days_deferred=0, source_days_checked=0):
    """Statistically honest coverage and ageing from original saved forecasts.

    No "missed forecasts" inferred from total NBA schedule. A missing record
    cannot be counted as a prediction. No ROI, accuracy, or calibration created.
    """
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    if not isinstance(history, list):
        raise ValueError("durable_forward_history_list_required")
    if any(type(v) is not int or v < 0 for v in (days_deferred, source_days_checked)):
        raise ValueError("source_day_counters_must_be_nonnegative")
    status = Counter()
    seen = set()
    lead_minutes = []
    due_age_hours = []
    grade_delay_hours = []
    last_week_captures = 0
    for row in history:
        if not isinstance(row, dict):
            raise ValueError("invalid_durable_forward_history_row")
        if row.get("sport") != "nba":
            raise ValueError("only_unchanged_NBA_original_forecasts_allowed")
        eid = row.get("espn_event_id")
        if not isinstance(eid, str) or not eid.isdecimal() or eid in seen:
            raise ValueError("duplicate_or_invalid_forward_event")
        seen.add(eid)
        if (row.get("certified_prediction") is not False
                or row.get("certified_champion_001_shadow") is not False
                or row.get("positive_ev_certified") is not False
                or row.get("wager_stake_usd") != 0):
            raise ValueError("cannot_promote_grade_health_to_a_bet")
        when = parse_time(row["original_forecast_utc"])
        start = parse_time(row["original_tipoff_utc"])
        if not when < start:
            raise ValueError("first_original_forecast_not_pregame")
        if when > clock:
            raise ValueError("future_original_forecast_receipt")
        lead = (start - when).total_seconds() / 60
        lead_minutes.append(lead)
        if clock - timedelta(days=7) <= when <= clock:
            last_week_captures += 1
        state = row.get("grade_status")
        if state not in ALLOWED:
            raise ValueError("unknown_forward_grading_state")
        elapsed = (clock - start).total_seconds() / 3600
        y = row.get("home_won_published_final_research_only")
        if state == GRADE:
            if type(y) is not int or y not in (0, 1) or elapsed < 48:
                raise ValueError("grade_missing_final_or_not_mature")
            published = parse_time(row["published_final_observed_utc"])
            if not start < published <= clock:
                raise ValueError("grade_without_valid_observation_time")
            grade_delay_hours.append((published - start).total_seconds() / 3600)
        elif y is not None:
            raise ValueError("ungraded_forecast_has_outcome_label")
        elif state == PENDING and elapsed >= 48:
            raise ValueError("stale_maturity_state")
        elif state == DUE:
            if elapsed < 48:
                raise ValueError("unmature_forecast_misclassified_as_missing")
            due_age_hours.append(elapsed - 48)
        status[state] += 1
    n = len(history)
    graded = status[GRADE]
    due = status[DUE]
    pending = status[PENDING]
    quarantine = status[QUARANTINED]
    if graded + due + pending + quarantine != n:
        raise ValueError("inconsistent_forward_grade_partition")
    return {
        "report_type": "v8_durable_nba_forward_grading_runway_v1",
        "observed_at_utc": clock.isoformat(),
        "total_saved_original_forecasts": n,
        "genuinely_forward_grades": graded,
        "awaiting_48h_maturity": pending,
        "mature_due_without_accepted_final": due,
        "quarantined_conflicting_forecasts": quarantine,
        "mature_eligible_nonquarantined": graded + due,
        "grade_completeness_of_mature_nonquarantined_pct": _pct(
            graded, graded + due),
        "grade_coverage_of_all_archived_pct": _pct(graded,n),
        "forecast_captures_last_7_days": last_week_captures,
        "source_scoreboard_days_checked_last_batch": source_days_checked,
        "source_days_deferred_due_to_budget": days_deferred,
        "mature_ungraded_age_over_7_days": sum(v>7*24 for v in due_age_hours),
        "oldest_mature_ungraded_hours_after_48h_gate":
            round(max(due_age_hours),2) if due_age_hours else None,
        "median_original_pregame_lead_minutes": _quantile(lead_minutes,.5),
        "original_pregame_lead_p10_minutes": _quantile(lead_minutes,.1),
        "original_pregame_lead_under_15_minutes": sum(
            v < 15 for v in lead_minutes),
        "median_published_final_observation_delay_hours_after_tipoff":
            _quantile(grade_delay_hours,.5),
        "additional_graded_to_50": max(0,RESEARCH_BRIER_MIN_GAMES-graded),
        "additional_graded_to_100": max(0,RESEARCH_ECE_MIN_GAMES-graded),
        "next_priority": (
            "REVIEW_STALE_MATURED_UNGRADED_RESULTS" if due_age_hours else
            "COLLECT_MORE_UNCHANGED_PRETIPOFF_FORECASTS_AND_WAIT_FOR_MATURITY"
        ),
        "graded_sample_is_sufficient_for_published_skill":
            graded >= RESEARCH_BRIER_MIN_GAMES,
        "graded_sample_is_sufficient_for_ece_count_only":
            graded >= RESEARCH_ECE_MIN_GAMES,
        "predictive_accuracy_or_roi_computed": False,
        "no_missing_predictions_backfilled": True,
        "no_sportsbook_prices_inferred": True,
        "original_champion_001_modified": False,
        "calibrated_betting_model_created": False,
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
    }
