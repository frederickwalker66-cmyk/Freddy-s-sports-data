"""Research-only player injury and roster eligibility screening.

SportsDataIO injuries may be stale. Absence from an injury feed is NOT clearance.
No player can be certified eligible by this module.
"""
from nba_name_candidates import canonical,candidate_index

BLOCKED={"out","doubtful","inactive","suspended","injured","ruled out"}
UNCERTAIN={"questionable","probable","day-to-day","day to day","game time decision","gtd"}

def screen(market,players,injured):
    if not isinstance(market,dict) or not isinstance(players,list) or not isinstance(injured,list):
        return "HOLD_INVALID_INPUT"
    if market.get("is_player_prop") is not True:
        return "HOLD_NOT_PLAYER_PROP"
    name=canonical(market.get("player_name"))
    candidates=candidate_index(players).get(name,[]) if name else []
    if len(candidates)!=1:
        return "HOLD_PLAYER_IDENTITY_MISSING_OR_AMBIGUOUS"
    player=candidates[0]
    pid=player.get("PlayerID")
    teamid=player.get("TeamID")
    if not pid or not teamid:
        return "HOLD_PLAYER_ID_OR_TEAM_MISSING"
    injury_matches=[row for row in injured if isinstance(row,dict) and str(row.get("PlayerID") or "")==str(pid)]
    if len(injury_matches)>1:
        return "HOLD_DUPLICATE_INJURY_RECORDS"
    if injury_matches and injury_matches[0].get("TeamID") and str(injury_matches[0]["TeamID"])!=str(teamid):
        return "HOLD_INJURY_TEAM_CONFLICT"
    statuses=[canonical(player.get("Status")),canonical(player.get("InjuryStatus"))]
    if injury_matches:
        statuses.extend([canonical(injury_matches[0].get("Status")),canonical(injury_matches[0].get("InjuryStatus"))])
    if any(s in BLOCKED for s in statuses):
        return "HOLD_REPORTED_UNAVAILABLE"
    if any(s in UNCERTAIN for s in statuses):
        return "HOLD_REPORTED_UNCERTAIN"
    if not injury_matches:
        return "HOLD_NO_INJURY_RECORD_NOT_CLEARANCE"
    return "HOLD_PROVIDER_ONLY_NOT_OFFICIAL_ELIGIBILITY"

def summarize(markets,players,injured):
    counts={}
    for market in markets:
        reason=screen(market,players,injured)
        counts[reason]=counts.get(reason,0)+1
    return {"market_count":len(markets),"reasons":counts,"certified_take":0,"decision":"HOLD"}
