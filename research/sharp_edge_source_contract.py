"""Source-contract checks for independent Sharp Edge feed integration.

These checks validate structure and consistency only; they do NOT authenticate
provider signatures, model execution, odds, or event roster information.
"""
from datetime import datetime, timezone
from math import isfinite


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None


def validate_pair(quote, forecast, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    issues = []
    if not isinstance(quote, dict) or not isinstance(forecast, dict):
        return {"ready_for_authentication": False, "issues": ["invalid_record_type"],
                "certified": False, "decision": "HOLD"}
    keys = ("event_id", "market", "selection_id")
    for key in keys:
        if not quote.get(key) or quote.get(key) != forecast.get(key):
            issues.append("market_identity_mismatch:" + key)
    if not quote.get("sportsbook") or not quote.get("provider_record_id"):
        issues.append("missing_sportsbook_provenance")
    odds = quote.get("american_odds")
    if type(odds) is not int or (-100 < odds < 100):
        issues.append("invalid_american_odds")
    observed = _timestamp(quote.get("observed_at"))
    predicted = _timestamp(forecast.get("predicted_at"))
    event_start = _timestamp(quote.get("event_start_at"))
    if observed is None or not 0 <= (now - observed).total_seconds() <= 900:
        issues.append("stale_future_or_missing_quote")
    if predicted is None or predicted > now:
        issues.append("invalid_forecast_timestamp")
    if event_start is None or event_start <= now:
        issues.append("event_already_started_or_unknown")
    if forecast.get("model_id") != "Champion-001":
        issues.append("not_frozen_champion_001")
    p = forecast.get("model_probability")
    if type(p) not in (float, int) or not isfinite(p) or not 0 < p < 1:
        issues.append("invalid_native_probability")
    if not forecast.get("forecast_run_id") or not forecast.get("model_artifact_sha256"):
        issues.append("missing_model_provenance")
    if not quote.get("source_signature") or not forecast.get("source_signature"):
        issues.append("missing_provider_or_model_signature")
    return {
        "ready_for_authentication": not issues,
        "issues": issues,
        "certified": False,
        "decision": "HOLD",
        "authentication_status": "NOT_AUTHENTICATED_BY_SCHEMA_VALIDATION",
        "next_step": "Verify provider signatures and trusted model artifact provenance out of band",
    }
