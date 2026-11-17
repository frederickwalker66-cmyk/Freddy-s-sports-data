"""Use only PRE-EXISTING SharpAPI research artifacts to display exact market rows.

No provider API calls. ESPN corroboration is by exact league/team/start identity;
book label is an aggregator attribution, not executable checkout or certified EV.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json, math, re
from pathlib import Path
from zoneinfo import ZoneInfo

LEAGUES=("nba","nfl","mlb","nhl","ncaaf","ncaab","mls","uefa_champions_league")
NY=ZoneInfo("America/New_York")
COMBOS={
 "player_points_+_rebounds":"PR","player_points_+_assists":"PA",
 "player_rebounds_+_assists":"RA","player_points_+_rebounds_+_assists":"PRA",
 "player_rushing_+_receiving_yards":"Rush+Receive",
 "player_passing_+_rushing_yards":"Pass+Rush",
}
ALIASES={
 "mlb":{"run_line":"point_spread","total_runs":"total_points"},
 "nhl":{"puck_line":"point_spread","total_goals":"total_points"}
}
GAME={"moneyline","point_spread","total_points"}
CATEGORIES={"game","prop","combo"}

def utc(v):
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None

def name(v,cap=90):
    return "".join(ch for ch in v if ch.isprintable())[:cap].strip() if isinstance(v,str) else ""

def slug(v):
    return " ".join(name(v).casefold().split())

def american(v):
    return v if type(v) is int and 100<=abs(v)<=99999 else None

def decimal(v):
    return v if type(v) in (int,float) and math.isfinite(v) and 0<=v<=10000 else None

def signed_line(v):
    return v if type(v) in (int,float) and math.isfinite(v) and -1000<=v<=1000 else None

def parse(path,public,*,now=None,provider_run=0):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("aware clock required")
    now=now.astimezone(timezone.utc)
    day=now.astimezone(NY).date().isoformat()
    result={
      "schema":"freddys-existing-book-refs-v1","date_et":day,
      "processed_at_utc":now.isoformat(),
      "provider_run":provider_run if type(provider_run) is int and provider_run>0 else None,
      "capture_status":"NO_USABLE_CURRENT_PROVIDER_ARTIFACT",
      "leagues":{lg:{"rows":[],"game":0,"prop":0,"combo":0} for lg in LEAGUES},
      "certified_positive_ev":0,"checkout_prices_verified":0,
      "champion_001_modified":False,
      "source_notice":"Previously collected SharpAPI, aggregator-labelled DraftKings pregame quotes; no checkout, no certified EV."
    }
    if (not isinstance(public,dict)
        or public.get("schema")!="freddys-espn-public-hourly-v1"
        or public.get("date_et")!=day
        or public.get("champion_001_modified") is not False
        or not isinstance(public.get("leagues"),dict)):
        return result
    games={}
    for lg,source in public["leagues"].items():
        if lg not in LEAGUES or not isinstance(source,dict) or source.get("status")!="ESPN_SCOREBOARD_OBSERVED":
            continue
        observed=utc(source.get("observed_at_utc"))
        if not observed or not 0<=(now-observed).total_seconds()<=90*60:continue
        for g in source.get("games",[])[:120]:
            if not isinstance(g,dict) or g.get("status")!="pre":continue
            start=utc(g.get("start_et"))
            if not start or start<=now:continue
            key=(lg,slug(g.get("home")),slug(g.get("away")))
            games.setdefault(key,[]).append((g,start))
    if not path or not Path(path).is_file():return result
    source=Path(path)
    if source.stat().st_size>70_000_000:return result
    seen={}
    with source.open(encoding="utf-8") as stream:
        for i,line in enumerate(stream):
            if i>=100_000:break
            try:q=json.loads(line)
            except (ValueError,TypeError):continue
            if not isinstance(q,dict) or q.get("record_type")!="pregame_odds_observation":continue
            lg=q.get("league")
            if lg not in LEAGUES or q.get("sportsbook")!="draftkings" or q.get("certified_prediction") is not False:continue
            quote=utc(q.get("timestamp"));receipt=utc(q.get("recorded_at"));start=utc(q.get("event_start_time"))
            if not quote or not receipt or not start:continue
            if not(0<=(now-quote).total_seconds()<=60*60
                   and 0<=(now-receipt).total_seconds()<=60*60
                   and 0<=(receipt-quote).total_seconds()<=15*60
                   and now<start and quote<start and receipt<start):continue
            choices=games.get((lg,slug(q.get("home_team")),slug(q.get("away_team"))),[])
            exact=[g for g,t in choices if abs((t-start).total_seconds())<=60]
            if len(exact)!=1:continue
            game=exact[0];odd=american(q.get("odds_american"))
            if odd is None:continue
            market=name(q.get("market_type"),80)
            base=ALIASES.get(lg,{}).get(market,market)
            player=name(q.get("player_name"),90)
            typ=q.get("selection_type")
            if q.get("is_player_prop") is True:
                if not player or typ not in ("over","under"):continue
                cat="combo" if market in COMBOS else "prop"
                linevalue=decimal(q.get("line"))
                if linevalue is None:continue
                display=COMBOS.get(market) or market.removeprefix("player_").replace("_","+").replace("+ +","+")
            elif q.get("is_player_prop") is False:
                if base not in GAME:continue
                if base=="moneyline":
                    if typ not in ("home","away") or q.get("line") is not None:continue
                    linevalue=None
                elif base=="point_spread":
                    if typ not in ("home","away"):continue
                    linevalue=signed_line(q.get("line"))
                    if linevalue is None:continue
                else:
                    if typ not in ("over","under"):continue
                    linevalue=decimal(q.get("line"))
                    if linevalue is None or linevalue<=0:continue
                cat="game";display=base.replace("_"," ")
            else:continue
            side=name(typ,25)
            event_id=name(q.get("event_id"),100)
            if not event_id:continue
            row={
                "league":lg,"public_game_id":str(game["id"]),
                "event_start_et":game["start_et"],
                "home":name(game["home"]),"away":name(game["away"]),
                "player":player or None,"market":market,"market_label":display,
                "category":cat,"side":side,"line":linevalue,
                "american_odds":odd,"provider_quote_utc":quote.isoformat(),
                "source_received_utc":receipt.isoformat(),
                "provider":"SharpAPI / DraftKings-labelled",
                "original_provider_event_id":event_id,
                "crosswalk":"ESPN team names and start time (not independent identity authentication)",
                "is_alternate_line":q.get("is_alternate_line") is True,
                "bet_ready":False,"checkout_verified":False,
                "model_probability":None,"expected_value":None,
            }
            key=(lg,row["public_game_id"],player,market,side,linevalue,row["is_alternate_line"])
            prev=seen.get(key)
            if prev is None or row["provider_quote_utc"]>prev["provider_quote_utc"]:
                seen[key]=row
    rows=sorted(seen.values(),key=lambda q:(q["event_start_et"],q["public_game_id"],q["player"] or "",q["market"],q["side"]))
    for row in rows[:3000]:
        league=result["leagues"][row["league"]]
        if len(league["rows"])>=450:continue
        league["rows"].append(row);league[row["category"]]+=1
    if rows:result["capture_status"]="RECENT_PROVIDER_ARTIFACT_RESEARCH_ONLY"
    return result

def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--quotes");arg.add_argument("--public",required=True);arg.add_argument("--out",required=True)
    arg.add_argument("--provider-run",type=int,default=0)
    args=arg.parse_args()
    try:public=json.loads(Path(args.public).read_text())
    except (OSError,ValueError):public=None
    d=parse(args.quotes,public,provider_run=args.provider_run)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.out).write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d["capture_status"],"rows":sum(len(v["rows"]) for v in d["leagues"].values()),"provider_calls":0}))

if __name__=="__main__":main()
