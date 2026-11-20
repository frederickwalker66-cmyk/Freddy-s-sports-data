"""Offline, point-in-time backtest for NBA three-point prop strategy.
Input CSV columns: game_id,player,opponent,tipoff_utc,observed_at_utc,
line,actual_3pm,last5_hits,last10_hits,last5_games,last10_games,
opponent_3pm_allowed_rank,player_3pm_rank,minutes_verified,injury_verified,
odds_american,odds_timestamp,source,native_probability.
Only pregame features and quotes are eligible. Never invent missing data.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from research.tiktok_three_point_strategy import ThreePointCandidate, evaluate

def dt(s):
    value=datetime.fromisoformat(s.replace("Z","+00:00"))
    if value.tzinfo is None: raise ValueError("Timezone required")
    return value.astimezone(timezone.utc)

def optional_int(s):
    return int(s) if s not in ("",None) else None

def optional_float(s):
    return float(s) if s not in ("",None) else None

def backtest(rows):
    records=[]
    for row in rows:
        try:
            tip=dt(row["tipoff_utc"])
            observed=dt(row["observed_at_utc"])
            quote=dt(row["odds_timestamp"]) if row.get("odds_timestamp") else None
            if observed >= tip or (quote and quote >= tip):
                records.append({"game_id":row.get("game_id"),"player":row.get("player"),"status":"QUARANTINE_POST_TIP"});continue
            c=ThreePointCandidate(
                player=row["player"],opponent=row["opponent"],line=float(row["line"]),
                last5_hits=int(row["last5_hits"]),last10_hits=int(row["last10_hits"]),
                last5_games=int(row["last5_games"]),last10_games=int(row["last10_games"]),
                opponent_3pm_allowed_rank=optional_int(row.get("opponent_3pm_allowed_rank")),
                player_3pm_rank=optional_int(row.get("player_3pm_rank")),
                minutes_verified=row["minutes_verified"].lower()=="true",
                injury_verified=row["injury_verified"].lower()=="true",
                odds_american=optional_int(row.get("odds_american")),
                native_probability=optional_float(row.get("native_probability")),
                odds_timestamp=row.get("odds_timestamp"),source=row.get("source"))
            result=evaluate(c)
            result.update(game_id=row["game_id"],tipoff_utc=row["tipoff_utc"],
                          actual_3pm=int(row["actual_3pm"]),
                          won=int(row["actual_3pm"])>c.line,
                          status="RESEARCH_GRADED")
            records.append(result)
        except (KeyError,TypeError,ValueError) as exc:
            records.append({"game_id":row.get("game_id"),"player":row.get("player"),
                            "status":"QUARANTINE_INVALID_DATA","reason":str(exc)})
    graded=[r for r in records if r["status"]=="RESEARCH_GRADED"]
    eligible=[r for r in graded if r["historical_90"] and r["defense_top10"] and r["shooter_top10"]]
    return {"total_rows":len(records),"graded_rows":len(graded),
            "quarantined_rows":len(records)-len(graded),
            "strategy_eligible_rows":len(eligible),
            "eligible_wins":sum(r["won"] for r in eligible),
            "eligible_empirical_hit_rate":sum(r["won"] for r in eligible)/len(eligible) if eligible else None,
            "certified_bets":0,"records":records}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    with open(a.input,newline="") as f: result=backtest(csv.DictReader(f))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="records"}))

if __name__=="__main__": main()
