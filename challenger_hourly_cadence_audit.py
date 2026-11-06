"""Audit GitHub's real schedule events; never infer a run from cron configuration.

Research-only operational metadata. A successful Actions job is NOT proof that
its external source was independent, its artifact exists, a price is executable,
or any betting model has been calibrated.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

HOURLY_MINUTE = 27
HOURLY_GRACE_MINUTES = 90
MAX_WINDOW_HOURS = 48

def instant(text):
    if not isinstance(text, str):
        raise ValueError("timezone_aware_iso_timestamp_required")
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timezone_aware_iso_timestamp_required")
    return value.astimezone(timezone.utc)

def evaluate(payload, *, now, activated_at, window_hours=24, grace_minutes=HOURLY_GRACE_MINUTES):
    """Compare *eligible completed* slots with actually created schedule runs.

    Count only the first 24h of actual GitHub metadata. Uncreated/dropped runs
    leave an explicitly missing slot; delayed or in-progress runs remain
    separate. A 90-minute grace avoids prematurely calling an active slot lost.
    """
    if (not isinstance(payload, dict) or not isinstance(now, datetime)
            or not isinstance(activated_at, datetime)
            or now.tzinfo is None or activated_at.tzinfo is None
            or type(window_hours) is not int or not 1 <= window_hours <= MAX_WINDOW_HOURS
            or type(grace_minutes) is not int or not 1 <= grace_minutes <= 180):
        raise ValueError("invalid_hourly_cadence_inputs")
    now = now.astimezone(timezone.utc)
    activated_at = activated_at.astimezone(timezone.utc)
    start = max(activated_at, now - timedelta(hours=window_hours))
    boundary = now - timedelta(minutes=grace_minutes)
    slots = []
    first = start.replace(minute=HOURLY_MINUTE, second=0, microsecond=0)
    if first < start:
        first += timedelta(hours=1)
    cursor = first
    while cursor <= boundary:
        slots.append(cursor)
        cursor += timedelta(hours=1)
    result = {
        "report_type": "github_hourly_schedule_delivery_diagnostic_research_only",
        "observed_at_utc": now.isoformat(),
        "first_schedule_activation_utc": activated_at.isoformat(),
        "hourly_cron_utc": f"{HOURLY_MINUTE} * * * *",
        "window_hours": window_hours,
        "delay_grace_minutes": grace_minutes,
        "eligible_scheduled_slots": len(slots),
        "observed_scheduled_slots": 0,
        "successful_scheduled_workflow_runs": 0,
        "unsuccessful_or_running_scheduled_workflow_runs": 0,
        "unobserved_scheduled_slots": 0,
        "slots": [],
        "metadata_available": False,
        "independent_source_or_artifact_confirmation": False,
        "verified_bookmaker_prices": 0,
        "certified_model_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "note": ("GitHub Actions cron may be delayed or dropped. Count ACTUAL "
                 "schedule-created runs, not promised execution. Successful "
                 "workflow metadata is not independent source or betting proof."),
    }
    if payload.get("fetch_error") is True:
        result["metadata_status"] = "github_actions_api_unavailable_unknown_not_zero"
        result["unobserved_scheduled_slots"] = None
        return result
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("missing_github_actions_workflow_runs_list")
    result["metadata_available"] = True
    result["metadata_status"] = "github_actions_run_metadata_available"
    eligible = []
    for item in runs:
        if not isinstance(item, dict) or item.get("event") != "schedule":
            continue
        try:
            created = instant(item.get("created_at"))
        except (ValueError, TypeError):
            continue
        if (type(item.get("id")) is not int or created < start
                or created > now + timedelta(minutes=2)):
            continue
        eligible.append((created, item))
    eligible.sort(key=lambda pair: (pair[0], pair[1]["id"]))
    # A created run is assigned to the latest eligible hourly slot at or
    # before its timestamp; do not double-count delayed/duplicate executions.
    assigned = {}
    for created, item in eligible:
        candidate = None
        for idx, slot in enumerate(slots):
            if slot <= created <= slot + timedelta(minutes=grace_minutes):
                candidate = idx
        if candidate is not None and candidate not in assigned:
            assigned[candidate] = (created, item)
    for idx, slot in enumerate(slots):
        if idx not in assigned:
            result["slots"].append({"scheduled_for_utc": slot.isoformat(),
                                    "status": "not_observed_in_github_api"})
            continue
        created, item = assigned[idx]
        finished_ok = (item.get("status") == "completed"
                       and item.get("conclusion") == "success")
        result["slots"].append({
            "scheduled_for_utc": slot.isoformat(),
            "workflow_created_utc": created.isoformat(),
            "github_run_id": item["id"],
            "status": "workflow_success_unverified_source" if finished_ok
                      else "workflow_not_successful_or_still_running",
            "github_run_status": str(item.get("status")),
            "github_run_conclusion": item.get("conclusion"),
        })
        result["observed_scheduled_slots"] += 1
        if finished_ok:
            result["successful_scheduled_workflow_runs"] += 1
        else:
            result["unsuccessful_or_running_scheduled_workflow_runs"] += 1
    result["unobserved_scheduled_slots"] = len(slots) - len(assigned)
    assert (result["successful_scheduled_workflow_runs"] +
            result["unsuccessful_or_running_scheduled_workflow_runs"] +
            result["unobserved_scheduled_slots"] == len(slots))
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs-json", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--activated-at", required=True)
    p.add_argument("--hours", type=int, default=24)
    opts = p.parse_args()
    report = evaluate(
        json.loads(Path(opts.runs_json).read_text(encoding="utf8")),
        now=datetime.now(timezone.utc),
        activated_at=instant(opts.activated_at),
        window_hours=opts.hours,
    )
    out = Path(opts.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in (
        "metadata_status", "eligible_scheduled_slots",
        "observed_scheduled_slots", "successful_scheduled_workflow_runs",
        "unobserved_scheduled_slots")}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
