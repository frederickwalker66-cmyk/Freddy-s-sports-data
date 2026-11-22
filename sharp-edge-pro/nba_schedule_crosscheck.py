"""Compare SharpAPI NBA matchups to SportsDataIO scores schedule, fail closed.

Schedule agreement is cross-feed corroboration, not proof of market identity,
roster eligibility, official injury status or positive expected value.
"""
from datetime import datetime, timezone
from nba_name_candidates import canonical

def instant(value):
    if not isinstance(value,str) or not value.strip():
        return None
    try:
        parsed=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None

def abbreviations(market):
    sides=[]
    for key in ("home","away"):
        obj=market.get(key)
        name=obj.get("abbreviation") if isinstance(obj,dict) else None
        sides.append(canonical(name))
    return tuple(sides)

def schedule_teams(game):
    return (canonical(game.get("HomeTeam")),canonical(game.get("AwayTeam")))

def assess(market,games,tolerance_minutes=30):
    if not isinstance(market,dict) or not isinstance(games,list):
        return "HOLD_INVALID_SCHEMA"
    home,away=abbreviations(market)
    start=instant(market.get("event_start_time"))
    if not home or not away or home==away or not start:
        return "HOLD_MARKET_MATCHUP_OR_TIME_MISSING"
    candidates=[g for g in games if isinstance(g,dict) and schedule_teams(g)==(home,away)]
    if not candidates:
        return "HOLD_SCHEDULE_MATCHUP_NOT_FOUND"
    valid=[]
    for game in candidates:
        scheduled=instant(game.get("DateTimeUTC"))
        if scheduled and abs((scheduled-start).total_seconds())<=tolerance_minutes*60:
            valid.append(game)
    if len(valid)!=1:
        return "HOLD_SCHEDULE_TIME_MISSING_AMBIGUOUS_OR_CONFLICTING"
    if not valid[0].get("GameID"):
        return "HOLD_SCHEDULE_GAME_ID_MISSING"
    return "SCHEDULE_CORROBORATED_ONLY"

def summarize(markets,games):
    counts={}
    for m in markets:
        status=assess(m,games)
        counts[status]=counts.get(status,0)+1
    return {"markets":len(markets),"statuses":counts,"certified_take":0,"decision":"HOLD"}
