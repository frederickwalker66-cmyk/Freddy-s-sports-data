"""Research-only candidate matching of SharpAPI names to SportsDataIO player rows.

A unique exact name is a *candidate*, not a verified cross-provider identity.
Never promote this output to verified roster, eligibility or certified TAKE.
"""
import re
import unicodedata
from collections import defaultdict

def canonical(value):
    if not isinstance(value,str):
        return ""
    value=unicodedata.normalize("NFKC",value).casefold()
    return " ".join(re.sub(r"[^\w\s]"," ",value).split())

def candidate_index(players):
    index=defaultdict(list)
    if not isinstance(players,list):
        return index
    for row in players:
        if not isinstance(row,dict):
            continue
        names={canonical(row.get("DraftKingsName")),
               canonical(" ".join(str(row.get(k) or "") for k in ("FirstName","LastName")))}
        for name in names - {""}:
            index[name].append(row)
    return index

def assess_candidate(market,index):
    if not isinstance(market,dict) or market.get("is_player_prop") is not True:
        return {"status":"HOLD","reason":"not_a_verified_player_prop"}
    name=canonical(market.get("player_name"))
    if not name:
        return {"status":"HOLD","reason":"missing_player_name"}
    candidates=index.get(name,[])
    if len(candidates)!=1:
        return {"status":"HOLD","reason":"ambiguous_or_missing_name_match","candidate_count":len(candidates)}
    row=candidates[0]
    if not row.get("PlayerID") or not row.get("TeamID"):
        return {"status":"HOLD","reason":"provider_identity_fields_missing"}
    return {"status":"CANDIDATE_ONLY","reason":"independent_event_team_and_identity_crosscheck_required",
            "candidate_count":1}

def summary(markets,players):
    index=candidate_index(players)
    counts={"candidate_only":0,"hold":0}
    for market in markets:
        result=assess_candidate(market,index)
        counts["candidate_only" if result["status"]=="CANDIDATE_ONLY" else "hold"]+=1
    return {"market_count":len(markets),"results":counts,"certified_take":0,"decision":"HOLD"}
