"""Sport-agnostic pregame timeline report from validated observation snapshots.
Research only; all selections HOLD until independently certified.
"""
import argparse,json
from pathlib import Path
from pregame_timeline import timeline
SPORTS={"nba","nfl","nhl","mlb","ncaaf","ncaab","mls","uefa_champions_league"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sport",choices=sorted(SPORTS),required=True)
    p.add_argument("--input",required=True)
    p.add_argument("--output")
    args=p.parse_args()
    source=Path(args.input)
    if not source.is_file():p.error("Snapshot missing")
    rows=[];rejected=0
    for raw in source.read_text(encoding="utf8").splitlines():
        if not raw.strip():continue
        row=json.loads(raw)
        if not isinstance(row,dict) or row.get("league")!=args.sport or row.get("record_type")!="pregame_odds_observation":
            rejected+=1;continue
        start=row.get("event_start_time")
        try:tl=timeline(start) if start else {"status":"HOLD","reason":"Missing start time"}
        except (ValueError,TypeError,AttributeError):tl={"status":"HOLD","reason":"Invalid start time"}
        rows.append({"event_id":row.get("event_id"),"home_team":row.get("home_team"),
                     "away_team":row.get("away_team"),"market_type":row.get("market_type"),
                     "selection":row.get("selection"),"line":row.get("line"),
                     "odds_american":row.get("odds_american"),"source_timestamp":row.get("timestamp"),
                     "pregame_timeline":tl,"status":"HOLD","certified":False})
    out={"sport":args.sport,"status":"HOLD","certified_takes":0,"markets":rows,
         "rejected_rows":rejected,"note":"No model forecasts, injury certifications, or executable price confirmation; no wagers."}
    target=Path(args.output or f"sharp-edge-pro/output/{args.sport}_timeline.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"sport":args.sport,"observations":len(rows),"status":"HOLD","output":str(target)}))
if __name__=="__main__":main()
