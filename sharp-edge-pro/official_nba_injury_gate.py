"""Fail-closed official NBA injury-report evidence gate.

Accepts only manually reviewed, structured official-report entries with
explicit source URL, publication timestamp, game date, player identifier,
and availability. Does not fetch or infer official injury reports.
"""
from datetime import datetime, timezone

def aware(value):
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def check(record, *, expected_player_id, expected_game_date, as_of):
    if not isinstance(record,dict):
        return "HOLD_NO_OFFICIAL_REPORT_EVIDENCE"
    if record.get("source")!="NBA_OFFICIAL_INJURY_REPORT":
        return "HOLD_UNTRUSTED_REPORT_SOURCE"
    url=record.get("source_url","")
    if not isinstance(url,str) or not url.startswith("https://ak-static.cms.nba.com/"):
        return "HOLD_UNVERIFIED_SOURCE_URL"
    if str(record.get("player_id") or "")!=str(expected_player_id):
        return "HOLD_PLAYER_ID_NOT_VERIFIED"
    if record.get("game_date")!=expected_game_date:
        return "HOLD_GAME_DATE_MISMATCH"
    published=aware(record.get("published_at"))
    now=aware(as_of)
    if not published or not now or published>now:
        return "HOLD_INVALID_REPORT_TIMESTAMP"
    if (now-published).total_seconds()>6*3600:
        return "HOLD_REPORT_STALE"
    status=record.get("status")
    if status in ("Out","Doubtful","Questionable","Probable"):
        return "HOLD_OFFICIAL_STATUS_"+status.upper()
    if status not in ("Available","Not Listed"):
        return "HOLD_OFFICIAL_STATUS_UNKNOWN"
    # A published report may be incomplete or superseded. No automatic clearance.
    return "HOLD_REPORT_EVIDENCE_REQUIRES_FINAL_LINEUP_CHECK"

def summary(records):
    return {"evidence_count":len(records),"certified_take":0,"decision":"HOLD"}
