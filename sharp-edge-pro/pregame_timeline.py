"""Pregame release timeline for every sport: readiness is evidence-based, never time-based."""
from datetime import datetime, timezone, timedelta

CHECKPOINTS=((120,"INITIAL_SCAN"),(60,"ROSTER_INJURY_RECHECK"),(30,"ODDS_MODEL_RECHECK"),(15,"FINAL_PREGAME_GATE"),(5,"LAST_PRICE_CHECK"))
REQUIRED=("schedule_verified","roster_verified","injury_verified","market_verified","model_validated","shadow_validated","price_executable")

def parse_utc(s):
    t=datetime.fromisoformat(s.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("Timezone required")
    return t.astimezone(timezone.utc)

def timeline(event_start,now=None,gates=None):
    start=parse_utc(event_start)
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Timezone required")
    now=now.astimezone(timezone.utc)
    gates=gates or {}
    missing=[x for x in REQUIRED if gates.get(x) is not True]
    checkpoints=[]
    for minutes,name in CHECKPOINTS:
        at=start-timedelta(minutes=minutes)
        checkpoints.append({"name":name,"scheduled_at_utc":at.isoformat(),"state":"UPCOMING" if now<at else "DUE_OR_PAST"})
    state="CLOSED" if now>=start else ("HOLD" if missing else "READY_FOR_FINAL_PRICE_CONFIRMATION")
    return {"event_start_utc":start.isoformat(),"evaluated_at_utc":now.isoformat(),
            "status":state,"missing_gates":missing,"checkpoints":checkpoints,
            "rule":"Never convert HOLD to TAKE based only on countdown. Recheck executable odds and all evidence before placing a bet."}
