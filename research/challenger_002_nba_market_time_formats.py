"""Non-certifying timestamp-format census for SportsDataIO NBA market records."""
from collections import Counter
from datetime import datetime
from research.challenger_002_nba_research_join import field
from research.challenger_002_nba_temporal_audit import parse_aware

def classify(value):
    if value is None:return "missing"
    if not isinstance(value,str):return "non_string"
    if parse_aware(value) is not None:return "timezone_aware"
    try:
        dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        if dt.tzinfo is None:return "timezone_naive"
    except (ValueError,OverflowError):pass
    return "invalid_format"

def census(rows):
    out={"status":"RESEARCH_MARKET_TIME_FORMAT_ONLY","market_rows":0,
         "created_formats":{},"updated_formats":{},
         "verified_pregame_market_rows":0,"certified_take_count":0}
    if not isinstance(rows,list):
        out["status"]="BLOCKED_INVALID_INPUT";return out
    created=Counter();updated=Counter()
    for game in rows:
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            out["market_rows"]+=1
            created[classify(field(market,"Created"))]+=1
            updated[classify(field(market,"Updated"))]+=1
    out["created_formats"]=dict(sorted(created.items()))
    out["updated_formats"]=dict(sorted(updated.items()))
    return out
