"""Collect raw historical NBA Vault evidence with pinned provider transport.

Explicit endpoint URLs are required: historical subscription access alone does not
establish which endpoint and license is enabled. No retrospective as-of claims.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from research.trusted_provider_gateway import fetch_provider_json, SourceUnavailable

HOST = "api.sportsdata.io"

def collect(env=None, output=Path("challenger_results/nba_probability/vault")):
    env = os.environ if env is None else env
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    endpoints = {"games": "SPORTSDATAIO_NBA_HISTORY_GAMES_URL",
                 "odds": "SPORTSDATAIO_NBA_HISTORY_ODDS_URL"}
    status = {}
    for kind, variable in endpoints.items():
        url = env.get(variable, "").strip()
        key = (env.get("SPORTSDATAIO_ODDS_API_KEY") if kind == "odds" else
               env.get("SPORTSDATAIO_NBA_API_KEY")) or env.get("SPORTSDATAIO")
        if not url or not key:
            status[kind] = "HOLD_ENDPOINT_OR_KEY_NOT_CONFIGURED"
            continue
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != HOST or parsed.query or parsed.fragment or parsed.username or parsed.password:
            status[kind] = "HOLD_INVALID_PINNED_ENDPOINT"
            continue
        try:
            response = fetch_provider_json(url, api_key=key, allowed_host=HOST, max_bytes=12_000_000)
            payload = response["payload"]
            if not isinstance(payload, list):
                status[kind] = "HOLD_UNEXPECTED_SCHEMA"
                continue
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            (output / (kind + "_raw.json")).write_bytes(raw)
            (output / (kind + "_manifest.json")).write_text(json.dumps({
                "provider": "SportsDataIO", "endpoint_path": parsed.path,
                "retrieved_at": response["retrieved_at"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "records": len(payload), "archived_pregame_snapshot_proven": False,
                "independently_verified": False}, indent=2) + "\n")
            status[kind] = "RAW_HISTORICAL_RESPONSE_QUARANTINED"
        except (SourceUnavailable, ValueError, TypeError):
            status[kind] = "HOLD_PROVIDER_ERROR"
    report = {"endpoints": status, "qualified_training_records": 0,
              "certified_predictions": 0,
              "note": "Raw historical records require point-in-time feature construction and independent outcome review."}
    (output / "collector_status.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="challenger_results/nba_probability/vault")
    args = parser.parse_args()
    collect(output=Path(args.output))
