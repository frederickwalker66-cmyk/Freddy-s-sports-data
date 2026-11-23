"""Unified, conservative GitHub Actions health monitor.

Auto-retry only known transient workflow failures, at most once per run.
Never auto-edit code, merge PRs, rewrite training data, or certify predictions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from datetime import timedelta
from pathlib import Path
import urllib.error
import urllib.request

CRITICAL = {
    "freddys-operational-readiness.yml",
    "prediction-mode.yml",
    "challenger-multisport-training.yml",
    "sportsdataio-nba-live-readiness.yml",
}
TRANSIENT = ("rate limit", "http 429", "502 bad gateway", "503 service unavailable",
             "504 gateway", "connection reset", "timed out", "timeout while")
def api(path, token, repo, method="GET"):
    request = urllib.request.Request(
        "https://api.github.com/repos/" + repo + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "freddys-unified-repair"},
        method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        if method != "GET": return {}
        return json.load(response)

def audit(runs, attempts, *, auto_retry=False, retry=None):
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "prediction_mode": "HOLD_UNTIL_TRAINED_ARTIFACT_AND_PREGAME_INPUTS",
              "sharp_edge": "HOLD", "certified_takes": 0,
              "champion_001_modified": False, "workflows": [], "retry_attempts": attempts}
    for run in runs:
        workflow = run.get("path", "").split("/")[-1]
        if workflow not in CRITICAL or run.get("head_branch") != "main":
            continue
        status = run.get("status")
        conclusion = run.get("conclusion")
        item = {"workflow": workflow, "run_id": run.get("id"),
                "status": status, "conclusion": conclusion, "repair": "none"}
        run_id = run.get("id")
        if (auto_retry and retry is not None and status == "completed" and conclusion == "failure"
                and isinstance(run_id, int) and str(run_id) not in attempts
                and run.get("event") in ("schedule", "workflow_dispatch")
                and run.get("transient_failure_verified") is True):
            # Caller must supply verified log classification, never guess from failure.
            retry(run_id)
            attempts[str(run_id)] = "retry_requested_once"
            item["repair"] = "transient_failed_jobs_retry_requested"
        elif conclusion == "failure":
            item["repair"] = "manual_review_required"
        report["workflows"].append(item)
    report["workflows"].sort(key=lambda x: (x["workflow"], -(x["run_id"] or 0)))
    latest = {}
    for item in report["workflows"]:
        latest.setdefault(item["workflow"], item)
    report["latest_by_workflow"] = latest
    report["missing_workflows"] = sorted(CRITICAL - set(latest))
    return report

def transient_log(log):
    """Allow only explicit network/upstream errors, never application test failures."""
    if not isinstance(log, str) or len(log) > 500_000:
        return False
    lines = log.lower().splitlines()
    errors = [line for line in lines if re.search(r"error|fatal|exception|failed|timed out|timeout", line)]
    unsafe = ("assertionerror", "assert ", "permission denied", "unauthorized",
              "invalid api key", "bad credentials", "secret", "authentication failed",
              "syntaxerror", "modulenotfounderror", "test failed")
    return bool(errors) and any(any(t in line for t in TRANSIENT) for line in errors) and not any(
        any(bad in line for bad in unsafe) for line in errors)

def recover_latest(runs, token, repo, *, now=None, get_jobs=None, get_log=None, rerun=None):
    """At most one retry per original run; GitHub run_attempt persists across schedules."""
    now = now or datetime.now(timezone.utc)
    latest = {}
    for run in runs:
        name = run.get("path", "").split("/")[-1]
        if name in CRITICAL and run.get("head_branch") == "main":
            if name not in latest or run.get("created_at", "") > latest[name].get("created_at", ""):
                latest[name] = run
    results = []
    for name, run in sorted(latest.items()):
        item = {"workflow": name, "run_id": run.get("id"), "action": "none"}
        try:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            eligible = (run.get("status") == "completed" and run.get("conclusion") == "failure"
                        and run.get("event") in ("schedule", "workflow_dispatch")
                        and run.get("run_attempt") == 1 and run.get("head_branch") == "main"
                        and timedelta(0) <= now - created <= timedelta(hours=24))
            if not eligible:
                item["action"] = "not_eligible"
            else:
                jobs = get_jobs(run["id"])
                failed = [j for j in jobs if j.get("conclusion") == "failure"]
                if not failed or len(failed) > 3:
                    item["action"] = "manual_review"
                elif all(transient_log(get_log(j["id"])) for j in failed):
                    rerun(run["id"])
                    item["action"] = "retry_requested_once"
                else:
                    item["action"] = "manual_review"
        except (KeyError, TypeError, ValueError, urllib.error.URLError, TimeoutError) as exc:
            item["action"] = "diagnostic_error_no_retry"
        results.append(item)
    return results

PIPELINE_STAGES = {
    "data_collection": ("refresh-nba-mlb-evidence.yml", "sportsdataio-nba-live-readiness.yml"),
    "challenger_training": ("option-b-nba-training.yml", "challenger-multisport-training.yml", "all-eight-sports-training.yml"),
    "prediction": ("prediction-mode.yml",),
    "certification_guard": ("freddys-operational-readiness.yml",),
}
def pipeline_status(runs):
    """CI health only; successful jobs do not prove verified training data."""
    latest = {}
    for run in runs:
        name = run.get("path", "").split("/")[-1]
        if run.get("head_branch") != "main":
            continue
        if name not in latest or run.get("created_at", "") > latest[name].get("created_at", ""):
            latest[name] = run
    result = {}
    for stage, workflows in PIPELINE_STAGES.items():
        checks = {}
        for name in workflows:
            run = latest.get(name)
            checks[name] = {"run_id": run.get("id") if run else None,
                            "status": run.get("status") if run else "missing",
                            "conclusion": run.get("conclusion") if run else None}
        result[stage] = {"ci_state": "PASS" if all(x["conclusion"] == "success" for x in checks.values()) else "NEEDS_REVIEW",
                         "workflows": checks, "evidence_verified": False, "certified": False}
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="unified_health_report.json")
    p.add_argument("--enable-safe-retry", action="store_true")
    args = p.parse_args()
    token = os.getenv("GH_TOKEN", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repo:
        raise SystemExit("GH_TOKEN and GITHUB_REPOSITORY required")
    # Repository-wide first-page results can omit infrequently run critical jobs.
    runs = api("/actions/runs?per_page=100", token, repo).get("workflow_runs", [])
    seen = {run.get("id") for run in runs}
    for workflow in sorted(CRITICAL):
        try:
            recent = api(f"/actions/workflows/{workflow}/runs?branch=main&per_page=10",
                         token, repo).get("workflow_runs", [])
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        for run in recent:
            if run.get("id") not in seen:
                runs.append(run)
                seen.add(run.get("id"))
    report = audit(runs, {}, auto_retry=False)
    report['pipeline_stages'] = pipeline_status(runs)
    if args.enable_safe_retry:
        def get_jobs(run_id):
            return api(f"/actions/runs/{run_id}/jobs?per_page=100", token, repo).get("jobs", [])
        def get_log(job_id):
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs",
                headers={"Authorization": "Bearer " + token,
                         "User-Agent": "freddys-unified-repair"})
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read(500_001)
            return data.decode("utf-8", errors="replace")
        def rerun(run_id):
            api(f"/actions/runs/{run_id}/rerun-failed-jobs", token, repo, method="POST")
        report["recovery"] = recover_latest(runs, token, repo,
                                            get_jobs=get_jobs, get_log=get_log, rerun=rerun)
    else:
        report["recovery"] = "disabled"
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status":"HOLD","workflow_count":len(report["latest_by_workflow"]),
                      "missing":report["missing_workflows"],"certified_takes":0,
                      "recovery":report["recovery"]}))
if __name__ == "__main__":
    main()
