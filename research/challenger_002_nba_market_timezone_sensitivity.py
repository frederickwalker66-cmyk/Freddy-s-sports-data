"""Non-certifying NBA market timestamp timezone sensitivity audit."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from research.challenger_002_nba_research_join import field
from research.challenger_002_nba_temporal_audit import parse_aware
ZONES=("America/New_York","America/Chicago","America/Denver","America/Los_Angeles")

def audit(odds,meta):
    out={"status":"RESEARCH_MARKET_TIME_SENSITIVITY_ONLY","market_rows":0,
         "created_before_capture_all_zones":0,"updated_before_capture_all_zones":0,
         "created_after_capture_all_zones":0,"updated_after_capture_all_zones":0,
         "created_timezone_dependent":0,"updated_timezone_dependent":0,
         "created_unassessable":0,"updated_unassessable":0,
         "provider_timezone_verified":False,"certified_take_count":0,
         "training_rows_approved":0}
    if not isinstance(odds,list) or not isinstance(meta,dict):
        out["status"]="BLOCKED_INPUT";return out
    capture=parse_aware(meta.get("retrieved_at"))
    if capture is None:
        out["status"]="BLOCKED_CAPTURE_TIMESTAMP";return out
    for game in odds:
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            out["market_rows"]+=1
            for name,prefix in (("Created","created"),("Updated","updated")):
                raw=field(market,name)
                if not isinstance(raw,str):
                    out[prefix+"_unassessable"]+=1;continue
                try:dt=datetime.fromisoformat(raw.strip().replace("Z","+00:00"))
                except ValueError:
                    out[prefix+"_unassessable"]+=1;continue
                if dt.tzinfo is not None:
                    out[prefix+"_unassessable"]+=1;continue
                comparisons=[dt.replace(tzinfo=ZoneInfo(z)).astimezone(timezone.utc)<capture for z in ZONES]
                if all(comparisons):out[prefix+"_before_capture_all_zones"]+=1
                elif not any(comparisons):out[prefix+"_after_capture_all_zones"]+=1
                else:out[prefix+"_timezone_dependent"]+=1
    return out
