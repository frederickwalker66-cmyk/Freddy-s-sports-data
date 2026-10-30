"""Independent historical Elo benchmark for Challenger-001 research only.

Never uses sportsbook odds to generate probabilities. Online pregame forecasts
are computed BEFORE updating team ratings with results; simultaneous kickoffs
are scored as one batch to avoid outcome leakage. No Champion-001 integration.
This is a diagnostic baseline, not a calibrated, bet-ready sports model.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
import json
import math
from pathlib import Path
from historical_outcomes import LEAGUES, parse_time

BINARY_LEAGUES=("nba","nfl","mlb","nhl","ncaaf","ncaab")
SOCCER_LEAGUES=("mls","uefa_champions_league")
K=20.0
HOME_ADV=60.0
MIN_GAMES=80
MIN_EVAL=30
# Conservative embargo: ESPN historical data lacks a verified final-publication time.
SETTLEMENT_LAG_HOURS=48

def validate_game(row):
    if not isinstance(row,dict) or row.get("record_type")!="historical_completed_game_research":
        raise ValueError("Only historical completed game evidence is accepted")
    if row.get("outcome_source")!="espn_public_scoreboard":raise ValueError("Unsupported outcome provenance")
    if row.get("official_league_result_verified") is not False or row.get("champion_001_modified") is not False:
        raise ValueError("Misstated evidence status")
    lg=row.get("league")
    if lg not in LEAGUES:raise ValueError("Unsupported league")
    if lg=="nba" and row.get("season_type") != 2:
        raise ValueError("NBA regular-season evidence required")
    dt=parse_time(row.get("event_start_utc"))
    home=row.get("home_team_espn_id")
    away=row.get("away_team_espn_id")
    event=row.get("espn_event_id")
    if any(not isinstance(v,str) or not v.strip() for v in (home,away,event)) or home==away:
        raise ValueError("Invalid team/event identity")
    hs,as_=row.get("home_score"),row.get("away_score")
    if any(isinstance(v,bool) or not isinstance(v,int) or not 0<=v<1000 for v in (hs,as_)):
        raise ValueError("Missing or implausible scores")
    result="home" if hs>as_ else "away" if hs<as_ else "draw"
    if row.get("result")!=result:raise ValueError("Outcome contradicts scores")
    return (lg,dt,event,home,away,1 if hs>as_ else 0 if hs<as_ else None)

def pregame_probability(home_rating,away_rating):
    return 1/(1+10**((away_rating-home_rating-HOME_ADV)/400))

def embargoed_forecasts(games, lag_hours=SETTLEMENT_LAG_HOURS):
    """Produce pregame Elo forecasts with NO score known before its embargo expires.

    Historical ESPN responses do not include a trustworthy timestamp for when
    a final became public. A 48-hour minimum delay is a conservative assumption,
    not proof of exact publication time. Do not certify these diagnostics.
    """
    if lag_hours < 24:
        raise ValueError("settlement embargo must be at least 24 hours")
    ratings=defaultdict(lambda:1500.0)
    pending=[]
    tested=[]
    excluded_ties=0
    for dt,batch_iter in groupby(games,key=lambda g:g[0]):
        # Apply only prior results safely beyond the conservative embargo.
        ready=[item for item in pending if item[0]<=dt]
        pending=[item for item in pending if item[0]>dt]
        for _,home,away,y,ph in sorted(ready,key=lambda item:(item[0],item[1],item[2])):
            delta=K*(y-ph)
            ratings[home]+=delta
            ratings[away]-=delta
        # All events at this start time see identical pre-batch information.
        for _,eid,home,away,y in batch_iter:
            if y is None:
                excluded_ties+=1
                continue
            ph=pregame_probability(ratings[home],ratings[away])
            if not 0.001<ph<0.999:
                raise ValueError("Invalid model output")
            tested.append((ph,y,dt.isoformat()))
            pending.append((dt+timedelta(hours=lag_hours),home,away,y,ph))
    return tested,excluded_ties


def evaluate(rows, min_games=MIN_GAMES, min_eval=MIN_EVAL):
    groups=defaultdict(list)
    seen=set()
    for row in rows:
        lg,dt,eid,home,away,y=validate_game(row)
        key=(lg,eid)
        if key in seen:raise ValueError("Duplicate event ID")
        seen.add(key)
        groups[lg].append((dt,eid,home,away,y))
    reports={}
    for lg in LEAGUES:
        games=sorted(groups[lg],key=lambda x:(x[0],x[1]))
        if lg in SOCCER_LEAGUES:
            reports[lg]={"historical_games":len(games),"status":"three_way_model_required",
                         "diagnostic_brier":None,"evaluation_games":0}
            continue
        n_valid=sum(y is not None for *_,y in games)
        tested,excluded_ties=embargoed_forecasts(games)
        eval_items=tested[min_games:]
        n=len(eval_items)
        brier=sum((p-y)**2 for p,y,_ in eval_items)/n if n else None
        reference=sum((0.5-y)**2 for _,y,_ in eval_items)/n if n else None
        logloss=-sum(y*math.log(p)+(1-y)*math.log(1-p) for p,y,_ in eval_items)/n if n else None
        buckets=[]
        for lo in range(0,10):
            subset=[(p,y) for p,y,_ in eval_items if lo/10<=p<(lo+1)/10 or lo==9 and p==1]
            if subset:
                buckets.append({"range":[lo/10,(lo+1)/10],"count":len(subset),
                                "predicted_home_win_rate":round(sum(p for p,_ in subset)/len(subset),4),
                                "observed_home_win_rate":round(sum(y for _,y in subset)/len(subset),4)})
        enough=n>=min_eval and len(tested)>=min_games+min_eval
        reports[lg]={
            "historical_games":len(games),"valid_binary_games":n_valid,"excluded_ties":excluded_ties,
            "warmup_games":min(min_games,len(tested)),"evaluation_games":n,
            "evaluation_window_start_utc":eval_items[0][2] if n else None,
            "evaluation_window_end_utc":eval_items[-1][2] if n else None,
            "status":"provisional_walkforward_diagnostic" if enough else "insufficient_out_of_sample_games",
            "diagnostic_brier":round(brier,5) if enough else None,
            "neutral_50_50_brier":round(reference,5) if enough else None,
            "diagnostic_logloss":round(logloss,5) if enough else None,
            "calibration_bins":buckets if enough else [],
            "calibrated_probability_model_certified":False,
            "historical_final_publication_timestamp_verified":False,
            "assumed_result_settlement_embargo_hours":SETTLEMENT_LAG_HOURS,
            "game_day_roster_or_injury_features":False,
            "bet_ready":False,
        }
    report={
        "model_name":"Challenger-001 independent Elo baseline (NOT Champion-001)",
        "mode":"historical_walkforward_research_only",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "parameters":{"elo_k":K,"home_advantage_points":HOME_ADV,
                      "warmup_games":min_games,"minimum_evaluation_games":min_eval,
                      "assumed_result_settlement_embargo_hours":SETTLEMENT_LAG_HOURS},
        "by_league":reports,
        "certified_champion_001_predictions":0,
        "certified_challenger_predictions":0,
        "positive_ev_bets_certified":0,
        "bet_ready_selections":0,
        "automated_bets_placed":0,"champion_001_modified":False,
        "warning":"Historical final publication times are unavailable; forecasts use a conservative assumed 48-hour settlement lag. Diagnostics remain exploratory, NOT verified, calibrated, or bet-ready."
    }
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--output",default="challenger_history/walkforward_diagnostic.json")
    args=p.parse_args(argv)
    rows=[json.loads(x) for x in Path(args.results).read_text(encoding="utf8").splitlines() if x.strip()]
    report=evaluate(rows)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
