"""SportsDataIO NBA player-game statistics research ingestion.

Uses SportsDataIO's documented NBA stats JSON endpoint and an API key supplied
only through GitHub Actions Secrets. This is historical player performance data,
not sportsbook props, current betting lines, or a certified Sharp Edge feed.
"""
import json,os,urllib.request
from datetime import datetime,timezone
from pathlib import Path

def fetch(date,api_key):
    if not api_key: return {"status":"NOT_CONFIGURED","games":0,"players":0}
    if not date or len(date)!=10 or date[4]!='-' or date[7]!='-':
        raise ValueError("date must be YYYY-MM-DD")
    url="https://api.sportsdata.io/v3/nba/stats/json/PlayerGameStatsByDate/"+date
    request=urllib.request.Request(url,headers={
        "Ocp-Apim-Subscription-Key":api_key,
        "Accept":"application/json",
        "User-Agent":"FreddyNBAResearch/1"})
    with urllib.request.urlopen(request,timeout=30) as response:
        data=json.load(response)
    if not isinstance(data,list):raise ValueError("unexpected SportsDataIO response")
    rows=[]
    for x in data:
        if not isinstance(x,dict):continue
        pid=x.get("PlayerID")
        gid=x.get("GameID")
        if pid is None or gid is None:continue
        rows.append({
            "provider":"SportsDataIO","provider_game_id":str(gid),
            "provider_player_id":str(pid),"team":x.get("Team"),
            "opponent":x.get("Opponent"),"date":date,
            "points":x.get("Points"),"rebounds":x.get("Rebounds"),
            "assists":x.get("Assists"),"minutes":x.get("Minutes"),
            "is_game_over":x.get("IsGameOver"),
        })
    out=Path("sportsdataio_research");out.mkdir(exist_ok=True)
    if rows:
        (out/"player_game_stats.json").write_text(json.dumps({
            "provider":"SportsDataIO","retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
            "date":date,"records":rows,"certified":False,"decision":"HOLD",
            "note":"Historical statistics only; not a sportsbook or prop quote."
        },indent=2)+"\n")
    return {"status":"HISTORICAL_STATS_RETRIEVED" if rows else "NO_STATS",
            "games":len({r["provider_game_id"] for r in rows}),"players":len(rows)}

def main():
    from datetime import timedelta
    date=os.getenv("SPORTSDATAIO_NBA_DATE") or (datetime.now(timezone.utc)-timedelta(days=2)).date().isoformat()
    try:report=fetch(date,os.getenv("SPORTSDATAIO_API_KEY",""))
    except Exception as exc:
        report={"status":"ERROR","error_type":type(exc).__name__,"games":0,"players":0}
    print(json.dumps(report))
    if report["status"]=="ERROR":raise SystemExit(1)

if __name__=="__main__":main()
