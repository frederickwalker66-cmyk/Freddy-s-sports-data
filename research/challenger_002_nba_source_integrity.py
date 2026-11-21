"""Research-only source-integrity gate: scrambled odds are not real prices.

SportsDataIO documents trial/dev scrambled values as unsuitable for
analysis. No sportsbook-ID inference, training or certified TAKE permitted.
"""
from research.challenger_002_nba_research_join import field

def audit(odds):
    out={"status":"BLOCKED_UNVERIFIED_ODDS_INTEGRITY","game_records":0,
         "pregame_market_rows":0,"scrambled_sportsbook_rows":0,
         "non_scrambled_sportsbook_rows":0,"real_prices_verified":False,
         "eligible_training_rows":0,"certified_take_count":0,
         "blockers":["SPORTSDATAIO_SCRAMBLED_FEED_POSSIBLE",
                     "PRODUCTION_REAL_DATA_ENTITLEMENT_UNVERIFIED",
                     "DRAFTKINGS_IDENTITY_UNVERIFIED"]}
    if not isinstance(odds,list):
        out["status"]="BLOCKED_INVALID_INPUT";return out
    out["game_records"]=len(odds)
    for game in odds:
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            out["pregame_market_rows"]+=1
            name=field(market,"Sportsbook")
            if isinstance(name,str) and name.strip().casefold()=="scrambled":
                out["scrambled_sportsbook_rows"]+=1
            else:out["non_scrambled_sportsbook_rows"]+=1
    if out["scrambled_sportsbook_rows"]:
        out["status"]="BLOCKED_SCRAMBLED_SPORTSBOOK"
    return out
