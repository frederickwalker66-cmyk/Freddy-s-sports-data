"""Read-only SharpAPI odds response validation. No credentials or raw odds logged."""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://api.sharpapi.io/api/v1/odds?sportsbook=draftkings&league=nba&is_live=false&limit=5"

def main():
    key = os.getenv("SHARP_API_KEY")
    if not key:
        print("HOLD: SHARP_API_KEY not configured")
        return 2
    request = urllib.request.Request(URL, headers={"X-API-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"HOLD: HTTP {exc.code}; credentials and response withheld")
        return 1
    except (ValueError, OSError, TimeoutError) as exc:
        print(f"HOLD: response unavailable ({type(exc).__name__})")
        return 1
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        print("HOLD: expected top-level data list is absent")
        return 1
    rows = payload["data"]
    print(f"HTTP status: {status}")
    print(f"NBA DraftKings pregame sample rows: {len(rows)}")
    if not rows:
        print("HOLD: no records returned")
        return 1
    print("Schema: top-level data list verified")
    print("Market IDs, sportsbook provenance, line timestamps, roster and injury data: NOT VALIDATED")
    print("Model probabilities and positive EV: NOT CERTIFIED")
    print("Decision: HOLD (research-only)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
