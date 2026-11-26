"""Grade observed game results, never claim bookmaker settlement."""
import math

def grade_prop(value, target, final=False):
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (value,target)):
        return {"status":"UNKNOWN","remaining":None}
    remaining=max(0,target-value)
    return {"status":("WIN" if remaining==0 else "LOSS") if final else
            ("TARGET_MET" if remaining==0 else "IN_PROGRESS"),
            "observed":value,"remaining":remaining,"sportsbook_verified":False}

def grade_spread(team_score, opponent_score, spread, final=False):
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (team_score,opponent_score,spread)):
        return {"status":"UNKNOWN","adjusted_margin":None}
    margin=team_score-opponent_score+spread
    status=("WIN" if margin>0 else "LOSS" if margin<0 else "PUSH") if final else (
        "COVERING" if margin>0 else "NOT_COVERING" if margin<0 else "PUSH_POSITION")
    return {"status":status,"adjusted_margin":margin,"sportsbook_verified":False}
