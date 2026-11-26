"""Read-only live coverage diagnostic; no paid API calls."""
import json
from v8_nfl_live_feed import collect
from v8_nfl_live_ticket import track
def probe():
    feed=collect()
    ticket=track(feed)
    active=[g for g in feed["games"] if g["state"]=="in"]
    return {"source":feed["source"],"retrieved_utc":feed["retrieved_utc"],
            "active_games":len(active),
            "active_games_with_player_rows":sum(bool(g["players"]) for g in active),
            "errors":feed["errors"],"ticket":ticket,
            "provider_freshness_verified":False,
            "production_ready":False,
            "reason":"Independent source timestamps, complete market coverage and backup provider required"}
if __name__=="__main__":
    print(json.dumps(probe(),indent=2))
