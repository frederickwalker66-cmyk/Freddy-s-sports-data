"""Conservative temporal audit of retained NBA odds captures.

A timestamp comparison is a candidate filter, never independent point-in-time
custody or DraftKings certification. Naive timestamps are rejected.
"""
from datetime import datetime, timezone
from research.challenger_002_nba_research_join import field

def parse_aware(value):
    if not isinstance(value,str) or not value.strip():
        return None
    try:
        dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo and dt.utcoffset() is not None else None
    except (ValueError,OverflowError):
        return None

def audit(scores,odds,scores_meta,odds_meta):
    out={"status":"RESEARCH_TEMPORAL_SCREEN_ONLY","matched_games":0,
         "missing_start_count":0,"naive_start_count":0,
         "invalid_start_count":0,"invalid_capture_count":0,
         "timestamp_before_start_candidates":0,"blocked_missing_or_ambiguous_time":0,
         "blocked_at_or_after_start":0,"blocked_identifier_conflict":0,
         "training_rows_approved":0,"certified_take_count":0,
         "independent_pregame_custody_verified":False,
         "draftkings_identity_verified":False}
    if not isinstance(scores,list) or not isinstance(odds,list) or not isinstance(scores_meta,dict) or not isinstance(odds_meta,dict):
        out["status"]="BLOCKED_INVALID_INPUT";return out
    if scores_meta.get("date")!=odds_meta.get("date") or scores_meta.get("kind")!="nba_scores" or odds_meta.get("kind")!="nba_odds":
        out["status"]="BLOCKED_METADATA";return out
    def unique(rows):
        found={};duplicates=set()
        for row in rows:
            gid=field(row,"GameID")
            if not isinstance(gid,(int,str)) or not str(gid).strip():continue
            key=str(gid)
            if key in found:duplicates.add(key)
            found[key]=row
        return {k:v for k,v in found.items() if k not in duplicates}
    s=unique(scores);o=unique(odds)
    captured=parse_aware(odds_meta.get("retrieved_at"))
    for gid in set(s)&set(o):
        sr=s[gid];orr=o[gid]
        sg=field(sr,"GlobalGameID");og=field(orr,"GlobalGameID")
        if sg is None or og is None or str(sg)!=str(og):
            out["blocked_identifier_conflict"]+=1;continue
        out["matched_games"]+=1
        # Scores DateTimeUTC is provider supplied; reject naive values rather
        # than guessing the local time zone or interpreting DateTime as UTC.
        start=parse_aware(field(sr,"DateTimeUTC"))
        if start is None or captured is None:
            out["blocked_missing_or_ambiguous_time"]+=1
            raw=field(sr,"DateTimeUTC")
            if raw is None or raw=="":
                out["missing_start_count"]+=1
            elif isinstance(raw,str) and parse_aware(raw+"Z") is not None:
                out["naive_start_count"]+=1
            else:
                out["invalid_start_count"]+=1
            if captured is None:
                out["invalid_capture_count"]+=1
        elif captured>=start:
            out["blocked_at_or_after_start"]+=1
        else:
            out["timestamp_before_start_candidates"]+=1
    return out
