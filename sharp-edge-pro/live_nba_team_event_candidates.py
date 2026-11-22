"""Aggregate-only live roster-team and market-event candidate audit."""
import os
from live_nba_name_candidates import SHARP_URL, ROSTER_URL, retrieve
from nba_team_event_candidates import aggregate

def main():
    sharp=os.getenv("SHARP_API_KEY")
    nba=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp or not nba:
        raise SystemExit("HOLD: missing provider credentials")
    try:
        market_payload=retrieve(SHARP_URL,"X-API-Key",sharp)
        players=retrieve(ROSTER_URL,"Ocp-Apim-Subscription-Key",nba)
        if not isinstance(market_payload,dict) or not isinstance(market_payload.get("data"),list) or not isinstance(players,list):
            raise ValueError("schema")
        markets=[m for m in market_payload["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
        result=aggregate(markets,players)
    except Exception as exc:
        raise SystemExit("HOLD: live provider retrieval or schema error ("+type(exc).__name__+")")
    print("Sampled player props:",result["market_count"])
    for reason,count in sorted(result["reason_counts"].items()):
        print("Candidate result:",reason,"count:",count)
    print("Independently verified event count: 0")
    print("Certified TAKE: 0 (HOLD)")

if __name__=="__main__":
    main()
