"""Read-only SharpAPI market value quality audit; prints aggregates, never raw records."""
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from sharpapi_mapping import assess_sharpapi_row

URL = "https://api.sharpapi.io/api/v1/odds?sportsbook=draftkings&league=nba&is_live=false&limit=5"

def main():
    key = os.environ.get("SHARP_API_KEY")
    if not key:
        raise SystemExit("HOLD: missing SHARP_API_KEY")
    req = urllib.request.Request(URL, headers={"X-API-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HOLD: provider HTTP {exc.code}")
    except (OSError, ValueError, TimeoutError):
        raise SystemExit("HOLD: provider response unavailable")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SystemExit("HOLD: unexpected provider envelope")
    rows = payload["data"]
    counts = Counter()
    now = datetime.now(timezone.utc)
    for row in rows:
        outcome = assess_sharpapi_row(row, now=now)
        counts[outcome["data_quality"]] += 1
        for reason in outcome["reasons"]:
            counts["reason:" + reason] += 1
    print("Records audited:", len(rows))
    print("Research data-quality PASS:", counts["PASS"])
    print("Research data-quality HOLD:", counts["HOLD"])
    for label, count in sorted(counts.items()):
        if label.startswith("reason:"):
            print(label, count)
    print("No raw odds, IDs, team names, or secrets emitted.")
    print("Certified TAKE predictions: 0 (HOLD)")
    if not rows:
        raise SystemExit("HOLD: no records to audit")

if __name__ == "__main__":
    main()
