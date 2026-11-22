"""Verified field-name mapping from SharpAPI schema inspection (2026-11-22).

Schema presence was observed; values, types, semantics, and provenance have NOT
been independently validated. Never promote this mapping to betting certification.
"""
from provider_adapter import assess_record

FIELD_MAP = {
    "market_id": "market_id",
    "event_id": "event_id",
    "sportsbook": "sportsbook",
    "selection": "selection",
    "decimal_odds": "odds_decimal",
    "observed_at": "price_updated_at",
    "start_time": "event_start_time",
}

def assess_sharpapi_row(raw, now=None):
    if not isinstance(raw, dict):
        return {"data_quality": "HOLD", "certification": "HOLD", "reasons": ["invalid_provider_row"]}
    reasons = []
    if raw.get("is_live") is not False:
        reasons.append("pregame_status_unverified")
    if raw.get("is_active") is not True:
        reasons.append("market_active_status_unverified")
    if raw.get("is_stale_pregame_price") is not False:
        reasons.append("provider_stale_price_flag_unverified")
    if raw.get("is_player_prop") is True:
        reasons.append("player_roster_and_prop_identity_not_verified")
    if reasons:
        return {"data_quality": "HOLD", "certification": "HOLD", "reasons": reasons}
    return assess_record(raw, FIELD_MAP, now=now)
