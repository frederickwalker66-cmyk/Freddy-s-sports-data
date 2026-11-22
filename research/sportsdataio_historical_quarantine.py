"""Manually capture SportsDataIO original historical-response bytes in quarantine.

A successful HTTPS/API-key response does NOT prove historical entitlement,
original publication timestamp, licensed real scores/odds, or settlement.
Never promote the output to Challenger training or certified TAKE.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

HOST = "api.sportsdata.io"
ENDPOINT = "https://api.sportsdata.io/v3/nba/odds/json/GameOddsByDate/{date}"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect_blocked")

def capture(day, key, root, *, opener=None):
    date.fromisoformat(day)
    if date.fromisoformat(day).isoformat() != day or not key:
        raise ValueError("invalid_date_or_missing_key")
    url = ENDPOINT.replace("{date}", day)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST:
        raise ValueError("untrusted_provider_host")
    request = Request(url, headers={"Ocp-Apim-Subscription-Key": key,
        "Accept": "application/json", "User-Agent": "FreddysPicksHistoricalQuarantine/1"})
    opener = opener or build_opener(NoRedirect())
    response = opener.open(request, timeout=15)
    with response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("oversized_provider_response")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("unexpected_provider_schema")
    captured = datetime.now(timezone.utc).isoformat()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("unsafe_quarantine_directory")
    filename = "sportsdataio_nba_gameodds_" + day + ".json"
    dest = root / filename
    if dest.exists() or dest.is_symlink():
        raise ValueError("refuse_overwrite_original_bytes")
    dest.write_bytes(raw)
    report = {
        "provider": "SportsDataIO", "endpoint": "nba/odds/GameOddsByDate",
        "historical_query_date": day, "capture_received_at_utc": captured,
        "original_response_path": filename, "original_response_sha256": hashlib.sha256(raw).hexdigest(),
        "original_response_bytes": len(raw), "record_count": len(data),
        "https_api_key_response_received": True,
        "historical_entitlement_independently_verified": False,
        "historical_publication_timestamp_verified": False,
        "source_signature_verified": False, "original_pregame_custody_verified": False,
        "draftkings_historical_market_reconciled": False,
        "independent_official_outcome_reconciled": False,
        "bookmaker_settlement_reconciled": False,
        "pr255_signed_receipt_reconciliation_passed": False,
        "qualified_training_rows": 0, "certified_take_predictions": 0,
        "status": "HOLD_PROVIDER_RESPONSE_QUARANTINED",
        "blocking_reasons": ["provider_account_historical_entitlement_unverified",
          "response_capture_time_not_historical_publication_time",
          "independent_source_signature_or_custody_missing",
          "bookmaker_prices_market_rules_and_settlement_not_reconciled",
          "official_outcome_not_independently_verified",
          "pr255_signed_receipt_bundle_not_available"]
    }
    (root / ("sportsdataio_nba_gameodds_" + day + ".receipt.json")).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--output-dir", default="historical_quarantine")
    a = p.parse_args()
    key = os.environ.get("SPORTSDATAIO_ODDS_API_KEY") or os.environ.get("SPORTSDATAIO")
    if not key:
        raise SystemExit("HOLD: historical provider key not configured")
    try:
        report = capture(a.date, key, a.output_dir)
    except (ValueError, OSError, URLError, HTTPError) as exc:
        raise SystemExit("HOLD: provider response not archived (" + type(exc).__name__ + ")")
    print(json.dumps({k: report[k] for k in (
        "provider", "historical_query_date", "record_count", "status",
        "qualified_training_rows", "certified_take_predictions")}))

if __name__ == "__main__":
    main()
