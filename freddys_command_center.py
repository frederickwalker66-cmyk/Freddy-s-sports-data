"""Freddy's Picks AI safe phone control center (GitHub Actions, research only).

Metadata is operational evidence ONLY. A green GitHub job cannot authenticate
a source, create a calibrated prediction, or certify executable sportsbook odds.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

REPO = "frederickwalker66-cmyk/Freddy-s-sports-data"
HOME = "https://github.com/" + REPO
WATCH = {
    "Offline code validation": "validate-data.yml",
    "Hourly source capture": "challenger-eight-sport-source-preflight.yml",
    "NBA live provider": "nba-live-connection.yml",
    "SharpAPI multi-sport": "collect-sharpapi.yml",
    "SportsDataIO intake": "sportsdataio-research-intake.yml",
    "Prospective game capture": "challenger-prospective-pregame.yml",
    "Outcome adjudication": "challenger-prospective-outcome-validation.yml",
    "Calibration research": "challenger-isotonic-calibration.yml",
    "Historical training": "challenger-multisport-training.yml",
    "Source and branch backup": "export-github-source-backup.yml",
}
COMMANDS = {
    "status": (),
    "all_free_diagnostics": ("validate-data.yml", "challenger-eight-sport-source-preflight.yml", "challenger-prospective-outcome-validation.yml"),
    "public_eight_sport_scan": ("challenger-eight-sport-source-preflight.yml",),
    "code_tests": ("validate-data.yml",),
    "outcome_review": ("challenger-prospective-outcome-validation.yml",),
    "calibration_research": ("challenger-isotonic-calibration.yml",),
    "source_backup": ("export-github-source-backup.yml",),
    "nba_live_paid": ("nba-live-connection.yml",),
    "sportsdataio_paid": ("sportsdataio-research-intake.yml",),
}
PAID = {"nba_live_paid", "sportsdataio_paid"}

def approve(command, paid_confirmed):
    if command not in COMMANDS or type(paid_confirmed) is not bool:
        raise ValueError("invalid_allowlisted_command_or_consent")
    if command in PAID and not paid_confirmed:
        raise ValueError("paid_API_requires_separate_explicit_checkbox")
    return COMMANDS[command]

def latest(payload):
    if not isinstance(payload, dict) or payload.get("error") is True:
        return {"status": "github_api_unknown", "run_id": None, "event": None, "url": None}
    if not isinstance(payload.get("workflow_runs"), list):
        return {"status": "malformed_response_unknown", "run_id": None, "event": None, "url": None}
    candidates = []
    for r in payload["workflow_runs"]:
        if not isinstance(r, dict) or r.get("event") == "pull_request":
            continue
        if r.get("head_branch") not in (None, "main") or type(r.get("id")) is not int:
            continue
        try:
            t = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            if t.tzinfo is None: continue
        except (TypeError, KeyError, ValueError, AttributeError):
            continue
        candidates.append((t.astimezone(timezone.utc), r))
    if not candidates:
        return {"status": "no_recent_production_run", "run_id": None, "event": None, "url": None}
    t, r = max(candidates, key=lambda v: (v[0], v[1]["id"]))
    status = r.get("status")
    conclusion = r.get("conclusion")
    if status == "completed" and conclusion == "success":
        state = "job_success_not_model_certification"
    elif status == "completed" and conclusion == "skipped":
        state = "job_skipped"
    elif status == "completed":
        state = "job_failed_or_cancelled"
    elif status in ("queued", "in_progress", "pending", "waiting", "requested"):
        state = "job_pending_or_running"
    else:
        state = "job_status_unknown"
    return {"status": state, "run_id": r["id"], "event": r.get("event"),
            "created_at_utc": t.isoformat(), "url": f"{HOME}/actions/runs/{r['id']}"}

def compose(payloads, branch_protected, accepted, now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("real_aware_timestamp_required")
    if branch_protected not in (True, False, None):
        raise ValueError("branch_protection_must_be_bool_or_unknown")
    workflows = {}
    for display, path in WATCH.items():
        state = latest(payloads.get(path, {"error": True}))
        state["workflow_link"] = f"{HOME}/actions/workflows/{path}"
        workflows[display] = state
    return {
        "created_at_utc": now.astimezone(timezone.utc).isoformat(),
        "repository": REPO,
        "branch_protected": branch_protected,
        "latest_runs": workflows,
        "requested_workflow_dispatches": accepted,
        "model_release_status": "BLOCKED_NOT_CERTIFIED",
        "champion_001_modified": False,
        "champion_001_original_authenticated": False,
        "native_challenger_001_validated": False,
        "direct_draftkings_checkout_quotes_verified": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "caution": "Successful GitHub jobs do not authenticate provider data, model training, sportsbook checkout prices or wagering edge.",
    }

def markdown(report):
    lines = [
        "# Freddy's Picks AI — Phone Command Center",
        "",
        f"Last refreshed (UTC): {report['created_at_utc']}",
        "",
        "**Champion-001 FROZEN | Challenger-001 UNVALIDATED | Certified bets: 0.**",
        f"Main branch protected: **{report['branch_protected'] if report['branch_protected'] is not None else 'UNKNOWN'}**",
        "",
        "| Subsystem | Latest result | Link |",
        "|---|---|---|",
    ]
    for name, state in report["latest_runs"].items():
        link = state["url"] or state["workflow_link"]
        lines.append(f"| {name} | {state['status'].replace('_', ' ')} | [View]({link}) |")
    lines.extend(["", "## Commands requested", ""])
    if report["requested_workflow_dispatches"]:
        for item in report["requested_workflow_dispatches"]:
            lines.append(f"- {item['workflow']}: {'REQUEST ACCEPTED, job not yet verified' if item['accepted'] else 'DISPATCH FAILED'}")
    else:
        lines.append("Status-only view; no new data collection and no paid API usage.")
    lines.extend([
        "", "## Open from laptop or phone browser",
        f"- [Phone command center]({HOME}/actions/workflows/freddys-command-center.yml)",
        f"- [NBA live provider workflow]({HOME}/actions/workflows/nba-live-connection.yml) — paid requests require explicit confirmation.",
        f"- [Outstanding authenticated-model blockers]({HOME}/issues/41)",
        "", "A workflow run, source archive, market label or research direction is NOT a certified Champion/Challenger pick.",
        "GitHub's scheduled workflow starts may be delayed or missed.",
    ])
    return "\n".join(lines) + "\n"

def github_json(endpoint):
    p = subprocess.run(["gh", "api", endpoint], capture_output=True,
                       text=True, check=False, timeout=30)
    if p.returncode != 0:
        return {"error": True}
    try:
        return json.loads(p.stdout)
    except (ValueError, TypeError):
        return {"error": True}

def dispatch(path):
    if path not in WATCH.values():
        raise ValueError("workflow_target_not_allowlisted")
    r = subprocess.run(
        ["gh", "api", "--method", "POST",
         f"repos/{REPO}/actions/workflows/{path}/dispatches", "-f", "ref=main"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    return {"workflow": path, "accepted": r.returncode == 0}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--command", default="status", choices=tuple(COMMANDS))
    p.add_argument("--paid-confirmation", default="false")
    p.add_argument("--output-dir", default="mobile_status")
    args = p.parse_args(argv)
    try:
        targets = approve(args.command, args.paid_confirmation.lower() == "true")
    except ValueError as exc:
        p.error(str(exc))
    if not os.environ.get("GH_TOKEN"):
        p.error("GH_TOKEN_unavailable_no_dispatch")
    dispatches = [dispatch(path) for path in targets]
    responses = {
        path: github_json(f"repos/{REPO}/actions/workflows/{path}/runs?per_page=15")
        for path in WATCH.values()
    }
    raw_branch = github_json(f"repos/{REPO}/branches/main").get("protected")
    protected = raw_branch if type(raw_branch) is bool else None
    report = compose(responses, protected, dispatches, datetime.now(timezone.utc))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "PHONE_DASHBOARD.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    view = markdown(report)
    (out / "PHONE_DASHBOARD.md").write_text(view, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(view)
    print(json.dumps({"command": args.command, "dispatches": dispatches,
                      "model_release": report["model_release_status"]}, sort_keys=True))
    return 1 if any(not d["accepted"] for d in dispatches) else 0

if __name__ == "__main__":
    raise SystemExit(main())
