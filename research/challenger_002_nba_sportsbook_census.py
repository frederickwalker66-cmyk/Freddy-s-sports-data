"""Aggregate sportsbook name census; never log odds prices or licensed market rows."""
from collections import Counter
from research.challenger_002_nba_research_join import field

def census(rows):
    result={"status":"RESEARCH_SPORTSBOOK_CENSUS_ONLY","sportsbooks":[],
            "pregame_rows":0,"certified_take_count":0,"draftkings_identity_verified":False}
    if not isinstance(rows,list):
        result["status"]="BLOCKED_INVALID_INPUT";return result
    counts=Counter();ids={}
    for game in rows:
        if not isinstance(game,dict):continue
        markets=field(game,"PregameOdds")
        if not isinstance(markets,list):continue
        for market in markets:
            if not isinstance(market,dict):continue
            result["pregame_rows"]+=1
            name=field(market,"Sportsbook")
            sid=field(market,"SportsbookId")
            label=name.strip() if isinstance(name,str) and name.strip() else "(missing)"
            # Only bounded sportsbook labels and identifier strings; no prices.
            if len(label)>100:label="(invalid name)"
            counts[label]+=1
            if sid is not None:ids.setdefault(label,set()).add(str(sid)[:40])
    result["sportsbooks"]=[{"name":name,"market_rows":count,
                           "sportsbook_ids":sorted(ids.get(name,set()))}
                          for name,count in sorted(counts.items())]
    return result
