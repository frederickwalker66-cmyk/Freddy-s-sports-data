"""Rank historical evidence, never substitute it for calibrated probability."""
from math import sqrt

def wilson(wins, losses):
    if any(type(v) is not int or v < 0 for v in (wins, losses)):
        raise ValueError("invalid historical counts")
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
        ranked.append({"selection":candidate.get("selection"),
                       "history":{"windows":windows},
                       "historical_rank_score":score,
                       "certified_prediction":False,"bet_ready":False,
                       "champion_001_modified":False,
                       "decision":"HOLD","model_probability":None,"ev":None})
    return sorted(ranked,key=lambda r:(r["historical_rank_score"],
        r["history"]["windows"]["L10"]["hit_rate"]),reverse=True)

def price_freshness(quote, as_of_utc):
    """Research-only gate; provider observation is not checkout authentication."""
    from v8_unified_hit_rate import timestamp
    try:
        if quote.get("sportsbook") != "draftkings":
            return "HOLD_WRONG_BOOK"
        now = timestamp(as_of_utc)
        captured = timestamp(quote["last_capture_utc"])
        published = timestamp(quote["provider_quote_utc"])
        start = timestamp(quote["start_utc"])
        if not published <= captured <= now < start:
            return "HOLD_INVALID_CHRONOLOGY"
        if (now-published).total_seconds() > 300:
            return "HOLD_STALE_PRICE"
        odds = quote["american_odds"]
        if type(odds) is not int or abs(odds) < 100:
            return "HOLD_INVALID_PRICE"
        return "FRESH_RESEARCH_ONLY"
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return "HOLD_MISSING_PRICE_EVIDENCE"
