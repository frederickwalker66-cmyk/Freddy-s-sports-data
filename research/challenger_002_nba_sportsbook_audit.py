"""Research-only sportsbook identity and price-field completeness diagnostic.

Never exports prices or claims an independently verified DraftKings market.
"""
from collections import Counter
from research.challenger_002_nba_research_join import field

def audit(rows):
    out={"status":"RESEARCH_SPORTSBOOK_SCREEN_ONLY","pregame_market_rows":0,
         "draftkings_name_matches":0,"draftkings_named_game_count":0,
         "missing_sportsbook_name":0,"missing_sportsbook_id":0,
         "missing_created_timestamp":0,"missing_updated_timestamp":0,
         "other_named_sportsbook_rows":0,"unique_sportsbook_id_count":0,
         "moneyline_pair_present":0,"spread_pair_present":0,"total_pair_present":0,
         "draftkings_identity_verified":False,"independent_price_custody_verified":False,
         "certified_take_count":0,"training_rows_approved":0}
    if not isinstance(rows,list):
        out["status"]="BLOCKED_INVALID_INPUT";return out
    ids=set();dk_games=set()
    for row in rows:
        if not isinstance(row,dict):continue
        game=field(row,"GameID")
        markets=field(row,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            out["pregame_market_rows"]+=1
            name=field(market,"Sportsbook")
            sid=field(market,"SportsbookId")
            if not isinstance(name,str) or not name.strip():
                out["missing_sportsbook_name"]+=1
            elif name.strip().casefold()=="draftkings":
                out["draftkings_name_matches"]+=1
                if game is not None:dk_games.add(str(game))
            else:
                out["other_named_sportsbook_rows"]+=1
            if sid is None:out["missing_sportsbook_id"]+=1
            else:ids.add(str(sid))
            if field(market,"Created") is None:out["missing_created_timestamp"]+=1
            if field(market,"Updated") is None:out["missing_updated_timestamp"]+=1
            if all(field(market,k) is not None for k in ("HomeMoneyLine","AwayMoneyLine")):
                out["moneyline_pair_present"]+=1
            if all(field(market,k) is not None for k in ("HomePointSpread","AwayPointSpread")):
                out["spread_pair_present"]+=1
            if all(field(market,k) is not None for k in ("OverUnder","OverPayout","UnderPayout")):
                out["total_pair_present"]+=1
    out["draftkings_named_game_count"]=len(dk_games)
    out["unique_sportsbook_id_count"]=len(ids)
    return out
