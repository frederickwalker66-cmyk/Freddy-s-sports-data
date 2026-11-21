"""Authenticated NBA SportsDataIO research snapshot intake.

Captures an API response via the existing trusted gateway and saves a
canonical JSON snapshot with a SHA256 digest. This is NOT a historical
pregame receipt when fetched after the event, nor proof of DraftKings identity.
Never logs API keys or emits certified predictions.
"""
import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from research.trusted_provider_gateway import SourceUnavailable, fetch_provider_json
from research.challenger_002_pregame_gate import inspect_pregame_snapshot

HOST = "api.sportsdata.io"
PATHS = {
    "nba_scores": "/v3/nba/scores/json/GamesByDate/{date}",
    "nba_odds": "/v3/nba/odds/json/GameOddsByDate/{date}",
}

def capture(day, kind, output_dir, *, env=None, fetch=fetch_provider_json):
    env = os.environ if env is None else env
    if date.fromisoformat(day).isoformat() != day or kind not in PATHS:
        raise ValueError("invalid_date_or_kind")
    key = (env.get("SPORTSDATAIO_ODDS_API_KEY") or env.get("SPORTSDATAIO")
           if kind == "nba_odds" else env.get("SPORTSDATAIO_NBA_API_KEY") or env.get("SPORTSDATAIO"))
    report = {"provider":"SportsDataIO", "kind":kind, "date":day,
              "status":"BLOCKED", "certified_take_count":0,
              "point_in_time_provenance_verified":False}
    if not key:
        report["reason"] = "API_KEY_NOT_CONFIGURED"
        return report
    url = "https://" + HOST + PATHS[kind].replace("{date}", day)
    try:
        response = fetch(url, api_key=key, allowed_host=HOST)
        payload = response["payload"]
        retrieved_at = response["retrieved_at"]
        if not isinstance(payload, list):
            raise ValueError("unexpected_payload_schema")
        # Canonicalized JSON, not the provider's original byte-for-byte HTTP body.
        canonical = json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        filename = kind + "_" + day + "_" + digest[:16] + ".json"
        path = directory / filename
        path.write_bytes(canonical)
        pregame = inspect_pregame_snapshot(payload, retrieved_at) if kind == "nba_scores" else {"status":"NOT_ASSESSED_FOR_ODDS_NESTED_SCHEMA","certified_take_count":0}
        report.update(pregame_candidate_assessment=pregame)
        report.update(status="AUTHENTICATED_SNAPSHOT_RESEARCH_ONLY",
                      retrieved_at=retrieved_at, record_count=len(payload),
                      canonical_payload_sha256=digest, snapshot_path=str(path),
                      raw_http_body_preserved=False,
                      historical_pregame_availability_verified=False,
                      draftkings_identity_verified=False)
    except (SourceUnavailable, ValueError, TypeError, KeyError) as exc:
        report["reason"] = type(exc).__name__
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--kind", choices=sorted(PATHS), required=True)
    p.add_argument("--output-dir", default="artifacts/challenger_002_snapshots")
    p.add_argument("--report", default="artifacts/challenger_002_intake_report.json")
    args = p.parse_args()
    result = capture(args.date,args.kind,args.output_dir)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k != "snapshot_path"}))
    if result["status"] == "BLOCKED":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
