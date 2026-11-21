"""Independent, transparent sharp-market diagnostics. No invented handle or bet percentages."""
import math

def implied_probability(american):
    if isinstance(american,bool) or not isinstance(american,(int,float)) or not math.isfinite(american) or abs(american)<100:
        raise ValueError("invalid odds")
    return 100/(american+100) if american>0 else abs(american)/(abs(american)+100)

def evaluate_market(opening, current, public_bet_pct=None, public_money_pct=None, sharp_book=None):
    """opening/current: dict(side,line,odds_american,timestamp,book).
    RLM requires documented public bet majority against the observed line move.
    Without independently sourced public splits, direction alone is NOT reverse-line movement.
    """
    for snap in (opening,current):
        if not isinstance(snap,dict) or not all(k in snap for k in ("side","line","odds_american","timestamp","book")):
            raise ValueError("incomplete market snapshot")
        implied_probability(snap["odds_american"])
    if opening["side"]!=current["side"] or opening["book"]!=current["book"]:
        raise ValueError("cannot compare different sides/books")
    if not isinstance(opening["line"],(int,float)) or not isinstance(current["line"],(int,float)):
        raise ValueError("numeric lines required")
    movement=current["line"]-opening["line"]
    report={"side":current["side"],"book":current["book"],"opening_line":opening["line"],
            "current_line":current["line"],"line_movement":movement,
            "opening_odds":opening["odds_american"],"current_odds":current["odds_american"],
            "opening_timestamp":opening["timestamp"],"current_timestamp":current["timestamp"],
            "public_bet_pct":public_bet_pct,"public_money_pct":public_money_pct,
            "reverse_line_movement":"UNVERIFIED","sharp_money":"UNVERIFIED",
            "team_lean":"NONE_VERIFIED","bet_status":"HOLD"}
    if public_bet_pct is not None:
        if isinstance(public_bet_pct,bool) or not isinstance(public_bet_pct,(int,float)) or not 0<=public_bet_pct<=100:
            raise ValueError("invalid public bet percentage")
        # Spread/total signs and selections vary by provider; never infer which side the
        # public favors from raw signed lines without a canonical market-side crosswalk.
        report["reverse_line_movement"]="REQUIRES_CANONICAL_SIDE_AND_SPLIT_PROVENANCE"
    if public_money_pct is not None:
        if isinstance(public_money_pct,bool) or not isinstance(public_money_pct,(int,float)) or not 0<=public_money_pct<=100:
            raise ValueError("invalid public money percentage")
        report["sharp_money"]="MONEY_SPLIT_REQUIRES_SOURCE_VERIFICATION"
    return report
