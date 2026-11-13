"""Point-in-time NBA rest and rolling team-form features (V8 research only).

The latest *observed* prior game supplies the calendar rest/B2B flag, while
published scores enter last-5/last-10 form only after the existing conservative
48-hour maturity embargo. No result from the target game, future score, betting
odds, inferred roster or Champion-001 probability enters this feature stream.
These are candidate Challenger training inputs, not calibrated betting edges.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from challenger_elo_walkforward import validate_game
from challenger_research_features import validated as validate_source_record
from historical_outcomes import parse_time, scoreboard_url

NY = ZoneInfo("America/New_York")
MATURITY_HOURS = 48
FEATURE_VERSION = "nba-rest-b2b-last5-last10-research-v1"


def _window(eligible, n):
    """Return all available matured rows, never pad a missing window with wins."""
    rows = eligible[-n:]
    return {
        "requested_games": n,
        "available_matured_games": len(rows),
        "complete_window": len(rows) == n,
        "win_rate": round(mean(r["won"] for r in rows), 6) if rows else None,
        "average_point_margin": round(mean(r["margin"] for r in rows), 4) if rows else None,
        "average_points_scored": round(mean(r["scored"] for r in rows), 4) if rows else None,
        "average_points_allowed": round(mean(r["allowed"] for r in rows), 4) if rows else None,
        "source_espn_event_ids": [r["event_id"] for r in rows],
    }


def _team_features(entries, target_start, capture_at):
    target_day = target_start.astimezone(NY).date()
    past = [r for r in entries if r["started"] < target_start
            and r["started"] < capture_at and r["retrieved"] <= capture_at]
    past.sort(key=lambda r: (r["started"], r["event_id"]))
    last = past[-1] if past else None
    if last:
        dates_apart = (target_day - last["started"].astimezone(NY).date()).days
        if dates_apart < 0:
            raise ValueError("NBA_prior_game_calendar_order_invalid")
        rest_days = max(0, dates_apart - 1)
        b2b = dates_apart == 1
    else:
        dates_apart, rest_days, b2b = None, None, None
    # Observing yesterday's FINAL does not authorize using yesterday's score
    # in a forecast: the 48h embargo is applied independently.
    matured = [r for r in past
               if r["started"] + timedelta(hours=MATURITY_HOURS) <= capture_at]
    return {
        "previous_game_date_et": (
            last["started"].astimezone(NY).date().isoformat() if last else None),
        "days_between_game_dates": dates_apart,
        "rest_days": rest_days,
        "back_to_back_second_night": b2b,
        "prior_game_event_id_for_rest_only": last["event_id"] if last else None,
        "last5": _window(matured, 5),
        "last10": _window(matured, 10),
    }


def build_features(history, schedule, captured_at):
    """Compute per-game home/away context from independently timestamped history.

    Every historical row must be original-source-shaped, captured before the
    forecast and associated with its published Eastern-date scoreboard URL.
    Never impute an absent previous game or extend earlier-season statistics.
    """
    asof = parse_time(captured_at.isoformat() if hasattr(captured_at, "isoformat")
                      else captured_at)
    if not isinstance(history, list) or not isinstance(schedule, list):
        raise ValueError("NBA_history_and_schedule_lists_required")
    team_games = defaultdict(list)
    seen = set()
    for row in history:
        validate_source_record(row)
        league, started, event_id, home, away, result = validate_game(row)
        if league != "nba" or result not in (0, 1):
            raise ValueError("NBA_only_binary_regular_season_history")
        if row.get("source_url") != scoreboard_url(
                "nba", started.astimezone(NY).date()):
            raise ValueError("historical_NBA_source_date_mismatch")
        retrieved = parse_time(row["retrieved_at_utc"])
        if not started < retrieved <= asof:
            raise ValueError("NBA_historical_result_not_observed_by_forecast")
        if event_id in seen:
            raise ValueError("duplicate_NBA_history_event")
        seen.add(event_id)
        for tid, scored, allowed in (
                (home, row["home_score"], row["away_score"]),
                (away, row["away_score"], row["home_score"])):
            team_games[tid].append({
                "started": started, "retrieved": retrieved,
                "event_id": event_id, "won": int(scored > allowed),
                "margin": scored - allowed, "scored": scored, "allowed": allowed,
            })
    output = {}
    for game in schedule:
        if not isinstance(game, dict) or game.get("league") != "nba":
            raise ValueError("NBA_future_schedule_required")
        game_id = game.get("espn_event_id")
        home, away = game.get("home_team_espn_id"), game.get("away_team_espn_id")
        if game_id in output:
            raise ValueError("duplicate_future_NBA_identity")
        if (not isinstance(game_id, str) or not game_id
                or not isinstance(home, str) or not isinstance(away, str)
                or home == away):
            raise ValueError("invalid_NBA_future_identity")
        start = parse_time(game["start_utc"])
        if start <= asof:
            continue
        output[game_id] = {
            "feature_version": FEATURE_VERSION,
            "score_maturity_embargo_hours": MATURITY_HOURS,
            "last_game_date_uses_observed_prior_event_only": True,
            "full_5_and_10_game_windows_required_for_complete_form": True,
            "home": _team_features(team_games[home], start, asof),
            "away": _team_features(team_games[away], start, asof),
            "derived_as_of_utc": asof.isoformat(),
            "champion_001_modified": False,
            "applied_as_probability_weight": False,
        }
    return output
