"""Independent betting arithmetic. Never substitutes market odds for model forecasts."""
import math

def american_to_decimal(odds):
    if isinstance(odds, bool) or not isinstance(odds, (int,float)) or not math.isfinite(odds) or abs(odds) < 100:
        raise ValueError("Invalid American odds")
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def break_even_probability(odds):
    return 1 / american_to_decimal(odds)

def expected_return_per_unit(probability, odds):
    if isinstance(probability, bool) or not isinstance(probability,(int,float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Model probability must be in [0,1]")
    return probability * american_to_decimal(odds) - 1

def evaluate(selection, odds, model_probability=None, model_validated=False,
             market_verified=False, roster_verified=False, injury_verified=False,
             shadow_validated=False):
    """Fail closed until *independent* forecasts and every release gate exist."""
    if not isinstance(selection,str) or not selection.strip():
        raise ValueError("Selection required")
    result={"selection":selection,"odds_american":odds,
            "break_even_probability":round(break_even_probability(odds),6),
            "status":"HOLD","certified":False}
    if model_probability is not None:
        result["model_probability"]=model_probability
        result["expected_return_per_unit"]=round(expected_return_per_unit(model_probability,odds),6)
    gates={"model_validated":model_validated,"market_verified":market_verified,
           "roster_verified":roster_verified,"injury_verified":injury_verified,
           "prospective_shadow_validated":shadow_validated}
    result["gates"]=gates
    if all(v is True for v in gates.values()) and model_probability is not None:
        result["status"]="TAKE" if result["expected_return_per_unit"] > 0 else "PASS"
        result["certified"]=result["status"]=="TAKE"
    return result
