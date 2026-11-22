"""Fail-closed schema-only NBA player/event reconciliation preflight.

This script intentionally does not infer cross-provider IDs from player names.
It reports field names and counts, not licensed values or personal credentials.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

def fetch(url, key, header):
    request = urllib.request.Request(url, headers={header:key,"Accept":"application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

def shape(payload):
    if not isinstance(payload, list):
        return {"schema":"unexpected","records":0,"fields":[]}
    row = next((x for x in payload if isinstance(x,dict)),{})
    return {"schema":"list","records":len(payload),"fields":sorted(row)[:80]}

def main():
    key=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not key:
        raise SystemExit("HOLD: NBA provider credential missing")
    endpoints={
        "players":"https://api.sportsdata.io/v3/nba/scores/json/Players",
        "injured_players":"https://api.sportsdata.io/v3/nba/projections/json/InjuredPlayers"
    }
    for name,url in endpoints.items():
        try:
            result=shape(fetch(url,key,"Ocp-Apim-Subscription-Key"))
            print(json.dumps({"feed":name,**result},sort_keys=True))
        except Exception as exc:
            print(json.dumps({"feed":name,"status":"HOLD","error_type":type(exc).__name__}))
    print("Cross-provider player-ID mapping: HOLD; no identity inferred from names")
    print("Certified TAKE: 0 — HOLD")

if __name__=="__main__":
    main()
