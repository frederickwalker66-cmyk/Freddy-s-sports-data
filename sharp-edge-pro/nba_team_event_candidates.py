"""Fail-closed NBA team and event candidate checks.

Team abbreviation agreement is preliminary evidence, not independent event
verification or confirmation of a player's eligibility.
"""
from nba_name_candidates import canonical, candidate_index

def inspect_market(market, players):
    result={"status":"HOLD","reason":"unverified","certified_take":False}
    if not isinstance(market,dict) or market.get("is_player_prop") is not True:
        result["reason"]="not_player_prop"
        return result
    name=canonical(market.get("player_name"))
    matches=candidate_index(players).get(name,[]) if name else []
    if len(matches)!=1:
        result["reason"]="player_identity_missing_or_ambiguous"
        return result
    player=matches[0]
    if not player.get("PlayerID") or not player.get("TeamID"):
        result["reason"]="provider_player_or_team_id_missing"
        return result
    teams=[]
    for side in ("home","away"):
        nested=market.get(side)
        if isinstance(nested,dict):
            abbr=canonical(nested.get("abbreviation"))
            if abbr:
                teams.append(abbr)
    if len(teams)!=2 or teams[0]==teams[1]:
        result["reason"]="market_teams_missing_or_invalid"
        return result
    roster_team=canonical(player.get("Team"))
    if not roster_team or roster_team not in teams:
        result["reason"]="player_team_not_in_market_matchup"
        return result
    if not market.get("event_id") and not market.get("event_uuid"):
        result["reason"]="market_event_id_missing"
        return result
    if not market.get("event_start_time"):
        result["reason"]="market_event_start_missing"
        return result
    result["status"]="TEAM_EVENT_CANDIDATE_ONLY"
    result["reason"]="requires_independent_schedule_and_identity_validation"
    return result

def aggregate(markets,players):
    counts={}
    for market in markets:
        outcome=inspect_market(market,players)
        counts[outcome["reason"]]=counts.get(outcome["reason"],0)+1
    return {"market_count":len(markets),"reason_counts":counts,
            "verified_events":0,"certified_take":0,"decision":"HOLD"}
