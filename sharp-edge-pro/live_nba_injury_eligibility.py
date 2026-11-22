"""Live, aggregate-only NBA injury crosscheck. Never certifies player availability."""
import os
from live_nba_name_candidates import SHARP_URL,ROSTER_URL,retrieve
from nba_injury_eligibility import summarize

def main():
    sharp=os.getenv("SHARP_API_KEY")
    nba=os.getenv("SPORTSDATAIO_NBA_API_KEY") or os.getenv("SPORTSDATAIO")
    if not sharp or not nba:
        raise SystemExit("HOLD: missing provider credentials")
    try:
        payload=retrieve(SHARP_URL,"X-API-Key",sharp)
        players=retrieve(ROSTER_URL,"Ocp-Apim-Subscription-Key",nba)
        injured=retrieve("https://api.sportsdata.io/v3/nba/projections/json/InjuredPlayers",
                         "Ocp-Apim-Subscription-Key",nba)
        if not isinstance(payload,dict) or not isinstance(payload.get("data"),list) or not isinstance(players,list) or not isinstance(injured,list):
            raise ValueError("provider_schema")
        markets=[m for m in payload["data"] if isinstance(m,dict) and m.get("is_player_prop") is True]
        result=summarize(markets,players,injured)
    except Exception as exc:
        raise SystemExit("HOLD: provider retrieval or schema failed ("+type(exc).__name__+")")
    print("Player props screened:",result["market_count"])
    print("Provider injured-player records:",len(injured))
    for reason,count in sorted(result["reasons"].items()):
        print("Injury screening:",reason,"count:",count)
    print("Official independent injury verification: 0")
    print("Certified TAKE: 0 (HOLD)")

if __name__=="__main__":
    main()
