"""Unified, conservative GitHub Actions health monitor.

Auto-retry only known transient workflow failures, at most once per run.
Never auto-edit code, merge PRs, rewrite training data, or certify predictions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
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
        return json.load(response) if response.status != 201 or method == "GET" else {}

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

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="unified_health_report.json")
    args = p.parse_args()
    token = os.getenv("GH_TOKEN", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repo:
        raise SystemExit("GH_TOKEN and GITHUB_REPOSITORY required")
    runs = api("/actions/runs?per_page=100", token, repo).get("workflow_runs", [])
    # Fail closed: no automatic retry until trusted job-log classification is implemented.
    report = audit(runs, {}, auto_retry=False)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status":"HOLD","workflow_count":len(report["latest_by_workflow"]),
                      "missing":report["missing_workflows"],"certified_takes":0}))
if __name__ == "__main__":
    main()
