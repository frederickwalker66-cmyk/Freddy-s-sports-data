"""Stages 11-15 consolidated NBA research board; fail-closed on absent evidence."""
import argparse,json,math,os
from pathlib import Path

def board(accuracy, forecasts, props, odds):
    n=accuracy.get("scored_games",0)
    valid_perf=n>=200 and accuracy.get("brier_score") is not None and accuracy.get("baseline_50_50_brier") is not None and accuracy["brier_score"]<accuracy["baseline_50_50_brier"]
    markets=[]
    for f in forecasts.get("forecasts",[]):
        for side in ("home","away"):
            markets.append({"event_id":f["event_id"],"matchup":f["away_team"]+" @ "+f["home_team"],
                "market":"moneyline","selection":f[side+"_team"] if side+"_team" in f else f["home_team"] if side=="home" else f["away_team"],
                "research_probability":f[side+"_win_probability"],"sportsbook_odds":None,
                "expected_value":None,"decision":"HOLD","reason":"Authenticated timestamped odds and independent calibration not established"})
    # Player props and sportsbook records must be real, structured and verified; never fabricate them.
    props_schema=props.get("schema_valid") is True and props.get("kind")=="props" and bool(props.get("records"))
    odds_schema=odds.get("schema_valid") is True and odds.get("kind")=="odds" and bool(odds.get("records"))
    stages={
      "11":{"name":"Prospective accuracy","status":"RESEARCH" if n else "PENDING","scored_games":n,
            "accuracy":accuracy.get("pick_accuracy"),"brier":accuracy.get("brier_score"),"baseline_brier":accuracy.get("baseline_50_50_brier"),"exploratory_baseline_beaten":valid_perf},
      "12":{"name":"Player props and combos","status":"HOLD_SCHEMA_VALIDATED_AUTHENTICITY_UNVERIFIED" if props_schema else "HOLD_MISSING_VERIFIED_PROPS"},
      "13":{"name":"Sportsbook prices and EV","status":"HOLD_SCHEMA_VALIDATED_AUTHENTICITY_UNVERIFIED" if odds_schema else "HOLD_MISSING_VERIFIED_ODDS"},
      "14":{"name":"Sharp Edge independent certification","status":"HOLD","certified_take_count":0},
      "15":{"name":"Unified market display","status":"RESEARCH_DISPLAY_READY","markets":markets,
            "unavailable_categories":["spreads","totals","points","rebounds","assists","PR","PA","RA","PRA"]}}
    return {"model":"Challenger-001","status":"RESEARCH_ONLY","stages":stages,
      "champion_001_modified":False,"certified":False,"bet_ready":False,"take_count":0,
      "note":"Stage 11's 200-game threshold is an exploratory monitoring checkpoint, not certification. No market implied probabilities substituted for model estimates."}

def main():
    p=argparse.ArgumentParser()
    for x in ("accuracy","forecasts","output"):p.add_argument("--"+x,required=True)
    p.add_argument("--props");p.add_argument("--odds")
    a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text()) if path and Path(path).exists() else {}
    result=board(read(a.accuracy),read(a.forecasts),read(a.props),read(a.odds))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    summary=["## Freddy's Picks AI — Stages 11–15","",
        "| Stage | Component | Status |","|---|---|---|"]
    for k,v in result["stages"].items():summary.append(f"| {k} | {v['name']} | {v['status']} |")
    summary+=["",f"**Scored games:** {result['stages']['11']['scored_games']}",
        f"**Brier:** {result['stages']['11']['brier']} | **50/50 baseline:** {result['stages']['11']['baseline_brier']}",
        f"**Research moneyline forecasts:** {len(result['stages']['15']['markets'])}",
        "**Sharp Edge:** HOLD | **Champion-001:** Frozen | **Certified TAKE:** 0",
        "No fabricated player props, sportsbook prices, or expected values."]
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write("\n".join(summary)+"\n")
    print("\n".join(summary))
if __name__=="__main__":main()
