"""Fail-closed NBA injury evidence reconciliation.

A previous game's OUT is never evidence of today's OUT. A player absent from
an injury report is not automatically confirmed active or starting.
This module deliberately does not certify picks, rosters, or odds.
"""
from datetime import datetime, timezone


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("missing_observation_timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive_observation_timestamp")
    return dt.astimezone(timezone.utc)


def reconcile_player(game_date, team, player, observations, as_of_utc):
    """Return an auditable research status, never a bet-ready decision.

    Observations: {game_date, team, player, status, observed_at_utc,
    source_url, source_type}. Source_type must be 'nba_official_report'
    to support a league designation. All other reports are context only.
    """
    as_of = _instant(as_of_utc)
    relevant = []
    previous = 0
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("invalid_observation")
        if row.get("team") != team or row.get("player") != player:
            continue
        when = _instant(row.get("observed_at_utc"))
        if when > as_of:
            raise ValueError("future_dated_injury_evidence")
        if row.get("game_date") != game_date:
            previous += 1
            continue
        if not isinstance(row.get("source_url"), str) or not row["source_url"].startswith("https://"):
            raise ValueError("missing_source_provenance")
        if row.get("status") not in ("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE", "AVAILABLE", "NOT_LISTED", "NOT_SUBMITTED"):
            raise ValueError("unknown_injury_designation")
        relevant.append((when, row))
    official = sorted((r for r in relevant if r[1].get("source_type") == "nba_official_report"), key=lambda r: r[0])
    latest = official[-1][1] if official else None
    designation = latest["status"] if latest else "UNVERIFIED"
    return {
        "game_date": game_date, "team": team, "player": player,
        "official_designation": designation,
        "official_observed_at_utc": latest["observed_at_utc"] if latest else None,
        "official_source_url": latest["source_url"] if latest else None,
        "prior_game_records_excluded": previous,
        "third_party_same_game_reports": len(relevant) - len(official),
        "confirmed_starter": False,
        "confirmed_active": False,
        "model_probability": None,
        "certified_take": False,
        "decision": "HOLD",
    }
