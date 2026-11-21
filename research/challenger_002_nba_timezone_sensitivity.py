"""Timezone sensitivity screen for naive SportsDataIO NBA start timestamps.

This is NOT provider timezone verification. It tests several possible
interpretations, and never approves training or certified predictions.
"""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from research.challenger_002_nba_temporal_audit import parse_aware
from research.challenger_002_nba_research_join import field

ZONES=("America/New_York","America/Chicago","America/Denver","America/Los_Angeles")

def analyze(scores,odds,scores_meta,odds_meta):
    out={"status":"RESEARCH_TIMEZONE_SENSITIVITY_ONLY",
         "zones_considered":list(ZONES),"matched_games":0,
         "robust_before_start_across_all_zones":0,
         "robust_at_or_after_start_across_all_zones":0,
         "timezone_dependent":0,"unassessable":0,
         "training_rows_approved":0,"certified_take_count":0,
         "provider_timezone_confirmed":False}
    if not isinstance(scores,list) or not isinstance(odds,list) or not isinstance(scores_meta,dict) or not isinstance(odds_meta,dict):
        out["status"]="BLOCKED_INPUT";return out
    if scores_meta.get("date")!=odds_meta.get("date") or scores_meta.get("kind")!="nba_scores" or odds_meta.get("kind")!="nba_odds":
        out["status"]="BLOCKED_METADATA";return out
    def unique(rows):
        found={};duplicates=set()
        for r in rows:
            gid=field(r,"GameID")
            if not isinstance(gid,(int,str)):continue
            k=str(gid)
            if k in found:duplicates.add(k)
            found[k]=r
        return {k:v for k,v in found.items() if k not in duplicates}
    a=unique(scores);b=unique(odds)
    capture=parse_aware(odds_meta.get("retrieved_at"))
    for gid in set(a)&set(b):
        sg=field(a[gid],"GlobalGameID");og=field(b[gid],"GlobalGameID")
        if sg is None or og is None or str(sg)!=str(og):
            continue
        out["matched_games"]+=1
        raw=field(a[gid],"DateTimeUTC")
        if not isinstance(raw,str) or capture is None:
            out["unassessable"]+=1;continue
        try:
            dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        except ValueError:
            out["unassessable"]+=1;continue
        if dt.tzinfo is not None:
            out["unassessable"]+=1;continue
        before=[capture<dt.replace(tzinfo=ZoneInfo(z)).astimezone(timezone.utc) for z in ZONES]
        if all(before):
            out["robust_before_start_across_all_zones"]+=1
        elif not any(before):
            out["robust_at_or_after_start_across_all_zones"]+=1
        else:
            out["timezone_dependent"]+=1
    return out
