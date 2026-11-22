"""Live, read-only NBA candidate matching; prints aggregate counts only.

Matching a name does not establish verified identity, team, event, injury status,
provider authenticity or certified model probability.
"""
import json
import os
import urllib.error
import urllib.request
from nba_name_candidates import summary

SHARP_URL="https://api.sharpapi.io/api/v1/odds?sportsbook=draftkings&league=nba&is_live=false&limit=5"
ROSTER_URL="https://api.sportsdata.io/v3/nba/scores/json/Players"

def retrieve(url, header, key):
    req=urllib.request.Request(url,headers={header:key,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        return json.load(resp)

def main():
    sharp_key=os.getenv("SHARP_API_KEY")
    nba_key=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp_key or not nba_key:
        raise SystemExit("HOLD: one or more provider credentials missing")
    try:
        sharp=retrieve(SHARP_URL,"X-API-Key",sharp_key)
        roster=retrieve(ROSTER_URL,"Ocp-Apim-Subscription-Key",nba_key)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HOLD: provider HTTP {exc.code}")
    except (OSError,ValueError,TimeoutError):
        raise SystemExit("HOLD: provider transport or JSON error")
    if not isinstance(sharp,dict) or not isinstance(sharp.get("data"),list) or not isinstance(roster,list):
        raise SystemExit("HOLD: unexpected provider schema")
    markets=[m for m in sharp["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
    result=summary(markets,roster)
    print("SharpAPI sample records:",len(sharp["data"]))
    print("Player props sampled:",result["market_count"])
    print("SportsDataIO roster rows:",len(roster))
    print("Unique name-match candidates (unverified):",result["results"]["candidate_only"])
    print("Missing or ambiguous candidates (HOLD):",result["results"]["hold"])
    print("Player ID cross-provider verification: HOLD")
    print("Roster, injury and event eligibility: HOLD")
    print("Certified TAKE predictions: 0 (HOLD)")

if __name__=="__main__":
    main()
