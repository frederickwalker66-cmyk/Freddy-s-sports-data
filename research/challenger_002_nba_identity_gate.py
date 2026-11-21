"""Fail-closed sportsbook identity gate for SportsDataIO scrambled feeds."""
from research.challenger_002_nba_research_join import field

def gate(rows,verified_mapping=None):
    result={"status":"BLOCKED_SPORTSBOOK_IDENTITY","pregame_rows":0,
            "scrambled_rows":0,"verified_draftkings_rows":0,
            "sportsbook_identity_verified":False,"certified_take_count":0,
            "training_rows_approved":0,
            "blockers":["SPORTSBOOK_NAME_SCRAMBLED_OR_UNVERIFIED",
                        "INDEPENDENT_PROVIDER_ID_MAPPING_REQUIRED"]}
    if not isinstance(rows,list):
        result["status"]="BLOCKED_INVALID_INPUT";return result
    # No caller-provided ID mapping is accepted as proof: requires a
    # separately authenticated provider reference and custody workflow.
    for game in rows:
        if not isinstance(game,dict):continue
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            result["pregame_rows"]+=1
            name=field(market,"Sportsbook")
            if isinstance(name,str) and name.strip().casefold()=="scrambled":
                result["scrambled_rows"]+=1
    return result
