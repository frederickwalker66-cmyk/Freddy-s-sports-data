"""Six read-only virtual staff roles for Freddy's Picks AI V9.

This coordinator audits existing GitHub workflow metadata. It does not run
paid APIs, authenticate bookmaker prices, infer independent probabilities,
recommend a bet, change Champion-001, or place wagers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from freddys_command_center import WATCH, compose, github_json

STAFF = (
    ("Command Center Manager", ("Offline code validation", "V8 One Command (phone/laptop)", "Public web dashboard")),
    ("Sports Data Analyst", ("Hourly source capture", "SharpAPI multi-sport", "Eight-sport last-5/last-10 source", "NBA official injury evidence")),
    ("Sharp Edge Analyst", ("NBA/NFL Sharp Edge and props", "Calibration research", "V8 all-sports model readiness")),
    ("Parlay Builder", ("V8 One Command (phone/laptop)", "NBA/NFL Sharp Edge and props")),
    ("Risk Manager", ("NBA/NFL Sharp Edge and props", "Outcome adjudication", "Calibration research")),
    ("Audit Engineer", ("Offline code validation", "Source and branch backup", "Persistent NBA forward grade ledger", "Historical training")),
)


def workflow_evidence(report, labels):
    """Show actual workflow metadata; never promote job status to market evidence."""
    runs = report.get("latest_runs") or {}
    result = []
    for label in labels:
        state = runs.get(label) or {}
        result.append({
            "workflow": label,
            "latest_job_status": state.get("status", "unknown"),
            "latest_run_url": state.get("url") or state.get("workflow_link"),
            "job_freshness_only": state.get("operational_freshness", "UNKNOWN"),
            "price_or_model_authentication": "NOT_ESTABLISHED_BY_JOB_METADATA",
        })
    return result


def evaluate(report):
    """Generate a single fail-closed role board from a genuine status snapshot."""
    if not isinstance(report, dict):
        raise ValueError("report_object_required")
    failures = list(report.get("latest_failed_or_cancelled_workflows") or [])
    stale = list(report.get("stale_successful_workflows") or [])
    pending = list(report.get("latest_pending_or_running_workflows") or [])
    incident = bool(failures or stale)
    statuses = (
        "ACTION_REQUIRED" if incident else "METADATA_REVIEW_ONLY",
        "SOURCE_COVERAGE_UNVERIFIED",
        "HOLD_NO_AUTHENTIC_MODEL_EV",
        "HOLD_NO_CERTIFIED_PARLAY",
        "BLOCK_WAGERS_AND_UNVERIFIED_RELEASE",
        "ACTION_REQUIRED" if incident else "AUDIT_MONITOR",
    )
    findings = (
        [f"{len(failures)} latest failed/cancelled workflows; {len(stale)} stale successful runs; {len(pending)} in flight.",
         "A successful workflow does not establish a complete live sportsbook board."],
        ["Read only existing provider and official-source workflow statuses.",
         "League fixtures, player eligibility, quote timestamps and completeness require original source evidence."],
        ["Do not confuse price-implied break-even or no-vig percentages with native Champion-001 probability.",
         "Without original authenticated model forecasts, validated calibration and executable quotes, every candidate is HOLD."],
        ["Game ML, spreads, totals and player PTS/REB/AST/PR/PA/RA/PRA can be reviewed as research only.",
         "Do not fabricate 4-, 6- or 8-leg tickets, joint probabilities, correlation adjustments or parlay EV."],
        ["Champion-001 remains frozen; Challenger-001 remains separate and unpromoted.",
         "No sportsbook orders, paid API dispatch, automatic bets or positive-EV certification."],
        ["Investigate failed, cancelled, stale and unknown workflow states using linked run logs.",
         "Job completion and published historical scores do not authenticate pregame model inputs."],
    )
    actions = (
        "Review affected workflow runs and update the one-screen dashboard.",
        "Inspect source artifacts, player availability, L5/L10 and odds provenance.",
        "Obtain independent model, calibration, identity and executable sportsbook evidence before any edge designation.",
        "Require exact bookmaker ticket, settlement rules and defensible correlated joint probability.",
        "Enforce HOLD until every independent gate passes; retain $0 shadow stake.",
        "Audit GitHub logs, original pregame receipts, adjudication and provenance.",
    )
    roles = []
    for i, (name, labels) in enumerate(STAFF):
        roles.append({
            "employee": name,
            "status": statuses[i],
            "findings": findings[i],
            "next_action": actions[i],
            "workflow_evidence": workflow_evidence(report, labels),
        })
    return {
        "title": "Freddy's Picks AI V9 — Virtual Staff Command Center",
        "snapshot_created_at_utc": report.get("created_at_utc"),
        "repository": report.get("repository"),
        "six_roles": roles,
        "failed_or_cancelled_workflows": failures,
        "stale_successful_workflows": stale,
        "pending_workflows": pending,
        "certified_positive_ev_from_this_audit": 0,
        "verified_executable_draftkings_prices_from_this_audit": 0,
        "native_model_forecasts_authenticated_by_this_audit": 0,
        "model_release": "HOLD_UNVERIFIED",
        "champion_001_change_requested": False,
        "automated_wagers": 0,
        "paid_api_calls": 0,
        "shadow_stake_usd": 0,
        "scope_warning": "Six role-based automated audits, not six autonomous LLM accounts. GitHub workflow metadata alone cannot certify betting predictions or prices.",
    }


def markdown(board):
    lines = [
        "# Freddy's Picks AI V9 — Six Virtual Employees", "",
        f"Snapshot UTC: {board['snapshot_created_at_utc'] or 'unknown'}",
        "",
        "**Champion-001 frozen • Challenger isolated • HOLD on uncertified edges • $0 wagers and API credits.**",
        "",
        "| Virtual employee | Status | Next action |",
        "|---|---|---|",
    ]
    for role in board["six_roles"]:
        lines.append("| " + role["employee"] + " | " + role["status"] + " | " + role["next_action"] + " |")
    lines.extend(["", "## Operational exceptions",
        f"- Latest failed or cancelled workflows: {len(board['failed_or_cancelled_workflows'])}",
        f"- Stale successful workflow runs: {len(board['stale_successful_workflows'])}",
        f"- Pending or running workflows: {len(board['pending_workflows'])}",
        "- **Certified positive-EV bets from this audit: 0. This is not a new calibration or sportsbook quote check.**",
    ])
    for group, names in (("Failed/cancelled", board["failed_or_cancelled_workflows"]),
                         ("Stale", board["stale_successful_workflows"])):
        if names:
            lines.append(f"- {group}: " + ", ".join(names))
    for role in board["six_roles"]:
        lines.extend(["", f"## {role['employee']} — {role['status']}"])
        lines.extend("- " + item for item in role["findings"])
        lines.append("Workflow evidence (job status only):")
        for item in role["workflow_evidence"]:
            label = item["workflow"]
            url = item["latest_run_url"]
            label = f"[{label}]({url})" if url else label
            lines.append(f"- {label}: {item['latest_job_status']}")
    lines.extend(["", board["scope_warning"],
        "The existing all-sports ChatGPT scan already runs at 8:00 AM and 5:00 PM Eastern. This GitHub board reads the existing pipelines; it does not duplicate collection or guarantee GitHub scheduler timing.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", help="Existing PHONE_DASHBOARD.json to evaluate offline")
    parser.add_argument("--output-dir", default="v9_results")
    args = parser.parse_args(argv)
    if args.report_json:
        report = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    else:
        if not os.environ.get("GH_TOKEN"):
            parser.error("GH_TOKEN required for live GitHub metadata; use --report-json for offline replay")
        data = {path: github_json(f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{path}/runs?per_page=15")
                for path in WATCH.values()}
        b = github_json(f"repos/{os.environ['GITHUB_REPOSITORY']}/branches/main").get("protected")
        report = compose(data, b if type(b) is bool else None, [], datetime.now(timezone.utc))
    board = evaluate(report)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "V9_VIRTUAL_STAFF_BOARD.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    rendered = markdown(board)
    (output / "V9_VIRTUAL_STAFF_BOARD.md").write_text(rendered, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
    print(json.dumps({"six_roles": len(board["six_roles"]), "model_release": board["model_release"],
                      "wagers": board["automated_wagers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
