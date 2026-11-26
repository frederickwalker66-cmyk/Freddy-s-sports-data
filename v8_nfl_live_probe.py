"""Read-only live coverage diagnostic; no paid API calls."""
import json
from v8_nfl_live_feed import collect
from v8_nfl_live_ticket import track
from v8_nfl_live_failover import collect_with_failover
def probe():
    feed=collect_with_failover(collect)
    ticket=track(feed)
    active=[g for g in feed["games"] if g["state"]=="in"]
    return {"source":feed.get("source"),"retrieved_utc":feed.get("retrieved_utc"),
            "active_games":len(active),
            "active_games_with_player_rows":sum(bool(g["players"]) for g in active),
            "errors":feed.get("errors",[]),"provider_attempts":feed.get("provider_attempts",[]),"ticket":ticket,
            "provider_freshness_verified":False,
            "production_ready":False,
            "reason":"Independent source timestamps, complete market coverage and backup provider required"}
if __name__=="__main__":
    print(json.dumps(probe(),indent=2))
