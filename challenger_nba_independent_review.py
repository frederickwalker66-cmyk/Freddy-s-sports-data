"""NBA evidence certification review. Fail closed; does not train or modify Champion-001.

Consumes independently reviewed evidence assertions. An assertion alone is not proof:
human/source auditing and independently retained source artifacts are required.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

def instant(s):
    if not isinstance(s, str):
        raise ValueError("missing_timestamp")
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive_timestamp")
    return d.astimezone(timezone.utc)

def host(url):
    if not isinstance(url, str):
        raise ValueError("missing_source_url")
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("invalid_source_url")
    return p.hostname.lower()

def review(row):
    if not isinstance(row, dict) or row.get("league") != "nba":
        raise ValueError("not_nba_evidence")
    if row.get("champion_001_modified") is not False:
        raise ValueError("champion_safety_flag_missing")
    if row.get("certified_prediction") is not False or row.get("bet_ready") is not False:
        raise ValueError("research_quarantine_flag_missing")
    event_id = str(row.get("event_id", ""))
    if not event_id.isdigit():
        raise ValueError("invalid_event_id")
    captured, start, outcome = (instant(row[k]) for k in
        ("snapshot_completed_at_utc", "start_utc", "outcome_observed_at_utc"))
    if not captured < start < outcome:
        raise ValueError("not_point_in_time")
    checks = row.get("independent_checks")
    if not isinstance(checks, dict):
        raise ValueError("independent_checks_missing")
    required = ("schedule", "pregame_features", "final_outcome")
    for kind in required:
        check = checks.get(kind)
        if not isinstance(check, dict) or check.get("reviewer_verified") is not True:
            raise ValueError(kind + "_not_reviewed")
        sources = check.get("sources")
        if not isinstance(sources, list) or len(sources) < 2:
            raise ValueError(kind + "_insufficient_sources")
        providers = set()
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError(kind + "_invalid_source")
            providers.add(source.get("origin_provider"))
            host(source.get("url"))
            observed = instant(source.get("observed_at_utc"))
            if kind != "final_outcome" and observed > captured:
                raise ValueError(kind + "_late_source")
            if kind == "final_outcome" and observed <= start:
                raise ValueError("outcome_not_postgame")
            digest = source.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(kind + "_missing_source_digest")
        if None in providers or len(providers) < 2:
            raise ValueError(kind + "_not_distinct_origins")
        if check.get("upstream_independence_verified") is not True:
            raise ValueError(kind + "_independence_unproven")
        if check.get("values_agree") is not True:
            raise ValueError(kind + "_source_disagreement")
    return (event_id, captured.isoformat())

def assess(rows):
    outcomes = []
    rejected = Counter()
    seen = Counter(str(r.get("event_id", "")) for r in rows if isinstance(r, dict))
    for row in rows:
        try:
            key = str(row.get("event_id", ""))
            if seen[key] != 1:
                raise ValueError("duplicate_event_quarantined")
            event_id, captured = review(row)
            outcomes.append({"event_id": event_id, "snapshot_completed_at_utc": captured,
                             "status": "reviewed_candidate_not_certified"})
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            rejected[str(exc)] += 1
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "league": "nba",
        "reviewed_candidates": len(outcomes),
        "rejected_records": sum(rejected.values()),
        "rejection_reasons": dict(sorted(rejected.items())),
        "candidates": outcomes,
        "qualified_training_examples": 0,
        "certified_predictions": 0,
        "bet_ready_selections": 0,
        "champion_001_modified": False,
        "note": "Source assertions and hashes require external audit; no automated promotion to training."
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="nba_independent_evidence.jsonl")
    p.add_argument("--output", default="challenger_results/nba_independent_review.json")
    a = p.parse_args()
    path = Path(a.input)
    rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []
    report = assess(rows)
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k!="candidates"}, sort_keys=True))

if __name__ == "__main__":
    main()
