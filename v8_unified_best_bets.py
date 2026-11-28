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

def reverse_edge(previous, current, splits, as_of_utc):
    """Price-only reverse movement on the identical selection; not sharp proof."""
    from v8_unified_hit_rate import timestamp
    from math import isfinite
    result={"signal":False,"decision":"HOLD","model_probability":None,"ev":None}
    try:
        keys=("sportsbook","event_id","market_id","selection_id","line","start_utc")
        if any(k not in previous or k not in current or k not in splits
               or previous[k]!=current[k] or current[k]!=splits[k] for k in keys):
            return dict(result,reason="market_identity_mismatch")
        if price_freshness(current,as_of_utc)!="FRESH_RESEARCH_ONLY":
            return dict(result,reason="current_price_unverified")
        old=timestamp(previous["provider_quote_utc"])
        new=timestamp(current["provider_quote_utc"])
        split=timestamp(splits["observed_utc"])
        if not 0<(new-old).total_seconds()<=3600 or abs((new-split).total_seconds())>60 or split>timestamp(as_of_utc):
            return dict(result,reason="unsynchronized_observations")
        tickets=splits["ticket_pct"]
        if type(tickets) not in (int,float) or not isfinite(tickets) or not 0<=tickets<=100:
            return dict(result,reason="invalid_ticket_share")
        def implied(a):
            if type(a) is not int or abs(a)<100:
                raise ValueError("invalid odds")
            return -a/(100-a) if a<0 else 100/(100+a)
        delta=implied(current["american_odds"])-implied(previous["american_odds"])
        return dict(result,signal=tickets<50 and delta>0,
                    implied_price_change=delta,reason="research_only_not_sharp_proof")
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
        return dict(result,reason="missing_or_invalid_evidence")
