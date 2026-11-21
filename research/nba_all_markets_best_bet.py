"""Permanent NBA all-market Best Bet board; no fabricated model signals."""
from datetime import datetime, timezone
from math import isfinite
import json

MARKETS = ("moneyline","spread","game_total_over","game_total_under",
           "player_points_over","player_points_under","player_rebounds_over",
           "player_rebounds_under","player_assists_over","player_assists_under",
           "player_threes_over","player_threes_under","player_pra_over",
           "player_pra_under","player_pr_over","player_pr_under",
           "player_pa_over","player_pa_under","player_ra_over","player_ra_under")

def evaluate(markets, *, champion_verified=False, draftkings_verified=False,
             odds_integrity_verified=False, calibration_verified=False):
    out=[]
    for item in markets:
        market=item.get("market","")
        p=item.get("champion_probability")
        decimal=item.get("decimal_odds")
        receipts=item.get("receipts") or {}
        valid=(market in MARKETS and all((champion_verified,draftkings_verified,
              odds_integrity_verified,calibration_verified))
              and isinstance(p,(float,int)) and not isinstance(p,bool)
              and isinstance(decimal,(float,int)) and not isinstance(decimal,bool)
              and isfinite(p) and isfinite(decimal) and 0<p<1 and decimal>1
              and all(isinstance(receipts.get(k),str) and receipts[k].strip()
              for k in ("model","odds","timestamp","roster","injury")))
        ev=round(p*decimal-1,6) if valid else None
        decision="TAKE" if valid and ev>0 else "PASS" if valid else "HOLD"
        out.append({"selection":item.get("selection",""),"market":market,
                    "decision":decision,"expected_value":ev,
                    "champion_probability":p if valid else None,
                    "reason":"VERIFIED_POSITIVE_EV" if decision=="TAKE" else
                    "VERIFIED_NONPOSITIVE_EV" if decision=="PASS" else
                    "UNVERIFIED_SOURCE_OR_MODEL"})
    takes=sorted((x for x in out if x["decision"]=="TAKE"),
                 key=lambda x:x["expected_value"],reverse=True)
    return {"generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "best_bet":takes[0] if takes else None,
            "best_bet_status":"TAKE" if takes else "HOLD_NO_CERTIFIED_BEST_BET",
            "categories":list(MARKETS),"markets":out,
            "take_count":len(takes),
            "pass_count":sum(x["decision"]=="PASS" for x in out),
            "hold_count":sum(x["decision"]=="HOLD" for x in out)}

if __name__=="__main__":
    print(json.dumps(evaluate([]),sort_keys=True))
