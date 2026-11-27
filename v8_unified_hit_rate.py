"""Historical exact-current-line research; not a prediction or certification."""
from math import isfinite
from datetime import datetime

COMBOS = {"PR": ("PTS","REB"), "PA": ("PTS","AST"),
          "RA": ("REB","AST"), "PRA": ("PTS","REB","AST")}
STATS = {s:(s,) for s in ("PTS","REB","AST","3PM","STL","BLK","TOV")}
STATS.update(COMBOS)

def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x):
        raise ValueError("invalid numeric evidence")
    return x

def timestamp(x):
    t=datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.utcoffset() is None:
        raise ValueError("timezone required")
    return t

def grade(row, market, side, line):
    if market in STATS:
        value=sum(number(row[k]) for k in STATS[market])
    elif market == "ML":
        value=number(row["team_points"])-number(row["opponent_points"])
        line=0
    elif market == "SPREAD":
        value=number(row["team_points"])-number(row["opponent_points"])+line
        line=0
    elif market == "TOTAL":
        value=number(row["team_points"])+number(row["opponent_points"])
    elif market == "TEAM_TOTAL":
        value=number(row["team_points"])
    else:
        raise ValueError("unknown market")
    delta=value-line
    if side == "UNDER":
        delta=-delta
    return "PUSH" if delta==0 else "WIN" if delta>0 else "LOSS"

def summarize(grades):
    w=grades.count("WIN"); l=grades.count("LOSS"); p=grades.count("PUSH")
    return {"wins":w,"losses":l,"pushes":p,"sample":len(grades),
            "hit_rate":w/(w+l) if w+l else None}

def historical(rows, *, subject_id, opponent_id, season, cutoff, market, side, line):
    if not subject_id or not opponent_id or not season:
        raise ValueError("identity and season required")
    number(line)
    if side not in (("TEAM",) if market in ("ML","SPREAD") else ("OVER","UNDER")):
        raise ValueError("invalid market side")
    end=timestamp(cutoff)
    seen=set(); records=[]
    for row in rows:
        if row.get("subject_id") != subject_id or row.get("final") is not True:
            continue
        if row.get("season") != season or timestamp(row["settled_utc"]) >= end:
            continue
        ident=row["game_id"]
        if not ident or ident in seen:
            raise ValueError("missing or duplicate game identity")
        seen.add(ident)
        records.append((timestamp(row["settled_utc"]),row["opponent_id"],grade(row,market,side,line)))
    records.sort(reverse=True)
    results={f"L{n}":summarize([x[2] for x in records[:n]]) for n in (5,10,20)}
    results["season"]=summarize([x[2] for x in records])
    results["head_to_head_season"]=summarize([x[2] for x in records if x[1]==opponent_id])
    return {"windows":results,"decision":"HOLD","model_probability":None,"ev":None,
            "historical_source_authenticated":False,"champion_001_modified":False}
