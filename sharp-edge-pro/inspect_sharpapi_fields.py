"""Inspect API response FIELD NAMES ONLY; never print odds, teams, IDs or credentials."""
import json
import os
import re
import urllib.error
import urllib.request

URL = "https://api.sharpapi.io/api/v1/odds?sportsbook=draftkings&league=nba&is_live=false&limit=5"
SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

def fields(value):
    if not isinstance(value, dict):
        return ["<non-object>"]
    return sorted(k for k in value if SAFE_KEY.fullmatch(k))[:50]

def main():
    key = os.getenv("SHARP_API_KEY")
    if not key:
        raise SystemExit("HOLD: missing secret")
    request = urllib.request.Request(URL, headers={"X-API-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HOLD: provider HTTP {exc.code}")
    except (OSError, ValueError, TimeoutError):
        raise SystemExit("HOLD: provider response unavailable")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SystemExit("HOLD: unexpected response envelope")
    rows = payload["data"]
    print("Envelope field names:", fields(payload))
    print("Records returned:", len(rows))
    if not rows:
        raise SystemExit("HOLD: no records to inspect")
    first = rows[0]
    print("First record field names:", fields(first))
    if isinstance(first, dict):
        for name in fields(first):
            child = first[name]
            if isinstance(child, dict):
                print(f"Nested object {name} field names:", fields(child))
            elif isinstance(child, list):
                print(f"Nested list {name}: present (contents withheld)")
    print("No raw values were printed. Field names alone do not establish mapping semantics.")
    print("Certification: HOLD")

if __name__ == "__main__":
    main()
