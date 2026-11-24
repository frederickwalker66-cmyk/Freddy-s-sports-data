"""Exploratory Challenger NBA probability calibration audit; no betting certification.

IMPORTANT: Earlier parameter selection examined this same historical holdout.
Therefore these scores are NOT an independent confirmation. Obtain a future
untouched prospective sample before promoting any probability transform.
"""
import argparse
import json
import math
from pathlib import Path
from challenger_elo_walkforward import validate_game
from research.nba_elo_parameter_audit import score, WARMUP

HOME_ADV = 20.0  # candidate chosen in earlier parameter audit
MIN_DEV = 40
MIN_TEST = 40
SLOPES = (0.5, 0.75, 1.0, 1.25, 1.5)
INTERCEPTS = (-0.4, -0.2, 0.0, 0.2, 0.4)

def transform(p, slope, intercept):
    p = min(1-1e-9, max(1e-9, p))
    z = slope * math.log(p/(1-p)) + intercept
    return 1/(1+math.exp(-z))

def brier(items):
    return sum((p-y)**2 for p,y in items)/len(items)

def log_loss(items):
    return -sum(y*math.log(max(1e-9,p))+(1-y)*math.log(max(1e-9,1-p)) for p,y in items)/len(items)

def run(rows):
    games, seen = [], set()
    for row in rows:
        league, dt, eid, home, away, y = validate_game(row)
        if league != "nba":
            continue
        if eid in seen:
            raise ValueError("duplicate NBA event")
        seen.add(eid)
        games.append((dt,eid,home,away,y))
    games.sort()
    predictions = score(games,HOME_ADV)
    n = len(predictions)-WARMUP
    holdout_n = max(MIN_TEST,n//3)
    development_n = n-holdout_n
    base = {"status":"INSUFFICIENT_DATA","certified":False,"bet_ready":False,
            "champion_001_modified":False,"take_count":0}
    if development_n < MIN_DEV or holdout_n < MIN_TEST:
        return dict(base, historical_games=len(games), forecast_count=len(predictions))
    dev = predictions[WARMUP:WARMUP+development_n]
    test = predictions[WARMUP+development_n:]
    choices = [(brier([(transform(p,s,i),y) for p,y in dev]),s,i)
               for s in SLOPES for i in INTERCEPTS]
    _,slope,intercept = min(choices)
    calibrated_dev = [(transform(p,slope,intercept),y) for p,y in dev]
    calibrated_test = [(transform(p,slope,intercept),y) for p,y in test]
    return {
        "status":"EXPLORATORY_REUSED_HOLDOUT_NOT_CERTIFIED",
        "historical_games":len(games),"warmup_games":WARMUP,
        "development_games":development_n,"holdout_games":len(test),
        "home_advantage_elo":HOME_ADV,
        "selected_calibration_logit_slope":slope,
        "selected_calibration_logit_intercept":intercept,
        "development_raw_brier":round(brier(dev),6),
        "development_transformed_brier":round(brier(calibrated_dev),6),
        "holdout_raw_brier":round(brier(test),6),
        "holdout_transformed_brier":round(brier(calibrated_test),6),
        "holdout_raw_log_loss":round(log_loss(test),6),
        "holdout_transformed_log_loss":round(log_loss(calibrated_test),6),
        "holdout_reused_from_prior_parameter_audit":True,
        "fresh_prospective_validation_required":True,
        "production_model_updated":False,
        "historical_publication_timestamps_verified":False,
        "sportsbook_odds_verified":False,
        "roster_injury_features_verified":False,
        "calibrated_probability_model_certified":False,
        "certified":False,"bet_ready":False,"take_count":0,
        "champion_001_modified":False,
        "warning":"Calibration experiment only. Previously inspected holdout cannot certify the transform; do not publish TAKE or positive EV."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--results",required=True)
    ap.add_argument("--output",default="nba_research/calibration_audit.json")
    a=ap.parse_args()
    rows=[json.loads(x) for x in Path(a.results).read_text().splitlines() if x.strip()]
    result=run(rows)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
