"""Score locked NBA prospective forecasts against later published ESPN results.

Research evaluation only. Requires a forecast artifact saved before tipoff.
Do not infer certification from score quality or artifact timestamps alone.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from challenger_elo_walkforward import validate_game

def dt(value):
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None: raise ValueError("timezone required")
    return t.astimezone(timezone.utc)

def evaluate(ledgers, results):
    outcomes={}
    for row in results:
        league,start,eid,home,away,y=validate_game(row)
        if league!="nba" or y is None:continue
        if eid in outcomes:raise ValueError("duplicate outcome event")
        outcomes[eid]=(start,home,away,y)
    accepted={}
    rejected=[]
    pending=[]
    for ledger in ledgers:
        if ledger.get("champion_001_modified") is not False or ledger.get("certified_take_count")!=0:
            raise ValueError("unsafe forecast ledger")
        for f in ledger.get("forecasts",[]):
            eid=str(f["event_id"])
            p=float(f["home_win_probability"])
            created=dt(f["forecast_created_utc"])
            start=dt(f["start_utc"])
            if not 0<p<1 or created>=start or f.get("decision")!="HOLD" or f.get("certified") is not False:
                rejected.append({"event_id":eid,"reason":"invalid pregame probability or HOLD evidence"})
                continue
            if eid not in outcomes:
                pending.append(eid)
                continue
            actual_start,home,away,y=outcomes[eid]
            if actual_start!=start:
                rejected.append({"event_id":eid,"reason":"start timestamp mismatch"})
                continue
            if eid in accepted:
                rejected.append({"event_id":eid,"reason":"duplicate scored forecast"})
                continue
            accepted[eid]={"event_id":eid,"home_team":f["home_team"],"away_team":f["away_team"],
                "forecast_created_utc":created.isoformat(),"start_utc":start.isoformat(),
                "home_win_probability":p,"actual_home_win":y,
                "brier":round((p-y)**2,8),
                "log_loss":round(-(y*math.log(p)+(1-y)*math.log(1-p)),8),
                "correct":(p>=0.5)==bool(y)}
    games=list(accepted.values())
    n=len(games)
    return {"status":"RESEARCH_ONLY_NOT_CERTIFIED","scored_games":n,
        "pending_outcomes":len(set(pending)),"rejected_forecasts":rejected,
        "brier_score":round(sum(x["brier"] for x in games)/n,8) if n else None,
        "log_loss":round(sum(x["log_loss"] for x in games)/n,8) if n else None,
        "pick_accuracy":round(sum(x["correct"] for x in games)/n,6) if n else None,
        "games":games,"champion_001_modified":False,"certified":False,
        "bet_ready":False,"take_count":0,
        "warning":"ESPN scores and workflow timestamps are not independently authenticated betting evidence."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--forecast",action="append",required=True,help="Saved pregame forecast JSON; repeat for multiple runs")
    ap.add_argument("--results",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    ledgers=[json.loads(Path(p).read_text()) for p in a.forecast]
    rows=[json.loads(s) for s in Path(a.results).read_text().splitlines() if s.strip()]
    report=evaluate(ledgers,rows)
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("games","rejected_forecasts")},indent=2))

if __name__=="__main__":main()
