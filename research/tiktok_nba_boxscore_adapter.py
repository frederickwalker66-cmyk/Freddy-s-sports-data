"""Offline ESPN player-box adapter: prior-game 3PM features only, research-only.
Consumes challenger_nba_player_boxes.py JSONL output. No API calls or bets.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

def parse_time(s):
    if not isinstance(s,str): raise ValueError("missing timestamp")
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timezone required")
    return d.astimezone(timezone.utc)

def rolling_features(rows, threshold=1.5):
    if not math.isfinite(threshold) or threshold < 0: raise ValueError("invalid threshold")
    seen=set(); valid=[]; quarantined=[]
    for r in rows:
        try:
            if r.get("sport")!="nba" or not str(r.get("player_id","")).isdigit() or not str(r.get("event_id","")).isdigit():
                raise ValueError("invalid identity")
            key=(str(r["event_id"]),str(r["player_id"]))
            if key in seen: raise ValueError("duplicate player-game")
            seen.add(key)
            t=parse_time(r["event_start_utc"])
            if r.get("did_not_play") is not False or type(r.get("threes_made")) is not int or r["threes_made"]<0:
                raise ValueError("DNP or missing 3PM")
            if r.get("minutes") is not None and (
                type(r["minutes"]) not in (int,float) or not math.isfinite(r["minutes"])
                or r["minutes"] < 0 or r["minutes"] > 70
            ):
                raise ValueError("invalid minutes")
            if r.get("independently_verified_player_stats") is not False or r.get("qualified_for_player_prop_training") is not False:
                raise ValueError("unexpected qualification flags")
            valid.append((t,key,r))
        except (KeyError,ValueError,TypeError) as exc:
            quarantined.append({"event_id":r.get("event_id"),"player_id":r.get("player_id"),"reason":str(exc)})
    valid.sort(key=lambda x:(x[0],x[1]))
    history=defaultdict(list); features=[]
    for t,key,r in valid:
        prior=[v for previous_t,v in history[key[1]] if previous_t<t]
        last5=prior[-5:];last10=prior[-10:]
        features.append({"event_id":key[0],"player_id":key[1],
          "player_name":r.get("player_name"),"event_start_utc":t.isoformat(),
          "line":threshold,"actual_3pm":r["threes_made"],
          "last5_games":len(last5),"last5_hits":sum(v>threshold for v in last5),
          "last10_games":len(last10),"last10_hits":sum(v>threshold for v in last10),
          "historical_90":len(last10)==10 and sum(v>threshold for v in last10)>=9,
          "defense_rank":None,"shooter_rank":None,"pregame_odds":None,
          "native_probability":None,"decision":"HOLD",
          "certification":"UNCERTIFIED_RESEARCH_ONLY"})
        history[key[1]].append((t,r["threes_made"]))
    return {"player_game_rows":len(features),"quarantined_rows":len(quarantined),
            "unique_games":len({x["event_id"] for x in features}),
            "unique_players":len({x["player_id"] for x in features}),
            "rows_with_full_last10":sum(x["last10_games"]==10 for x in features),
            "rows_with_incomplete_last10":sum(x["last10_games"]<10 for x in features),
            "historical_90_rows":sum(x["historical_90"] for x in features),
            "certified_bets":0,"rows":features,"quarantine":quarantined}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--boxes",required=True);p.add_argument("--output",required=True)
    p.add_argument("--line",type=float,default=1.5)
    a=p.parse_args()
    with open(a.boxes,encoding="utf8") as f: rows=[json.loads(x) for x in f if x.strip()]
    result=rolling_features(rows,a.line)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","quarantine")}))

if __name__=="__main__":main()
