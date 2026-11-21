"""Research-only temporal screen of individual pregame odds rows.

Naive market timestamps cannot establish pregame availability. A provider
market timestamp is not independent custody even if it predates tipoff.
"""
from collections import Counter
from research.challenger_002_nba_temporal_audit import parse_aware
from research.challenger_002_nba_research_join import field

def audit(scores,odds,odds_meta):
    out={"status":"RESEARCH_MARKET_TIME_SCREEN_ONLY","market_rows":0,
         "missing_created":0,"missing_updated":0,"ambiguous_created":0,
         "ambiguous_updated":0,"created_after_capture":0,"updated_after_capture":0,
         "chronology_conflicts":0,"capture_time_invalid":False,
         "verified_pregame_market_rows":0,"certified_take_count":0,
         "independent_market_custody_verified":False}
    if not isinstance(scores,list) or not isinstance(odds,list) or not isinstance(odds_meta,dict):
        out["status"]="BLOCKED_INPUT";return out
    capture=parse_aware(odds_meta.get("retrieved_at"))
    if capture is None:
        out["capture_time_invalid"]=True
        out["status"]="BLOCKED_CAPTURE_TIMESTAMP"
        return out
    for game in odds:
        if not isinstance(game,dict):continue
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for m in markets:
            if not isinstance(m,dict):continue
            out["market_rows"]+=1
            raw_c=field(m,"Created");raw_u=field(m,"Updated")
            if raw_c is None:out["missing_created"]+=1
            if raw_u is None:out["missing_updated"]+=1
            created=parse_aware(raw_c);updated=parse_aware(raw_u)
            if raw_c is not None and created is None:out["ambiguous_created"]+=1
            if raw_u is not None and updated is None:out["ambiguous_updated"]+=1
            if created and created>capture:out["created_after_capture"]+=1
            if updated and updated>capture:out["updated_after_capture"]+=1
            if created and updated and updated<created:out["chronology_conflicts"]+=1
    return out
