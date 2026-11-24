"""Validate external NBA props and sportsbook snapshots without inventing evidence.

Inputs are provider-exported JSON documents; no secrets are stored here.
A validated schema is NOT independent certification.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

def utc(v):
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("timezone offset required")
    return d.astimezone(timezone.utc)

def validate(payload,kind):
    if not isinstance(payload,dict) or not isinstance(payload.get("records"),list):
        raise ValueError("provider payload must contain records array")
    seen=set();out=[]
    for row in payload["records"]:
        if not isinstance(row,dict):raise ValueError("invalid record")
        required=["provider","provider_event_id","event_start_utc","observed_at_utc","home_team_id","away_team_id"]
        if kind=="props":required+=["player_id","market","line","stat_window","sample_size"]
        else:required+=["sportsbook","market","selection","american_odds"]
        if any(row.get(k) is None or row.get(k)=="" for k in required):raise ValueError("missing "+kind+" fields")
        start,observed=utc(row["event_start_utc"]),utc(row["observed_at_utc"])
        if observed>=start:raise ValueError("non-pregame record")
        if str(row["home_team_id"])==str(row["away_team_id"]):raise ValueError("invalid team identity")
        if kind=="props":
            if row["market"] not in ("points","rebounds","assists","PR","PA","RA","PRA"):raise ValueError("unsupported prop market")
            if type(row["sample_size"]) is not int or row["sample_size"]<1:raise ValueError("invalid sample size")
            if not isinstance(row["line"],(int,float)) or isinstance(row["line"],bool):raise ValueError("invalid prop line")
        else:
            if row["sportsbook"].lower()!="draftkings":raise ValueError("not DraftKings")
            if type(row["american_odds"]) is not int or -100<row["american_odds"]<100:raise ValueError("invalid American odds")
        key=tuple(str(row[k]) for k in required if k not in ("observed_at_utc","american_odds","line","stat_window","sample_size"))
        if key in seen:raise ValueError("duplicate provider record")
        seen.add(key);out.append(row)
    return {"kind":kind,"records":out,"schema_valid":True,"record_count":len(out),
            "independently_authenticated":False,"certified":False,"decision":"HOLD",
            "warning":"Schema and chronology validation do not prove provider authenticity or independently timestamp data."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kind",choices=("props","odds"),required=True)
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=validate(json.loads(Path(a.input).read_text()),a.kind)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"kind":a.kind,"records":result["record_count"],"decision":"HOLD"}))
if __name__=="__main__":main()
