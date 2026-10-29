"""Archive independent public completed-game evidence for Challenger research only.

ESPN scoreboard is a *separate published source*, NOT official league adjudication.
No sportsbook odds, player props or Champion-001 probabilities are generated.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

LEAGUES = {
    "nba": ("basketball","nba"), "nfl": ("football","nfl"),
    "mlb": ("baseball","mlb"), "nhl": ("hockey","nhl"),
    "ncaaf": ("football","college-football"),
    "ncaab": ("basketball","mens-college-basketball"),
    "mls": ("soccer","usa.1"),
    "uefa_champions_league": ("soccer","uefa.champions"),
}
BASE="https://site.api.espn.com/apis/site/v2/sports/"

def scoreboard_url(league,day):
    sport,comp=LEAGUES[league]
    return BASE+sport+"/"+comp+"/scoreboard?"+urlencode({"dates":day.strftime("%Y%m%d"),"limit":500})

def fetch_json(url):
    req=Request(url,headers={"User-Agent":"FreddysPicks-HistoricalResearch/1.0","Accept":"application/json"})
    with urlopen(req,timeout=16) as resp:
        raw=resp.read(6_000_001)
    if len(raw)>6_000_000: raise ValueError("oversized scoreboard")
    result=json.loads(raw)
    if not isinstance(result,dict) or not isinstance(result.get("events"),list): raise ValueError("invalid ESPN scoreboard shape")
    if len(result["events"])>=500: raise ValueError("scoreboard response may be truncated")
    return result

def parse_time(value):
    if not isinstance(value,str): raise ValueError("missing game time")
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("naive game time")
    return d.astimezone(timezone.utc)

def int_score(value):
    if isinstance(value,bool): raise ValueError("invalid score")
    if not isinstance(value,(str,int)): raise ValueError("invalid score")
    s=str(value)
    if not s.isdigit(): raise ValueError("invalid score")
    v=int(s)
    if v>999: raise ValueError("impossible game score")
    return v

def normalize_game(game,league,source_url,now):
    if not isinstance(game,dict): return None
    status=game.get("status")
    if not isinstance(status,dict) or not isinstance(status.get("type"),dict): return None
    state=status["type"]
    if state.get("state")!="post" or state.get("completed") is not True: return None
    comps=game.get("competitions")
    if not isinstance(comps,list) or len(comps)!=1 or not isinstance(comps[0],dict): return None
    comp=comps[0]
    competitors=comp.get("competitors")
    if not isinstance(competitors,list) or len(competitors)!=2: return None
    try:
        started=parse_time(game.get("date") or comp.get("date"))
        if started>=now: return None
        by_side={}
        for c in competitors:
            if not isinstance(c,dict) or c.get("homeAway") not in ("home","away"): return None
            team=c.get("team")
            if not isinstance(team,dict): return None
            team_id=str(team.get("id") or "").strip()
            name=team.get("displayName")
            if not team_id or not isinstance(name,str) or not name.strip(): return None
            by_side[c["homeAway"]]={"id":team_id,"name":name.strip(),"score":int_score(c.get("score"))}
        home,away=by_side["home"],by_side["away"]
        if home["id"]==away["id"]: return None
        eid=str(game.get("id") or "")
        if not eid or not eid.isdigit(): return None
    except (ValueError,KeyError,TypeError,OverflowError): return None
    return {
        "record_type":"historical_completed_game_research",
        "outcome_source":"espn_public_scoreboard",
        "source_url":source_url,"retrieved_at_utc":now.isoformat(),
        "league":league,"espn_event_id":eid,"event_start_utc":started.isoformat(),
        "home_team":home["name"],"home_team_espn_id":home["id"],"home_score":home["score"],
        "away_team":away["name"],"away_team_espn_id":away["id"],"away_score":away["score"],
        "result":"home" if home["score"]>away["score"] else "away" if home["score"]<away["score"] else "draw",
        "official_league_result_verified":False,
        "provider_event_id_crosswalk_verified":False,
        "champion_001_modified":False,
    }

def collect(leagues,days,end_date,fetcher=fetch_json,clock=None,pause_seconds=0.12):
    now=(clock or (lambda:datetime.now(timezone.utc)))()
    if now.tzinfo is None: raise ValueError("clock must be timezone-aware")
    if not 1<=days<=35: raise ValueError("limit 1-35 days")
    if any(l not in LEAGUES for l in leagues) or len(set(leagues))!=len(leagues): raise ValueError("invalid/duplicate leagues")
    if end_date>now.astimezone(ZoneInfo("America/New_York")).date(): raise ValueError("future end date not allowed")
    rows,seen=[],set()
    stats={league:{"days_attempted":0,"days_ok":0,"days_failed":0,"completed_games":0,"draws":0,"error_types":{}} for league in leagues}
    for league in leagues:
        errors=Counter()
        for n in range(days):
            day=end_date-timedelta(days=days-1-n)
            url=scoreboard_url(league,day)
            stats[league]["days_attempted"]+=1
            try:
                payload=fetcher(url)
                if not isinstance(payload,dict) or not isinstance(payload.get("events"),list): raise ValueError("invalid events")
                if len(payload["events"])>=500: raise ValueError("possibly truncated")
                stats[league]["days_ok"]+=1
                for game in payload["events"]:
                    row=normalize_game(game,league,url,now)
                    if row is None:continue
                    # Never trust the endpoint to stay inside the requested date window.
                    if parse_time(row["event_start_utc"]).astimezone(ZoneInfo("America/New_York")).date()!=day:continue
                    key=(league,row["espn_event_id"])
                    if key in seen:continue
                    seen.add(key);rows.append(row)
                    stats[league]["completed_games"]+=1
                    stats[league]["draws"]+=int(row["result"]=="draw")
            except Exception as exc:
                stats[league]["days_failed"]+=1
                errors[type(exc).__name__]+=1
            if pause_seconds:time.sleep(pause_seconds)
        stats[league]["error_types"]=dict(errors)
    rows.sort(key=lambda x:(x["event_start_utc"],x["league"],x["espn_event_id"]))
    summary={
        "source":"ESPN public scoreboard (not official league result certification)",
        "generated_at_utc":now.isoformat(),"end_date_et":end_date.isoformat(),"days":days,
        "leagues":list(leagues),"daily_requests_maximum":len(leagues)*days,
        "by_league":stats,"total_completed_results":len(rows),
        "independently_officially_adjudicated_results":0,
        "certified_champion_001_predictions":0,"bet_ready_selections":0,
        "champion_001_modified":False,
        "warning":"Historical games may be partial on failed days; results are not training-ready until coverage and identity are audited."
    }
    return rows,summary

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--leagues",default="NBA,NFL,MLB,NHL,NCAAF,NCAAB,MLS,UEFA_CHAMPIONS_LEAGUE")
    p.add_argument("--days",type=int,default=21)
    p.add_argument("--end-date",default=None)
    p.add_argument("--output-dir",default="challenger_history")
    args=p.parse_args(argv)
    leagues=tuple(x.strip().lower() for x in args.leagues.split(",") if x.strip())
    today=datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date()
    end=date.fromisoformat(args.end_date) if args.end_date else today-timedelta(days=1)
    data,report=collect(leagues,args.days,end)
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"results.jsonl").write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in data),encoding="utf8")
    (out/"coverage.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
