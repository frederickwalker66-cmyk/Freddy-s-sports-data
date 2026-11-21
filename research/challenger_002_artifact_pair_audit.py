"""Offline integrity and temporal audit for paired NBA snapshot artifacts.

Accepts extracted canonical JSON files and their intake metadata reports.
A matching game/date is not evidence of pregame market availability or
DraftKings identity. This module never authorizes a certified prediction.
"""
import argparse
import hashlib
import json
from pathlib import Path

def audit_pair(scores_bytes, odds_bytes, scores_report, odds_report):
    blockers=[]
    for label, raw, report, expected in (
        ("scores",scores_bytes,scores_report,"nba_scores"),
        ("odds",odds_bytes,odds_report,"nba_odds"),
    ):
        if not isinstance(report,dict) or report.get("kind") != expected:
            blockers.append(label.upper()+"_METADATA_MISMATCH")
            continue
        if hashlib.sha256(raw).hexdigest() != report.get("canonical_payload_sha256"):
            blockers.append(label.upper()+"_DIGEST_MISMATCH")
        if report.get("status") != "AUTHENTICATED_SNAPSHOT_RESEARCH_ONLY":
            blockers.append(label.upper()+"_CAPTURE_NOT_SUCCESSFUL")
        try:
            rows=json.loads(raw)
            if not isinstance(rows,list): raise ValueError()
        except (ValueError,TypeError):
            blockers.append(label.upper()+"_INVALID_JSON_ARRAY")
    if scores_report.get("date") != odds_report.get("date"):
        blockers.append("DIFFERENT_GAME_DATES")
    for label,report in (("SCORES",scores_report),("ODDS",odds_report)):
        if not report.get("retrieved_at"):
            blockers.append(label+"_RETRIEVAL_TIMESTAMP_MISSING")
    # The API endpoint's date and collection time cannot prove a market was
    # offered before tipoff; no historical inference is made from these alone.
    blockers.extend(["INDEPENDENT_POINT_IN_TIME_CUSTODY_NOT_VERIFIED",
                     "DRAFTKINGS_PRICE_IDENTITY_NOT_VERIFIED",
                     "GAME_OUTCOME_JOIN_NOT_VALIDATED"])
    return {"status":"BLOCKED","research_only":True,
            "game_date":scores_report.get("date"),
            "digest_integrity_passed":not any("DIGEST_MISMATCH" in b for b in blockers),
            "blockers":sorted(set(blockers)),"certified_take_count":0}

def main():
    p=argparse.ArgumentParser()
    for name in ("scores","odds","scores-report","odds-report","output"):
        p.add_argument("--"+name,required=True)
    args=p.parse_args()
    result=audit_pair(Path(args.scores).read_bytes(),Path(args.odds).read_bytes(),
                      json.loads(Path(args.scores_report).read_text()),
                      json.loads(Path(args.odds_report).read_text()))
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":
    main()
