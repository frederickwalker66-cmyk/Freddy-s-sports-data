"""Leakage-conscious NBA Elo parameter comparison for Challenger research.

Development scores choose a candidate; the final chronological holdout is
reported only once. This does NOT establish calibration or betting value.
Champion-001 and all certification gates remain untouched.
"""
import argparse
import json
import math
from pathlib import Path
from datetime import timedelta
from challenger_elo_walkforward import validate_game, K, SETTLEMENT_LAG_HOURS

CANDIDATES = (0.0, 20.0, 40.0, 60.0, 80.0)
WARMUP = 80
MIN_DEVELOPMENT = 40
MIN_HOLDOUT = 40

def score(games, home_adv):
    ratings = {}
    pending = []
    forecasts = []
    for dt in sorted({g[0] for g in games}):
        ready = [p for p in pending if p[0] <= dt]
        pending = [p for p in pending if p[0] > dt]
        for _, home, away, outcome, prob in sorted(ready):
            delta = K * (outcome - prob)
            ratings[home] = ratings.get(home, 1500.0) + delta
            ratings[away] = ratings.get(away, 1500.0) - delta
        for _, event_id, home, away, outcome in (g for g in games if g[0] == dt):
            if outcome is None:
                continue
            diff = ratings.get(home, 1500.0) + home_adv - ratings.get(away, 1500.0)
            prob = 1 / (1 + 10 ** (-diff / 400))
            forecasts.append((prob, outcome))
            pending.append((dt + timedelta(hours=SETTLEMENT_LAG_HOURS), home, away, outcome, prob))
    return forecasts

def brier(pairs):
    return sum((p-y)**2 for p,y in pairs)/len(pairs)

def run(rows):
    games = []
    seen = set()
    for row in rows:
        league, dt, event, home, away, outcome = validate_game(row)
        if league != "nba":
            continue
        if event in seen:
            raise ValueError("Duplicate NBA event")
        seen.add(event)
        games.append((dt,event,home,away,outcome))
    games.sort()
    valid_count = sum(g[-1] is not None for g in games)
    remaining = valid_count - WARMUP
    holdout_n = max(MIN_HOLDOUT, remaining // 3)
    dev_n = remaining - holdout_n
    if dev_n < MIN_DEVELOPMENT or holdout_n < MIN_HOLDOUT:
        return {"status":"INSUFFICIENT_DATA", "valid_games":valid_count,
                "certified":False, "bet_ready":False}
    scores = {adv:score(games,adv) for adv in CANDIDATES}
    development = {str(int(adv)):round(brier(pred[WARMUP:WARMUP+dev_n]),6)
                   for adv,pred in scores.items()}
    selected = min(CANDIDATES,key=lambda adv:development[str(int(adv))])
    holdout = scores[selected][WARMUP+dev_n:]
    baseline = scores[60.0][WARMUP+dev_n:]
    return {
        "status":"RESEARCH_ONLY_NOT_CALIBRATED",
        "historical_games":len(games),
        "warmup_games":WARMUP,
        "development_games":dev_n,
        "untouched_holdout_games":len(holdout),
        "development_brier_by_home_advantage":development,
        "selected_home_advantage_elo":selected,
        "selected_holdout_brier":round(brier(holdout),6),
        "original_60_holdout_brier":round(brier(baseline),6),
        "holdout_50_50_brier":round(brier([(0.5,y) for _,y in holdout]),6),
        "holdout_evaluated_only_after_selection":True,
        "historical_publication_timestamps_verified":False,
        "rosters_and_injuries_included":False,
        "sportsbook_odds_verified":False,
        "calibrated":False,"certified":False,"bet_ready":False,
        "take_count":0,"champion_001_modified":False,
        "warning":"Development-selected Elo setting is exploratory; no independent publication timestamps, calibrated probabilities, or betting certification."
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",required=True)
    parser.add_argument("--output",default="nba_elo_parameter_audit.json")
    args=parser.parse_args()
    rows=[json.loads(line) for line in Path(args.results).read_text().splitlines() if line.strip()]
    report=run(rows)
    Path(args.output).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
