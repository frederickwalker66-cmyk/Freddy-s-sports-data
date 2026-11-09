"""V8 research source cadence watchdog: safely request missing source captures.

Only compares actual GitHub Actions run metadata. GitHub cron is best-effort;
a new dispatch does not prove the job ran, data was archived or a model was
calibrated. Rate-limited dispatch targets the pre-existing public-source-only
source preflight workflow on main. No paid SharpAPI or sportsbook calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess

TARGET = "challenger-eight-sport-source-preflight.yml"
REPO = "frederickwalker66-cmyk/Freddy-s-sports-data"
MAX_AGE_MINUTES = 150
MAX_RECOVERY_ATTEMPTS_PER_DAY = 4
ACTIVE_STATUSES = frozenset(("queued", "in_progress", "pending", "waiting", "requested"))


def utc(value):
    if not isinstance(value, str):
        raise ValueError("missing_timezone_aware_github_timestamp")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("missing_timezone_aware_github_timestamp")
    return d.astimezone(timezone.utc)


def evaluate(payload, now=None):
    observed = now or datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    observed = observed.astimezone(timezone.utc)
    report = {
        "stage": "v8_source_cadence_recovery_diagnostic_research_only",
        "checked_at_utc": observed.isoformat(),
        "source_workflow": TARGET,
        "max_minutes_without_completed_success": MAX_AGE_MINUTES,
        "max_recovery_attempts_per_24h": MAX_RECOVERY_ATTEMPTS_PER_DAY,
        "latest_successful_workflow_run_id": None,
        "latest_successful_workflow_completion_utc": None,
        "minutes_since_latest_successful_run": None,
        "in_flight_source_run_ids": [],
        "recent_workflow_dispatch_runs_24h": 0,
        "recovery_decision": "HOLD",
        "reason": "metadata_unavailable",
        "dispatch_attempted": False,
        "dispatch_accepted": False,
        "source_data_independently_authenticated": False,
        "model_probabilities_independently_verified": False,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
    }
    if not isinstance(payload, dict) or payload.get("fetch_error") is True:
        return report
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        return report
    checked, seen = [], set()
    for item in runs:
        if not isinstance(item, dict) or type(item.get("id")) is not int:
            continue
        if item["id"] in seen or item.get("head_branch") != "main":
            continue
        seen.add(item["id"])
        try:
            created = utc(item["created_at"])
            updated = utc(item["updated_at"])
        except (KeyError, ValueError, TypeError):
            continue
        if not (created <= updated <= observed + timedelta(minutes=2)):
            continue
        checked.append((item, created, updated))
    active = [item["id"] for item, created, updated in checked
              if item.get("status") in ACTIVE_STATUSES]
    report["in_flight_source_run_ids"] = sorted(active)
    successes = [(updated, item["id"]) for item, created, updated in checked
                 if item.get("status") == "completed"
                 and item.get("conclusion") == "success"]
    recent_dispatches = sum(
        item.get("event") == "workflow_dispatch"
        and observed - timedelta(hours=24) <= created <= observed
        for item, created, updated in checked
    )
    report["recent_workflow_dispatch_runs_24h"] = recent_dispatches
    if successes:
        last, run_id = max(successes)
        report["latest_successful_workflow_run_id"] = run_id
        report["latest_successful_workflow_completion_utc"] = last.isoformat()
        report["minutes_since_latest_successful_run"] = round(
            (observed - last).total_seconds() / 60, 2)
    if active:
        report["reason"] = "source_workflow_already_in_flight"
    elif successes and report["minutes_since_latest_successful_run"] < MAX_AGE_MINUTES:
        report["reason"] = "recent_successful_source_workflow"
    elif recent_dispatches >= MAX_RECOVERY_ATTEMPTS_PER_DAY:
        report["reason"] = "recovery_attempt_budget_exhausted_24h"
    else:
        report["recovery_decision"] = "REQUEST_ONE_PUBLIC_SOURCE_CAPTURE"
        report["reason"] = "source_workflow_success_stale_or_absent"
    return report


def dispatch(report, *, execute=False, token=None, runner=None):
    """Dispatch only the single fixed safe workflow; never call a paid source."""
    if (not isinstance(report, dict)
            or report.get("recovery_decision") != "REQUEST_ONE_PUBLIC_SOURCE_CAPTURE"
            or report.get("source_workflow") != TARGET
            or report.get("dispatch_attempted") is not False):
        return report
    if not execute:
        return report
    if not token:
        report["recovery_decision"] = "HOLD"
        report["reason"] = "github_actions_token_missing"
        return report
    report["dispatch_attempted"] = True
    args = ["gh", "api", "--method", "POST",
            f"repos/{REPO}/actions/workflows/{TARGET}/dispatches",
            "-f", "ref=main"]
    try:
        if runner is not None:
            result = runner(args)
        else:
            result = subprocess.run(args, text=True, capture_output=True,
                                    timeout=30, check=False, env=dict(os.environ, GH_TOKEN=token))
        accepted = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        accepted = False
    report["dispatch_accepted"] = accepted
    # Even an HTTP 204 acceptance is NOT a source run completion.
    report["reason"] = "github_dispatch_accepted_not_observed_as_run" if accepted else "github_dispatch_failed"
    report["recovery_decision"] = "DISPATCH_ACCEPTED_UNVERIFIED" if accepted else "DISPATCH_FAILED"
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs-json", required=True)
    p.add_argument("--output", default="v8_results/source_watchdog.json")
    p.add_argument("--execute-recovery", action="store_true")
    args = p.parse_args(argv)
    evidence = json.loads(Path(args.runs_json).read_text(encoding="utf-8"))
    report = evaluate(evidence)
    report = dispatch(report, execute=args.execute_recovery, token=os.environ.get("GH_TOKEN"))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "recovery_decision": report["recovery_decision"],
        "reason": report["reason"],
        "source_workflow_run_completed_now": False,
        "certified_positive_ev_bets": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
