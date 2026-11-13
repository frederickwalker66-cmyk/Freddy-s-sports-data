"""All-eight-sport season-to-date game, team and matchup rolling research.

The July 1 (cross-year leagues) / January 1 (calendar-year leagues) dates
are CONSERVATIVE COLLECTION ANCHORS, not independently verified official
season openers. Only ESPN season.type=2 published completed-game score
rows qualify as regular-season form. Cup, playoff, preseason, 90-minute
soccer settlement, OT/regulation market and provider odds are NOT inferred.

Point-in-time rule: source observed <= prediction timestamp; game started
at least 48h before the snapshot for scored form. Rest uses the known most
recent observed event; never implies a missed fixture did not happen.
A complete last-5/10 claim requires all scoreboard source-days covered.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from challenger_research_features import validated
from historical_outcomes import LEAGUES, parse_time, scoreboard_url

NY = ZoneInfo("America/New_York")
CROSS_YEAR = frozenset(("nba", "nfl", "nhl", "ncaaf", "ncaab", "uefa_champions_league"))
SOCCER = frozenset(("mls", "uefa_champions_league"))
MATURITY_HOURS = 48
VERSION = "v8-eight-league-same-season-last5-last10-v1"
MAX_HISTORY = 10000
MAX_TARGETS = 500


def season_anchor(league, at):
    """Conservative search anchor, explicitly *not* official opening day."""
    if league not in LEAGUES:
        raise ValueError("unsupported_league")
    instant = parse_time(at.isoformat() if isinstance(at, datetime) else at)
    d = instant.astimezone(NY).date()
    if league in CROSS_YEAR:
        year = d.year if d.month >= 7 else d.year - 1
        return date(year, 7, 1), f"{year}-{year+1}"
    return date(d.year, 1, 1), str(d.year)


def _coverage(league, coverage, asof):
    start, label = season_anchor(league, asof)
    end = asof.astimezone(NY).date() - timedelta(days=1)
    if not isinstance(coverage, dict) or coverage.get("league") != league:
        return start, label, False, "MISSING_LEAGUE_SOURCE_COVERAGE"
    if coverage.get("conservative_collection_anchor_et") != start.isoformat():
        return start, label, False, "SEASON_ANCHOR_MISMATCH"
    days = coverage.get("source_days_confirmed_et")
    if not isinstance(days, list) or len(days) != len(set(days)):
        return start, label, False, "MISSING_OR_DUPLICATE_SOURCE_DAYS"
    expected = ((end-start).days+1) if end >= start else 0
    full = (
        len(days) == expected and
        set(days) == {(start+timedelta(days=i)).isoformat() for i in range(expected)}
        and coverage.get("source_days_failed_in_latest_collection", 0) == 0
        and not coverage.get("conflicting_game_event_ids")
    )
    return start, label, full, (
        "ALL_SEASON_REQUESTED_DAYS_COMPLETE" if full else "SEASON_SCOREBOARD_GAPS_OR_CONFLICTS")


def _window(rows, n, complete):
    items = rows[-n:]
    if not items:
        return {
            "requested": n, "observed_matured": 0, "source_days_complete": complete,
            "complete_window": False, "wins": None, "draws": None, "losses": None,
            "win_pct_excluding_draws": None, "win_rate_including_draws_as_nonwins": None,
            "avg_scored": None, "avg_allowed": None, "avg_game_total_display_score": None,
            "avg_score_margin": None, "both_sides_scored_rate": None,
            "source_event_ids": [],
        }
    wins = sum(x["result"] == "win" for x in items)
    draws = sum(x["result"] == "draw" for x in items)
    losses = len(items)-wins-draws
    denomin = wins+losses
    return {
        "requested": n, "observed_matured": len(items),
        "source_days_complete": complete,
        "complete_window": complete and len(items) == n,
        "wins": wins, "draws": draws, "losses": losses,
        "win_pct_excluding_draws": round(wins/denomin, 6) if denomin else None,
        "win_rate_including_draws_as_nonwins": round(wins/len(items), 6),
        "avg_scored": round(mean(x["scored"] for x in items), 3),
        "avg_allowed": round(mean(x["allowed"] for x in items), 3),
        "avg_game_total_display_score": round(mean(x["scored"]+x["allowed"] for x in items), 3),
        "avg_score_margin": round(mean(x["scored"]-x["allowed"] for x in items), 3),
        "both_sides_scored_rate": round(
            mean(int(x["scored"] > 0 and x["allowed"] > 0) for x in items), 6),
        "source_event_ids": [x["event_id"] for x in items],
        "market_line_cover_probabilities": None,
        "betting_model_probability": None,
    }


def _team(team_rows, league, target, asof, complete):
    prev = [r for r in team_rows if r["start"] < target and r["retrieved"] <= asof]
    prev.sort(key=lambda x: (x["start"], x["event_id"]))
    matured = [r for r in prev if r["start"]+timedelta(hours=MATURITY_HOURS) <= asof]
    last = prev[-1] if prev else None
    days_apart = ((target.astimezone(NY).date() -
                   last["start"].astimezone(NY).date()).days) if last else None
    if days_apart is not None and days_apart < 0:
        raise ValueError("previous_game_future_calendar_order")
    return {
        "prior_published_game_event_id_rest_only": last["event_id"] if last else None,
        "prior_published_game_date_et_rest_only": (
            last["start"].astimezone(NY).date().isoformat() if last else None),
        "calendar_rest_days_from_observed_prior_event_only": (
            max(0, days_apart-1) if days_apart is not None else None),
        "back_to_back_second_night_observed_schedule_only": (
            days_apart == 1 if days_apart is not None else None),
        "rest_cannot_be_certified_when_history_gaps": not complete,
        "last5": _window(matured, 5, complete),
        "last10": _window(matured, 10, complete),
        "season_to_date_matured": _window(matured, len(matured), complete),
        "last5_home": _window([x for x in matured if x["venue"] == "home"], 5, complete),
        "last5_away": _window([x for x in matured if x["venue"] == "away"], 5, complete),
        "last10_home": _window([x for x in matured if x["venue"] == "home"], 10, complete),
        "last10_away": _window([x for x in matured if x["venue"] == "away"], 10, complete),
    }


def build_season_game_form(history, schedule, as_of_utc, coverage_by_league=None):
    """Season-isolated, timestamped research-only L5/L10 for all eight leagues."""
    asof = parse_time(as_of_utc.isoformat() if isinstance(as_of_utc, datetime)
                      else as_of_utc)
    if not isinstance(history, list) or not isinstance(schedule, list):
        raise ValueError("history_and_schedule_must_be_lists")
    if len(history) > MAX_HISTORY or len(schedule) > MAX_TARGETS:
        raise ValueError("all_league_season_form_input_budget_exceeded")
    coverage_by_league = coverage_by_league or {}
    teams = defaultdict(list)
    h2h = defaultdict(list)
    seen = set()
    skipped = defaultdict(int)
    for row in history:
        validated(row)
        league = row["league"]
        eid = row["espn_event_id"]
        if (league, eid) in seen:
            raise ValueError("duplicate_history_espn_event")
        seen.add((league, eid))
        start = parse_time(row["event_start_utc"])
        retrieved = parse_time(row["retrieved_at_utc"])
        if retrieved > asof:
            raise ValueError("history_not_observed_at_asof")
        if row.get("source_url") != scoreboard_url(league, start.astimezone(NY).date()):
            raise ValueError("historical_source_scoreboard_day_mismatch")
        anchor, _ = season_anchor(league, asof)
        if not anchor <= start.astimezone(NY).date() <= asof.astimezone(NY).date():
            skipped["outside_current_season_search_anchor"] += 1
            continue
        if row.get("season_type") != 2:
            skipped["non_regular_season_event"] += 1
            continue
        home, away = row["home_team_espn_id"], row["away_team_espn_id"]
        hs, a_s = row["home_score"], row["away_score"]
        def team_row(tid, scored, allowed, venue):
            return {
                "start": start, "retrieved": retrieved, "event_id": eid,
                "scored": scored, "allowed": allowed, "venue": venue,
                "result": ("win" if scored > allowed else
                           "loss" if scored < allowed else "draw"),
                "team_id": tid,
            }
        teams[(league, home)].append(team_row(home, hs, a_s, "home"))
        teams[(league, away)].append(team_row(away, a_s, hs, "away"))
        h2h[(league, frozenset((home, away)))].append({
            "start": start, "retrieved": retrieved, "event_id": eid,
            "home": home, "away": away, "home_score": hs, "away_score": a_s,
        })
    results = {}
    for game in schedule:
        if not isinstance(game, dict):
            raise ValueError("invalid_upcoming_game")
        league = game.get("league")
        if league not in LEAGUES:
            raise ValueError("invalid_upcoming_league")
        eid = game.get("espn_event_id")
        home = game.get("home_team_espn_id", game.get("home_team_id"))
        away = game.get("away_team_espn_id", game.get("away_team_id"))
        if (not isinstance(eid, str) or not eid or
                not isinstance(home, str) or not home or
                not isinstance(away, str) or not away or home == away or
                (league, eid) in results):
            raise ValueError("invalid_or_duplicate_future_game_identity")
        start = parse_time(game["start_utc"])
        if start <= asof:
            continue
        anchor, label, coverage_complete, coverage_status = _coverage(
            league, coverage_by_league.get(league), asof)
        home_info = _team(teams[(league, home)], league, start, asof, coverage_complete)
        away_info = _team(teams[(league, away)], league, start, asof, coverage_complete)
        past_h2h = [x for x in h2h[(league, frozenset((home, away)))]
                    if x["start"] < start and
                    x["start"] + timedelta(hours=MATURITY_HOURS) <= asof]
        past_h2h.sort(key=lambda x: (x["start"], x["event_id"]))
        hh = [
            {"start": x["start"], "event_id": x["event_id"],
             "scored": x["home_score"] if x["home"] == home else x["away_score"],
             "allowed": x["away_score"] if x["home"] == home else x["home_score"],
             "result": ("win" if (x["home_score"] > x["away_score"]) == (x["home"] == home)
                        and x["home_score"] != x["away_score"]
                        else "draw" if x["home_score"] == x["away_score"] else "loss")}
            for x in past_h2h
        ]
        results[(league, eid)] = {
            "version": VERSION, "league": league, "espn_event_id": eid,
            "season_label_conservative": label,
            "season_collection_anchor_not_verified_opening_day_et": anchor.isoformat(),
            "as_of_utc": asof.isoformat(), "score_result_maturity_hours": MATURITY_HOURS,
            "season_source_coverage_status": coverage_status,
            "complete_source_days_since_conservative_season_anchor": coverage_complete,
            "home_team_id": home, "away_team_id": away,
            "home": home_info, "away": away_info,
            "same_season_head_to_head_last5": _window(hh, 5, coverage_complete),
            "same_season_head_to_head_last10": _window(hh, 10, coverage_complete),
            "soccer_three_way_and_90_minute_settlement_not_verified": league in SOCCER,
            "NHL_OT_shootout_and_regulation_market_settlement_not_verified": league == "nhl",
            "spread_and_total_betting_lines_not_part_of_published_score": True,
            "no_market_line_hit_rate_without_actual_line": True,
            "model_form_coefficients_fitted": False,
            "historical_published_scores_not_authenticated_settlement": True,
            "champion_001_modified": False, "certified_positive_ev_bets": 0,
        }
    return {
        "report_type": "EIGHT_LEAGUE_SEASON_L5_L10_PREGAME_RESEARCH",
        "as_of_utc": asof.isoformat(), "fixtures": {
            f"{k[0]}:{k[1]}": v for k, v in sorted(results.items())},
        "fixture_count": len(results),
        "history_regular_season_source_event_count": len(seen) - sum(skipped.values()),
        "excluded_history_reasons": dict(skipped),
        "no_stale_odds_as_player_props": True,
        "champion_001_modified": False, "certified_positive_ev_bets": 0,
    }
