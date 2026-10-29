"""Research-only cross-check of SharpAPI and SportsGameOdds DraftKings-labeled quotes.
Two aggregators agreeing does NOT verify DraftKings itself or certify betting value.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

def parse_dt(value):
    d = datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timezone required")
    return d.astimezone(timezone.utc)

def norm(value):
    return " ".join(re.findall(r"[a-z0-9]+",str(value or "").lower()))

def team_key(value, league):
    s = norm(value)
    if league in ("nba","nfl","nhl","mlb","wnba"):
        return s.split()[-1] if s else ""
    return s

def event_key(row):
    league = row.get("league")
    if not isinstance(league,str): return None
    home,away = (team_key(row.get(k),league) for k in ("home_team","away_team"))
    return (league,home,away) if home and away and home != away else None

def market_key(row):
    kind,side = row.get("market_type"),row.get("selection_type")
    line = row.get("line")
    if kind == "moneyline" and side in ("home","away") and line is None:
        return ("moneyline",side,None,None)
    if kind in ("point_spread","run_line","puck_line","goal_spread") and side in ("home","away"):
        family="spread"
    elif kind == "total_points" and side in ("over","under") and row.get("selection")==side.title():
        family="total_points_game"
    elif isinstance(kind,str) and kind.startswith("player_") and side in ("over","under") and row.get("player_name"):
        family={"player_receiving_receptions":"player_receptions"}.get(kind,kind)
    else: return None
    if isinstance(line,bool) or not isinstance(line,(float,int)): return None
    player = norm(row.get("player_name")) if family.startswith("player_") else None
    if family.startswith("player_") and len(player.split())<2: return None
    return (family,side,float(line),player)

def load(path,source):
    rows=[]
    for raw in Path(path).read_text(encoding="utf8").splitlines():
        if not raw.strip(): continue
        row=json.loads(raw)
        if (row.get("source")!=source or row.get("certified_prediction") is not False
                or row.get("model_probability") is not None):
            raise ValueError("Untrusted source format or unexpected model prediction")
        rows.append(row)
    return rows

def events(rows):
    seen={}
    for row in rows:
        eid=row.get("event_id")
        if not eid or eid in seen or not event_key(row): continue
        try: start=parse_dt(row["event_start_time"])
        except (KeyError,TypeError,ValueError): continue
        seen[eid]=(event_key(row),start,row)
    return seen

def prices(rows):
    grouped=defaultdict(dict)
    ties=defaultdict(set)
    for row in rows:
        key=market_key(row)
        if key is None or row.get("sportsbook")!="draftkings": continue
        eid=row.get("event_id")
        try:
            stamp=parse_dt(row["timestamp"])
            recorded=parse_dt(row["recorded_at"])
            odds=row.get("odds_american")
            if isinstance(odds,bool) or not isinstance(odds,int) or abs(odds)<100 or stamp>recorded: continue
        except (KeyError,ValueError,TypeError): continue
        old=grouped[eid].get(key)
        if old:
            if old[0]==stamp and old[1]["odds_american"]!=odds: ties[eid].add(key)
            if old[0]>=stamp: continue
        grouped[eid][key]=(stamp,row)
    for eid,keys in ties.items():
        for key in keys: grouped[eid].pop(key,None)
    return grouped

def reconcile(sharp,sgo,now=None):
    now=now or datetime.now(timezone.utc)
    a,b=events(sharp),events(sgo)
    lookup=defaultdict(list)
    for eid,(key,start,_) in b.items():lookup[key].append((eid,start))
    links=[]
    for eid,(key,start,_) in a.items():
        options=[(j,t) for j,t in lookup[key] if abs((t-start).total_seconds())<=900]
        if len(options)==1:links.append((eid,options[0][0],(start-options[0][1]).total_seconds()))
    counts=Counter(j for _,j,_ in links)
    links=[(i,j,diff) for i,j,diff in links if counts[j]==1]
    pa,pb=prices(sharp),prices(sgo)
    agree,disagree=[],[]
    for i,j,delta in links:
        for key in pa.get(i,{}).keys() & pb.get(j,{}).keys():
            ta,ra=pa[i][key]
            tb,rb=pb[j][key]
            ca,cb=parse_dt(ra["recorded_at"]),parse_dt(rb["recorded_at"])
            if abs((ca-cb).total_seconds())>1800:continue
            same=ra["odds_american"]==rb["odds_american"]
            item={
                "league":ra["league"],"home_team":b[j][2]["home_team"],"away_team":b[j][2]["away_team"],
                "event_time_sharpapi":a[i][1].isoformat(),"event_time_sgo":b[j][1].isoformat(),
                "event_time_discrepancy_seconds":delta,
                "market_type":key[0],"selection_type":key[1],"line":key[2],"player_name_research_only":key[3],
                "sharpapi_price":ra["odds_american"],"sgo_price":rb["odds_american"],
                "sharpapi_quote_time":ta.isoformat(),"sgo_quote_time":tb.isoformat(),
                "matching_prices":same,
                "both_quotes_recent_at_report_time":all(0<=(now-t).total_seconds()<=120 for t in (ta,tb,ca,cb)),
                "independent_schedule_verified":False,"draftkings_direct_price_verified":False,
                "player_availability_verified":False,"main_line_verified":False,
                "model_probability":None,"positive_ev_certified":False,"bet_ready":False,
                "status":"two_aggregator_research_only"
            }
            (agree if same else disagree).append(item)
    report={
        "generated_at_utc":now.isoformat(),"sharpapi_observations":len(sharp),"sportsgameodds_observations":len(sgo),
        "matched_events":len(links),"matched_market_lines":len(agree)+len(disagree),
        "matching_prices":len(agree),"different_prices":len(disagree),
        "fresh_at_report_time":sum(1 for x in agree+disagree if x["both_quotes_recent_at_report_time"]),
        "event_time_discrepancies":sum(d!=0 for _,_,d in links),
        "independently_verified_draftkings_prices":0,"certified_champion_001_predictions":0,
        "positive_ev_bets_certified":0,"bet_ready_selections":0,"automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":"Two aggregators are not direct DraftKings verification; schedule and availability not independently verified."
    }
    return agree,disagree,report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sharp",required=True)
    p.add_argument("--sgo",required=True)
    p.add_argument("--output-dir",default="crossfeed_output")
    args=p.parse_args()
    a,b,r=reconcile(load(args.sharp,"sharpapi_rest"),load(args.sgo,"sportsgameodds_v2"))
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    for name,rows in (("matching_prices.jsonl",a),("different_prices.jsonl",b)):
        (out/name).write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf8")
    (out/"report.json").write_text(json.dumps(r,indent=2)+"\n",encoding="utf8")
    print(json.dumps(r,indent=2))

if __name__=="__main__":main()
