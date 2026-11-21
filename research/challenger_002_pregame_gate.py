"""Research-only pregame NBA capture gate.

Rejects retroactive snapshots for pregame evidence. Captures provider responses
only for events whose verified start time is still in the future. A source
start time is an assertion, not independent verification. Never certifies TAKE.
"""
from datetime import datetime, timezone
from research.challenger_002_baseline import timestamp

def inspect_pregame_snapshot(payload, retrieved_at, *, start_field="DateTime"):
    """Assess candidate games; never claim independently verified pregame odds."""
    observed = timestamp(retrieved_at)
    if not isinstance(payload, list):
        return {"status":"BLOCKED","reason":"INVALID_PAYLOAD","certified_take_count":0}
    eligible, rejected = [], []
    for index, game in enumerate(payload):
        try:
            if not isinstance(game, dict):
                raise ValueError("INVALID_GAME")
            value = game.get(start_field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("START_TIME_MISSING")
            # SportsDataIO may provide timezone-naive local tipoff. Do not guess timezone.
            start = timestamp(value)
            if observed >= start:
                raise ValueError("OBSERVED_AT_OR_AFTER_START")
            identifier = game.get("GameID", game.get("GameId"))
            if identifier is None:
                raise ValueError("GAME_ID_MISSING")
            eligible.append({"game_id":str(identifier),"start_at":start.isoformat()})
        except (ValueError, TypeError, AttributeError) as exc:
            rejected.append({"row":index,"reason":str(exc)})
    return {"status":"PREGAME_CANDIDATES_NOT_AUTHENTICATED" if eligible else "BLOCKED",
            "eligible_count":len(eligible),"rejected":rejected,
            "eligible":eligible,"independently_verified":False,
            "draftkings_identity_verified":False,"certified_take_count":0}
