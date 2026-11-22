"""Diagnose SportsDataIO DateTimeUTC shapes without exposing game values."""
import os
from datetime import timedelta
from collections import Counter
from live_nba_name_candidates import SHARP_URL,retrieve
from nba_schedule_crosscheck import instant,abbreviations,schedule_teams

def main():
    sharp=os.getenv("SHARP_API_KEY")
    nba=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp or not nba:
        raise SystemExit("HOLD: missing credentials")
    try:
        payload=retrieve(SHARP_URL,"X-API-Key",sharp)
        markets=[m for m in payload["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
        days=set()
        for m in markets:
            t=instant(m.get("event_start_time"))
            if t:
                days.update((t.date(),(t-timedelta(days=1)).date(),(t+timedelta(days=1)).date()))
        games=[]
        for day in sorted(days):
            feed=retrieve("https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/"+day.isoformat(),
                          "Ocp-Apim-Subscription-Key",nba)
            if not isinstance(feed,list):
                raise ValueError("unexpected_schedule")
            games.extend(feed)
    except Exception as exc:
        raise SystemExit("HOLD: provider retrieval failed ("+type(exc).__name__+")")
    counter=Counter()
    seen=set()
    for market in markets:
        matchup=abbreviations(market)
        for i,g in enumerate(games):
            if i in seen or not isinstance(g,dict) or schedule_teams(g)!=matchup:
                continue
            seen.add(i)
            value=g.get("DateTimeUTC")
            if value is None:
                counter["utc_null"]+=1
            elif not isinstance(value,str):
                counter["utc_non_string"]+=1
            elif instant(value):
                counter["utc_aware_parseable"]+=1
            elif "T" in value and not ("Z" in value or "+" in value):
                counter["utc_naive_iso"]+=1
            elif " " in value and not ("Z" in value or "+" in value):
                counter["utc_naive_space"]+=1
            else:
                counter["utc_other_unparseable"]+=1
            if g.get("DateTime") is not None:
                counter["local_datetime_present"]+=1
    print("Matched schedule rows inspected:",len(seen))
    for key,count in sorted(counter.items()):
        print("DateTimeUTC shape:",key,count)
    print("No timestamps or records disclosed")
    print("Certified TAKE: 0 (HOLD)")

if __name__=="__main__":
    main()
