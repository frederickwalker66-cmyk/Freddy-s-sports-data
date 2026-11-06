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


def verify_stats_v3_scoreboard(raw, source_url, observed_at, *, event_day_et=None):
    """Validate NBA Stats V3 source and date, never future player active status.

    The default (used by player-status sources) still strictly requires the
    actual current Eastern date. The explicit event-day mode is ONLY for
    future-game research identity; the caller must use a date present in
    an existing ESPN pregame archive. Both modes require matching original
    JSON gameDate, leagueId=00, official team IDs and scheduled future tip.
    """
    expected_url = (stats_url_for_observation(observed_at)
                    if event_day_et is None else stats_scoreboard_url(event_day_et))
    if not isinstance(source_url, str) or source_url != expected_url:
        raise ValueError("nba_stats_scoreboard_source_not_for_observed_eastern_date")
    payload, future = validate_same_day_scoreboard(
        raw, observed_at, expected_day_et=event_day_et)
    # Only the exact fetched NBA-operated URL, actual observation timestamp,
    # and original bytes are eligible for independent research game identity.
    return payload, future
