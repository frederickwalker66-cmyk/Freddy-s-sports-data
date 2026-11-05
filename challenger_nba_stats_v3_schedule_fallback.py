"""NBA-operated date-specific Stats ScoreboardV3 as a third pregame ID source.

The Stats API is NBA-operated but may deny hosted runners. Its scoreboard
object is validated by strict same-Eastern-day and exact NBA team ID logic.
This is game identity evidence only, not Active List or betting certification.
"""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo

from challenger_nba_schedule_clock import stats_scoreboard_url
from challenger_nba_daily_scoreboard_fallback import validate_same_day_scoreboard

ET = ZoneInfo("America/New_York")


def stats_url_for_observation(observed_at):
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise ValueError("nba_stats_schedule_requires_aware_observation_clock")
    return stats_scoreboard_url(observed_at.astimezone(ET).date().isoformat())


def verify_stats_v3_scoreboard(raw, source_url, observed_at):
    """Reject any replay/date/URL mismatch and any non-NBA Stats payload."""
    expected_url = stats_url_for_observation(observed_at)
    if not isinstance(source_url, str) or source_url != expected_url:
        raise ValueError("nba_stats_scoreboard_source_not_for_observed_eastern_date")
    payload, future = validate_same_day_scoreboard(raw, observed_at)
    # The exact NBA-operated URL, actual timestamp and source bytes must
    # remain together in the original-data capture receipt.
    return payload, future
