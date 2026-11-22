"""Conservative odds quality gates; no prediction or wagering functionality.

Provider payloads must be normalized explicitly before these gates are used.
Unknown fields and missing provenance fail closed.
"""
from datetime import datetime, timezone

def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None

def validate_market(market, now=None, max_age_seconds=120):
    """Return (eligible, reasons). Eligible means data-quality only, never TAKE."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    if not isinstance(market, dict):
        return False, ["market_not_object"]
    required = ("market_id", "event_id", "sportsbook", "selection", "decimal_odds", "observed_at", "start_time")
    for field in required:
        if market.get(field) in (None, ""):
            reasons.append("missing_" + field)
    if str(market.get("sportsbook") or "").lower() != "draftkings":
        reasons.append("sportsbook_unverified")
    price = market.get("decimal_odds")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not (1.0 < price < 10000):
        reasons.append("invalid_decimal_odds")
    observed = _utc(market.get("observed_at"))
    start = _utc(market.get("start_time"))
    if observed is None:
        reasons.append("invalid_observation_time")
    else:
        age = (now - observed).total_seconds()
        if age < 0 or age > max_age_seconds:
            reasons.append("stale_or_future_quote")
    if start is None or start <= now:
        reasons.append("event_not_confirmed_pregame")
    if market.get("player_id") and not market.get("team_id"):
        reasons.append("player_team_unverified")
    return not reasons, reasons

def certification_status(market, now=None):
    """Data validation cannot certify independently calibrated model EV."""
    valid, reasons = validate_market(market, now=now)
    return {"data_quality": "PASS" if valid else "HOLD",
            "certification": "HOLD",
            "reasons": reasons if reasons else ["model_probability_and_injury_gates_not_verified"]}
