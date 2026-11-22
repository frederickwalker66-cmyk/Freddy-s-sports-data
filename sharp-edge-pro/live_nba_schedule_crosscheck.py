"""Live read-only NBA schedule comparison; aggregate results only."""
import os
from datetime import datetime,timezone,timedelta
from live_nba_name_candidates import SHARP_URL,retrieve
from nba_schedule_crosscheck import summarize

def main():
    sharp=os.getenv("SHARP_API_KEY")
    nba=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp or not nba:
        raise SystemExit("HOLD: missing provider credentials")
    try:
        payload=retrieve(SHARP_URL,"X-API-Key",sharp)
        if not isinstance(payload,dict) or not isinstance(payload.get("data"),list):
            raise ValueError("sharp_schema")
        markets=[m for m in payload["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
        dates=set()
        for market in markets:
            raw=market.get("event_start_time")
            if isinstance(raw,str):
                try:
                    t=datetime.fromisoformat(raw.replace("Z","+00:00"))
                    if t.tzinfo:
                        dates.update((t.date(),(t-timedelta(days=1)).date(),(t+timedelta(days=1)).date()))
                except ValueError:
                    pass
        if not dates:
            raise ValueError("no_parseable_event_dates")
        games=[]
        for day in sorted(dates):
            url="https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/"+day.isoformat()
            feed=retrieve(url,"Ocp-Apim-Subscription-Key",nba)
            if not isinstance(feed,list):
                raise ValueError("schedule_schema")
            games.extend(feed)
        result=summarize(markets,games)
    except Exception as exc:
        raise SystemExit("HOLD: schedule retrieval or schema failure ("+type(exc).__name__+")")
    print("Player props checked:",result["markets"])
    print("Schedule rows inspected:",len(games))
    for status,count in sorted(result["statuses"].items()):
        print("Schedule result:",status,"count:",count)
    print("Independently verified roster/eligibility: 0")
    print("Certified TAKE: 0 (HOLD)")

if __name__=="__main__":
    main()
