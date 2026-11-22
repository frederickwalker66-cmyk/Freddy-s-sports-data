"""Strict SharpAPI record adapter.

No undocumented SharpAPI fields are assumed. A mapping must be supplied after
the actual provider schema has been inspected and approved. Missing fields HOLD.
"""
from datetime import datetime, timezone
from typing import Mapping
from market_quality import certification_status

REQUIRED = ("market_id", "event_id", "sportsbook", "selection",
            "decimal_odds", "observed_at", "start_time")

def normalize_record(raw, field_map):
    """Map provider fields to canonical fields, refusing guessed or absent values."""
    if not isinstance(raw, dict) or not isinstance(field_map, dict):
        return None, ["invalid_record_or_mapping"]
    if any(not isinstance(field_map.get(k), str) or not field_map[k] for k in REQUIRED):
        return None, ["incomplete_provider_field_mapping"]
    missing = [key for key in REQUIRED if field_map[key] not in raw or raw[field_map[key]] is None]
    if missing:
        return None, ["provider_field_missing:" + ",".join(missing)]
    normalized = {key: raw[field_map[key]] for key in REQUIRED}
    for optional in ("player_id", "team_id"):
        if optional in field_map:
            if not isinstance(field_map[optional], str):
                return None, ["invalid_optional_mapping"]
            normalized[optional] = raw.get(field_map[optional])
    return normalized, []

def assess_record(raw, field_map, now=None):
    normalized, errors = normalize_record(raw, field_map)
    if errors:
        return {"data_quality": "HOLD", "certification": "HOLD", "reasons": errors}
    return certification_status(normalized, now=now)
