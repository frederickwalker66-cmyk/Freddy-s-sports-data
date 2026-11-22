"""Diagnose schedule time matching without printing licensed game records."""
import os
from datetime import datetime,timedelta
from live_nba_name_candidates import SHARP_URL,retrieve
from nba_schedule_crosscheck import abbreviations,instant,schedule_teams

def main():
    sharp=os.getenv("SHARP_API_KEY")
    nba=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp or not nba:
        raise SystemExit("HOLD: missing provider credentials")
    try:
        payload=retrieve(SHARP_URL,"X-API-Key",sharp)
        markets=[m for m in payload["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
        days=set()
        for m in markets:
            start=instant(m.get("event_start_time"))
            if start:
                days.update((start.date(),(start-timedelta(days=1)).date(),(start+timedelta(days=1)).date()))
        if not days:
            raise ValueError("no_aware_market_times")
        games=[]
        for day in sorted(days):
            feed=retrieve("https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/"+day.isoformat(),
                          "Ocp-Apim-Subscription-Key",nba)
            if not isinstance(feed,list):
                raise ValueError("schedule_not_list")
            games.extend(feed)
    except Exception as exc:
        raise SystemExit("HOLD: provider/schema error ("+type(exc).__name__+")")
    fields=set()
    for game in games:
        if isinstance(game,dict):
            fields.update(k for k in game if "date" in k.lower() or "time" in k.lower() or "gameid" in k.lower())
    print("Schedule date/time field names:",sorted(fields))
    counts={"no_team_match":0,"market_time_missing":0,"schedule_utc_missing_or_unparseable":0,
            "schedule_utc_match_within_30m":0,"schedule_utc_mismatch_over_30m":0}
    for market in markets:
        matchup=abbreviations(market)
        matching=[g for g in games if isinstance(g,dict) and schedule_teams(g)==matchup]
        if not matching:
            counts["no_team_match"]+=1
            continue
        mtime=instant(market.get("event_start_time"))
        if not mtime:
            counts["market_time_missing"]+=1
            continue
        times=[instant(g.get("DateTimeUTC")) for g in matching]
        if not any(times):
            counts["schedule_utc_missing_or_unparseable"]+=1
        elif any(t and abs((t-mtime).total_seconds())<=1800 for t in times):
            counts["schedule_utc_match_within_30m"]+=1
        else:
            counts["schedule_utc_mismatch_over_30m"]+=1
    for k,v in sorted(counts.items()):
        print("Time diagnostic:",k,v)
    print("Certified TAKE: 0 (HOLD)")

if __name__=="__main__":
    main()
