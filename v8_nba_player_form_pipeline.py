"""Bounded NBA pregame player-form research from fresh ESPN-published results.

Scores must come from the same source-labelled 35-day history captured for
the V8 forward-research lane. This module optionally fetches at most 24
historical ESPN box-score summaries for games involving the upcoming slate.
It creates a *new* later-timestamped research feature snapshot; it NEVER
retrofits the earlier Elo forecast, guesses active rosters, joins sportsbook
provider player identities, certifies betting probabilities or places wagers.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from challenger_elo_walkforward import validate_game
from challenger_research_features import validated as validate_source_record
from challenger_nba_player_boxes import fetch_summary, parse_summary
from historical_outcomes import parse_time, scoreboard_url
from v8_nba_player_recent_form import build_player_form
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MAX_SUMMARIES = 24
MAX_HISTORY = 650
MAX_CANDIDATES = 400


def _report(status, **fields):
    return {
        "report_type": "V8_NBA_PREGAME_LAST5_LAST10_PLAYER_FORM",
        "status": status,
        "historical_summaries_attempted": 0,
        "historical_summaries_validated": 0,
        "historical_player_box_rows_retained": 0,
        "future_player_targets_staged_unverified_roster": 0,
        "players_with_complete_last5": 0,
        "players_with_complete_last10": 0,
        "score_history_source": "ESPN published scoreboard research only",
        "player_history_source": "ESPN historical summary research only",
        "new_research_snapshot_not_original_elo_forecast": True,
        "current_team_and_active_status_verified": False,
        "player_stats_independently_corrobated": False,
        "bookmaker_checkout_or_player_prop_link_verified": False,
        "independently_calibrated_player_prop_probabilities": 0,
        "calculated_expected_value_bets": 0,
        "certified_positive_ev_bets": 0,
        "champion_001_modified": False,
        "wagers_placed": 0,
        **fields,
    }


def run_player_form_research(history_path, scheduled_games, output_dir, *,
                             coverage=None, max_summaries=MAX_SUMMARIES,
                             fetcher=fetch_summary, clock=None):
    """Capture safe player averages or explicitly report unavailable.

    A historical boxscore must match an ESPN scoreboard event ID and both
    teams. Only source-observed boxscore rows with mature earlier starts are
    used; the last-five/last-ten windows may be incomplete. Missing inputs
    report unavailable, never a zero-scoring player or a 0% betting chance.
    """
    clock = clock or (lambda: datetime.now(timezone.utc))
    if type(max_summaries) is not int or not 1 <= max_summaries <= MAX_SUMMARIES:
        raise ValueError("player_form_summary_budget_must_be_1_to_24")
    if not isinstance(scheduled_games, list) or not isinstance(coverage, dict):
        raise ValueError("player_form_schedule_and_source_coverage_required")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = Path(history_path)
    failed_days = coverage.get("source_days_failed", coverage.get("by_league", {}).get("nba", {}).get("days_failed"))
    if failed_days != 0:
        result = _report("HOLD_INCOMPLETE_OR_MISSING_SCORE_SOURCE_COVERAGE")
        _save(output, result, [])
        return result
    if not source.is_file() or source.is_symlink():
        result = _report("HOLD_NO_CAPTURED_HISTORICAL_NBA_SCORES")
        _save(output, result, [])
        return result
    raw = source.read_text(encoding="utf-8")
    if len(raw.encode("utf-8")) > 2_000_000:
        raise ValueError("oversized_NBA_score_history")
    history = [json.loads(x) for x in raw.splitlines() if x.strip()]
    if len(history) > MAX_HISTORY:
        raise ValueError("NBA_score_history_game_budget_exceeded")
    first_seen = _time(clock)
    games = []
    observed = set()
    active_ids = set()
    events = []
    for g in scheduled_games:
        if not isinstance(g, dict):
            raise ValueError("invalid_upcoming_NBA_scheduled_game")
        if g.get("league") not in (None, "nba"):
            raise ValueError("nonNBA_schedule_provided")
        eid = g.get("espn_event_id")
        if not isinstance(eid, str) or not eid or eid in observed:
            raise ValueError("invalid_or_duplicate_upcoming_game")
        observed.add(eid)
        start = parse_time(g["start_utc"])
        if start <= first_seen:
            continue
        home = g.get("home_team_id", g.get("home_team_espn_id"))
        away = g.get("away_team_id", g.get("away_team_espn_id"))
        if (not isinstance(home, str) or not isinstance(away, str)
                or not home.isdecimal() or not away.isdecimal() or home == away
                or (g.get("home_team_espn_id") is not None
                    and g["home_team_espn_id"] != home)
                or (g.get("away_team_espn_id") is not None
                    and g["away_team_espn_id"] != away)):
            raise ValueError("invalid_upcoming_team_ids")
        active_ids.update((home, away))
        events.append({**g, "home_team_espn_id": home, "away_team_espn_id": away})
    if not events:
        result = _report("HOLD_NO_FUTURE_NBA_GAMES_BEFORE_TIPOFF")
        _save(output, result, [])
        return result
    seen_history = set()
    for row in history:
        validate_source_record(row)
        league, start, eid, home, away, winner = validate_game(row)
        if league != "nba" or winner not in (0, 1):
            raise ValueError("invalid_historical_NBA_final")
        if row.get("source_url") != scoreboard_url("nba", start.astimezone(NY).date()):
            raise ValueError("NBA_historical_source_day_mismatch")
        when = parse_time(row["retrieved_at_utc"])
        if when > first_seen or not start < when:
            raise ValueError("NBA_historical_source_not_available_before_research")
        if eid in seen_history:
            raise ValueError("duplicate_historical_NBA_event")
        seen_history.add(eid)
        if (start + timedelta(hours=48) <= first_seen
                and (home in active_ids or away in active_ids)):
            games.append((start, eid, home, away))
    # Only the latest eligible games are requested; no stale/inplay outcomes.
    games.sort(reverse=True)
    games = games[:max_summaries]
    box_rows, errors = [], Counter()
    for start, eid, home, away in games:
        try:
            response = fetcher(eid)
            fetched = _time(clock)
            if fetched < first_seen:
                raise ValueError("player_form_source_clock_regression")
            if not isinstance(response, dict):
                raise ValueError("player_form_summary_object_required")
            parsed = parse_summary(response, eid, fetched.isoformat())
            if any(row["team_id"] not in (home, away) for row in parsed):
                raise ValueError("NBA_summary_team_disagrees_with_original_score")
            for row in parsed:
                stamp = row.get("event_start_utc")
                if stamp is not None and parse_time(stamp) != start:
                    raise ValueError("NBA_summary_event_time_disagrees_with_scoreboard")
            # Missing summary date can use the contemporaneously captured
            # scoreboard event-start field, not a guessed or later game date.
            for row in parsed:
                was_missing_start = row.get("event_start_utc") is None
                if was_missing_start:
                    row["event_start_utc"] = start.isoformat()
                row["event_start_from_published_scoreboard_when_missing"] = was_missing_start
                row["source_payload_sha256_canonical_not_original_wire"] = hashlib.sha256(
                    json.dumps(response, sort_keys=True, separators=(",", ":"),
                               allow_nan=False).encode()).hexdigest()
            box_rows.extend(parsed)
        except (ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
            errors[type(exc).__name__] += 1
    captured_at = _time(clock)
    # Source calls could span tipoff. Never silently attach today's results.
    future = [g for g in events if parse_time(g["start_utc"]) > captured_at]
    target_map = {}
    for g in future:
        for row in box_rows:
            if row.get("did_not_play") is True:
                continue
            if row["team_id"] in (g["home_team_espn_id"], g["away_team_espn_id"]):
                key = (g["espn_event_id"], row["player_id"])
                target_map.setdefault(key, {
                    "espn_event_id": g["espn_event_id"],
                    "player_id": row["player_id"], "start_utc": g["start_utc"],
                })
    if len(target_map) > MAX_CANDIDATES:
        raise ValueError("NBA_player_form_candidate_budget_exceeded")
    model = build_player_form(box_rows, list(target_map.values()),
                              captured_at.isoformat())
    forms = model["players"]
    name_by_id = {}
    for row in box_rows:
        if isinstance(row.get("player_name"), str) and row["player_name"]:
            name_by_id[row["player_id"]] = row["player_name"]
    player_views = []
    for key, x in sorted(forms.items()):
        player_views.append({
            "player_event_key": key,
            "historical_ESPN_name_not_confirmed_current_roster":
                name_by_id.get(x["historical_espn_player_id"]),
            **x,
        })
    result = _report(
        ("RESEARCH_ONLY_PARTIAL_HISTORICAL_PLAYER_FORM" if player_views
         else "HOLD_NO_MATCHED_HISTORICAL_PLAYER_APPEARANCES"),
        collected_at_utc=captured_at.isoformat(),
        historical_summaries_attempted=len(games),
        historical_summaries_validated=len(games)-sum(errors.values()),
        historical_player_box_rows_retained=len(box_rows),
        future_player_targets_staged_unverified_roster=len(player_views),
        players_with_complete_last5=sum(p["player_last5"]["full_window"] for p in player_views),
        players_with_complete_last10=sum(p["player_last10"]["full_window"] for p in player_views),
        source_errors_by_exception_class=dict(sorted(errors.items())),
        source_history_events_considered=len(history),
        history_summaries_budget=max_summaries,
        visible_future_games=len(future),
        player_form_from_original_publication_captured_at_research_only=True,
    )
    _save(output, result, player_views)
    return result


def _time(clock):
    when = clock()
    if not isinstance(when, datetime) or when.tzinfo is None:
        raise ValueError("aware_player_form_clock_required")
    return when.astimezone(timezone.utc)


def _save(out, report, players):
    (out / "NBA_PLAYER_FORM_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "NBA_PLAYER_LAST5_LAST10.json").write_text(
        json.dumps(players, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# NBA player last five / last ten — research only",
        f"**Status:** {report['status']}",
        f"**Historical summary requests:** {report['historical_summaries_attempted']} "
        f"(validated {report['historical_summaries_validated']})",
        f"**Unverified current-roster player targets:** {len(players)}",
        f"**Complete last-5 / last-10 windows:** "
        f"{report['players_with_complete_last5']} / {report['players_with_complete_last10']}",
        "**Not live roster verification, independent player-model probabilities, "
        "betting +EV, verified CLV, or confirmed prop lines. Never bet from this table.**",
        "| Historical player label (NOT verified active today) | Upcoming ESPN event | "
        "Last 5 / last 10 matured appearances | Last 5 P/R/A/3PM | Last 10 P/R/A/3PM |",
        "|---|---|---:|---|---|",
    ]
    for p in players[:80]:
        def average_stat_line(window):
            a = window["averages_when_every_selected_game_has_stat"]
            if not window["full_window"]:
                return "Incomplete window — N/A"
            return " / ".join(str(a[k]) if a[k] is not None else "N/A"
                            for k in ("points", "rebounds", "assists", "threes_made"))
        lines.append(
            f"| {str(p['historical_ESPN_name_not_confirmed_current_roster'] or 'N/A').replace('|','/')[:60]} "
            f"| {p['scheduled_event_id']} "
            f"| {p['player_last5']['matured_appearances_available']}/5 / "
            f"{p['player_last10']['matured_appearances_available']}/10 "
            f"| {average_stat_line(p['player_last5'])} "
            f"| {average_stat_line(p['player_last10'])} |")
    (out / "NBA_PLAYER_LAST5_LAST10.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
