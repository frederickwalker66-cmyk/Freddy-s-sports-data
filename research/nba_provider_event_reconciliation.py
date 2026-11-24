"""Reconcile provider event identity to ESPN forecasts, without guessing crosswalks."""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone

def stamp(value):
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("timezone required")
    return d.astimezone(timezone.utc)

def reconcile(forecasts,provider):
    events={}
    for f in forecasts.get("forecasts",[]):
        if not all(f.get(k) for k in ("event_id","home_team_espn_id","away_team_espn_id","start_utc")):
            continue  # Legacy forecast artifacts lack identity IDs; cannot safely join
        events[str(f["event_id"])]=f
    accepted=[];rejected=[]
    for r in provider.get("records",[]):
        # Only an explicit provider-supplied ESPN crosswalk can establish event identity.
        eid=str(r.get("espn_event_id",""))
        f=events.get(eid)
        reason=None
        if not f:reason="missing explicit ESPN event ID or matching forecast"
        elif str(r.get("home_team_espn_id",""))!=str(f["home_team_espn_id"]) or str(r.get("away_team_espn_id",""))!=str(f["away_team_espn_id"]):
            reason="ESPN home/away team ID mismatch"
        elif stamp(r["event_start_utc"])!=stamp(f["start_utc"]):
            reason="event start mismatch"
        elif stamp(r["observed_at_utc"])>=stamp(f["start_utc"]):
            reason="not a pregame snapshot"
        if reason:rejected.append({"provider_event_id":r.get("provider_event_id"),"reason":reason})
        else:accepted.append({"espn_event_id":eid,"provider_event_id":r["provider_event_id"],"market":r["market"],"status":"MATCHED_RESEARCH_ONLY"})
    return {"accepted":accepted,"rejected":rejected,"matched_count":len(accepted),"rejected_count":len(rejected),
            "certified":False,"decision":"HOLD","crosswalk_independently_authenticated":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forecasts",required=True);p.add_argument("--provider",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    report=reconcile(json.loads(Path(a.forecasts).read_text()),json.loads(Path(a.provider).read_text()))
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"matched":report["matched_count"],"rejected":report["rejected_count"],"decision":"HOLD"}))
if __name__=="__main__":main()
