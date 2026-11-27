"""Rank historical evidence, never substitute it for calibrated probability."""
from math import sqrt

def wilson(wins, losses):
    n=wins+losses
    if n<=0:
        return None
    p=wins/n
    z=1.96
    return (p+z*z/(2*n)-z*sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)

def rank(candidates):
    ranked=[]
    for candidate in candidates:
        windows=candidate["history"]["windows"]
        season=windows["season"]
        recent=windows["L10"]
        if season["wins"]+season["losses"]<20 or recent["wins"]+recent["losses"]<10:
            continue
        score=wilson(season["wins"],season["losses"])
        ranked.append({**candidate,"historical_rank_score":score,
                       "decision":"HOLD","model_probability":None,"ev":None})
    return sorted(ranked,key=lambda r:(r["historical_rank_score"],
        r["history"]["windows"]["L10"]["hit_rate"]),reverse=True)
