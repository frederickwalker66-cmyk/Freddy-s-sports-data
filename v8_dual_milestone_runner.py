"""Run both V8 research milestones against genuine supplied archived evidence.

Never creates a fake input row. Reuses the repository's NBA and seven-league
native research trainers; all model artifacts remain unverified research-only.
Evidence-file presence and self-reported review flags are NOT independent proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from challenger_nba_probability import train_engine as train_nba
from challenger_multisport_native_training import train as train_other_sports
from v8_milestone_tracker import LEAGUES, build_report


def load_jsonl(path):
    if path is None:
        return [], False
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()], True


def run(nba_rows, other_rows, nba_present=False, other_present=False, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    nba_report, nba_model = train_nba(nba_rows, as_of=now)
    other_report, other_models = train_other_sports(other_rows, now=now)
    audit = build_report()
    reports = {
        "report_version": "v8-research-both-milestones-v1",
        "created_utc": now.astimezone(timezone.utc).isoformat(),
        "nba_evidence_file_present": bool(nba_present),
        "other_sport_evidence_file_present": bool(other_present),
        "milestone_a_nba": {
            "status": nba_report["result"],
            "review_attested_games": nba_report["rows_review_attested_and_settled"],
            "research_model_fitted": nba_model is not None,
            "independently_complete": False,
        },
        "milestone_b_all_eight": {
            "research_models_fitted": (["nba"] if nba_model is not None else [])
                + sorted(other_models),
            "by_league": {
                league: (nba_report if league == "nba"
                         else other_report["by_league"].get(league, {}))
                for league in LEAGUES
            },
            "independently_complete": False,
        },
        "formal_milestone_gate": audit,
        "certified_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "bet_ready": False,
        "champion_001_modified": False,
        "warning": "Models generated from claims are research-only; independently audit raw pregame input provenance, numerical integrity, settlement and executable sportsbook prices before certification.",
    }
    return reports, nba_model, other_models


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nba-history", help="NBA separately reviewed original pregame evidence JSONL")
    p.add_argument("--other-history", help="Seven other leagues reviewed original pregame evidence JSONL")
    p.add_argument("--output-dir", default="v8_results/dual_milestone")
    args = p.parse_args(argv)
    nba_rows, nba_present = load_jsonl(args.nba_history)
    other_rows, other_present = load_jsonl(args.other_history)
    report, nba_model, other_models = run(nba_rows, other_rows, nba_present, other_present)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "research_milestone_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if nba_model is not None:
        (dest / "nba_unverified_research_model.json").write_text(
            json.dumps(nba_model, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for league, model in other_models.items():
        (dest / (league + "_unverified_research_model.json")).write_text(
            json.dumps(model, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "nba_status": report["milestone_a_nba"]["status"],
        "research_models": report["milestone_b_all_eight"]["research_models_fitted"],
        "certified_predictions": 0,
        "report": str(dest / "research_milestone_report.json"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
