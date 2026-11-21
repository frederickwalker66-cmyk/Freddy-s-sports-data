"""Unified NBA command for Sharp Edge Pro; never invents picks."""
import argparse
import json
import sys
from pathlib import Path

FAMILIES = {
    "spreads": {"point_spread"},
    "moneylines": {"moneyline"},
    "totals_over_under": {"total_points", "total_game_points"},
    "points": {"player_points"},
    "rebounds": {"player_rebounds"},
    "assists": {"player_assists"},
    "threes": {"player_threes", "player_three_pointers"},
    "combos_pra": {"player_points_rebounds_assists"},
    "combos_pr": {"player_points_rebounds"},
    "combos_pa": {"player_points_assists"},
    "combos_ra": {"player_rebounds_assists"},
}
def classify(row):
    market=str(row.get("market_type","")).lower()
    for label,values in FAMILIES.items():
        if market in values:
            return label
    if market.startswith("total_"):
        return "totals_over_under"
    if market.startswith("player_"):
        return "other_player_props"
    return "other_markets"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",help="Existing, timestamped SharpAPI JSONL file; no network calls")
    p.add_argument("--output",default="sharp-edge-pro/output/nba_all.json")
    args=p.parse_args()
    groups={k:[] for k in (*FAMILIES,"other_player_props","other_markets")}
    rejected=0
    if args.input:
        source=Path(args.input)
        if not source.is_file():
            p.error("Input snapshot not found")
        for line in source.read_text(encoding="utf8").splitlines():
            if not line.strip():continue
            row=json.loads(line)
            if not isinstance(row,dict) or row.get("league")!="nba" or row.get("record_type")!="pregame_odds_observation":
                rejected+=1
                continue
            item={k:row.get(k) for k in ("event_id","home_team","away_team","market_type","selection","selection_type","player_name","player_id","line","odds_american","timestamp","recorded_at")}
            item.update(status="HOLD",certified=False,model_probability=None,reason="Independent forecast, live roster/injury and executable odds not certified")
            groups[classify(row)].append(item)
    result={"command":"run nba","status":"HOLD","certified_takes":0,
            "input_snapshot":args.input,"rejected_non_nba_or_invalid":rejected,
            "markets":groups,"sharp_edge":{"status":"UNVERIFIED","qualified_bets":[],"reason":"No independently validated model edge and executable sportsbook price"},"reverse_line_movement":{"status":"UNVERIFIED","reason":"Requires timestamped opening/current same-book lines and verified public bet splits"},"sharp_money":{"status":"UNVERIFIED","reason":"Requires source-backed public handle and bet percentages"},"team_leans":{"status":"NONE_VERIFIED","leans":[],"reason":"No independent model team-side probabilities"},"note":"Research observations only. Missing markets are not fabricated. No wagers placed."}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"command":"run nba","status":"HOLD","certified_takes":0,
                      "market_counts":{k:len(v) for k,v in groups.items()},
                      "output":str(out)},indent=2))
if __name__=="__main__":
    main()
