"""Stages 11-15 consolidated NBA research board; fail-closed on absent evidence."""
import argparse,json,math,os
from datetime import datetime,timezone
from pathlib import Path

def professional_market_review(probability, american_odds, independently_validated=False):
    """Research pricing; never grants betting certification."""
    if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
        return {"decision": "HOLD", "reason": "Missing or invalid model probability"}
    if isinstance(american_odds, bool) or not isinstance(american_odds, (int, float)) or not math.isfinite(american_odds) or -100 < american_odds < 100:
        return {"decision": "HOLD", "reason": "Missing or invalid verified sportsbook odds"}
    decimal = 1 + (100 / abs(american_odds) if american_odds < 0 else american_odds / 100)
    break_even = 1 / decimal
    ev = probability * decimal - 1
    return {
        "break_even_probability": round(break_even, 6),
        "estimated_ev_per_unit": round(ev, 6),
        "edge_percentage_points": round(100 * (probability - break_even), 3),
        "decision": "PASS" if independently_validated and ev <= 0 else "HOLD",
        "reason": "Research edge is not independent certification" if ev > 0 else "Nonpositive estimated edge" if independently_validated else "Unverified probability or odds"
    }

def board(accuracy, forecasts, props, odds, reconciled_props=None, reconciled_odds=None):
    reconciled_props = reconciled_props or {}
    reconciled_odds = reconciled_odds or {}
    n=accuracy.get("scored_games",0)
    valid_perf=n>=200 and accuracy.get("brier_score") is not None and accuracy.get("baseline_50_50_brier") is not None and accuracy["brier_score"]<accuracy["baseline_50_50_brier"]
    markets=[]
    expired_forecasts=0
    now=datetime.now(timezone.utc)
    for f in forecasts.get("forecasts",[]):
        try:
            start=datetime.fromisoformat(f["start_utc"].replace("Z","+00:00"))
            if start.tzinfo is None or start<=now:
                expired_forecasts+=1
                continue
        except (KeyError,ValueError,TypeError):
            expired_forecasts+=1
            continue
        for side in ("home","away"):
            markets.append({"event_id":f["event_id"],"matchup":f["away_team"]+" @ "+f["home_team"],
                "market":"moneyline","selection":f[side+"_team"] if side+"_team" in f else f["home_team"] if side=="home" else f["away_team"],
                "research_probability":f[side+"_win_probability"],"sportsbook_odds":None,
                "professional_review":professional_market_review(f[side+"_win_probability"], None),
                "expected_value":None,"decision":"HOLD","reason":"Authenticated timestamped odds and independent calibration not established"})
    # Player props and sportsbook records must be real, structured and verified; never fabricate them.
    props_schema=props.get("schema_valid") is True and props.get("kind")=="props" and bool(props.get("records"))
    odds_schema=odds.get("schema_valid") is True and odds.get("kind")=="odds" and bool(odds.get("records"))
    matched_props = reconciled_props.get('matched_count', 0)
    matched_odds = reconciled_odds.get('matched_count', 0)
    # Reconciliation is not authentication; never promote unmatched or unsigned records.
    stages={
      "11":{"name":"Prospective accuracy","status":"RESEARCH" if n else "PENDING","scored_games":n,
            "accuracy":accuracy.get("pick_accuracy"),"brier":accuracy.get("brier_score"),"baseline_brier":accuracy.get("baseline_50_50_brier"),"exploratory_baseline_beaten":valid_perf},
      "12":{"name":"Player props and combos","validated_records":props.get('record_count',0),"matched_records":matched_props,"status":"HOLD_SCHEMA_VALIDATED_AUTHENTICITY_UNVERIFIED" if props_schema else "HOLD_MISSING_VERIFIED_PROPS"},
      "13":{"name":"Sportsbook prices and EV","validated_records":odds.get('record_count',0),"matched_records":matched_odds,"status":"HOLD_SCHEMA_VALIDATED_AUTHENTICITY_UNVERIFIED" if odds_schema else "HOLD_MISSING_VERIFIED_ODDS"},
      "14":{"name":"Sharp Edge independent certification","status":"HOLD","certified_take_count":0},
      "15":{"name":"Unified market display","status":"RESEARCH_DISPLAY_READY" if markets else "HOLD_NO_FUTURE_FIXTURES","expired_forecasts_filtered":expired_forecasts,"markets":markets,
            "unavailable_categories":["spreads","totals","points","rebounds","assists","PR","PA","RA","PRA"]}}
    return {"model":"Challenger-001","status":"RESEARCH_ONLY","stages":stages,
      "champion_001_modified":False,"certified":False,"bet_ready":False,"take_count":0,
      "risk_policy":{"independent_probability_required":True,"timestamped_odds_required":True,"positive_ev_required":True,"parlays_require_joint_probability":True,"automatic_staking_enabled":False},
      "note":"Stage 11's 200-game threshold is an exploratory monitoring checkpoint, not certification. No market implied probabilities substituted for model estimates."}

def main():
    p=argparse.ArgumentParser()
    for x in ("accuracy","forecasts","output"):p.add_argument("--"+x,required=True)
    p.add_argument("--props");p.add_argument("--odds")
    p.add_argument("--reconciled-props");p.add_argument("--reconciled-odds")
    a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text()) if path and Path(path).exists() else {}
    result=board(read(a.accuracy),read(a.forecasts),read(a.props),read(a.odds),read(a.reconciled_props),read(a.reconciled_odds))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+"\n")
    summary=["## Freddy's Picks AI — Stages 11–15","",
        "| Stage | Component | Status |","|---|---|---|"]
    for k,v in result["stages"].items():summary.append(f"| {k} | {v['name']} | {v['status']} |")
    summary += ["", f"**Player props:** {result['stages']['12']['validated_records']} schema-valid, {result['stages']['12']['matched_records']} event-matched", f"**DraftKings odds:** {result['stages']['13']['validated_records']} schema-valid, {result['stages']['13']['matched_records']} event-matched"]
    summary+=["",f"**Scored games:** {result['stages']['11']['scored_games']}",
        f"**Brier:** {result['stages']['11']['brier']} | **50/50 baseline:** {result['stages']['11']['baseline_brier']}",
        f"**Future research moneyline selections:** {len(result['stages']['15']['markets'])} | **Expired forecasts filtered:** {result['stages']['15']['expired_forecasts_filtered']}",
        "**Sharp Edge:** HOLD | **Champion-001:** Frozen | **Certified TAKE:** 0",
        "No fabricated player props, sportsbook prices, or expected values."]
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write("\n".join(summary)+"\n")
    print("\n".join(summary))
if __name__=="__main__":main()
