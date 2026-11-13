"""Last-5/last-10 NBA PLAYER box-score features, research-only.

Only original ESPN summary player rows captured before the prediction and
matured by >=48h are eligible. DNP is not an appearance; unknown stats and
missing games are never imputed. No unverified odds-to-roster join is allowed.
Requires real preserved player box-score history; does not download anything.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean

from historical_outcomes import parse_time

FIELDS = ("minutes", "points", "rebounds", "assists", "threes_made", "steals", "blocks")
LAG_HOURS = 48
MAX_UPCOMING_PLAYER_TARGETS = 400  # 9+ NBA games x full historical rosters
SOURCE_PREFIX = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="


def _avg(values, key):
    found = [g[key] for g in values if g[key] is not None]
    return round(mean(found), 3) if len(found) == len(values) and values else None


def _window(games, count):
    selected = games[-count:]
    return {
        "required_appearances": count,
        "matured_appearances_available": len(selected),
        "full_window": len(selected) == count,
        "averages_when_every_selected_game_has_stat": {
            k: _avg(selected, k) for k in FIELDS},
        "source_game_event_ids": [g["event_id"] for g in selected],
    }


def build_player_form(box_rows, targets, as_of_utc):
    """Return ESPN-ID-keyed, strictly historical inputs; never a betting edge."""
    asof = parse_time(as_of_utc)
    if not isinstance(box_rows, list) or not isinstance(targets, list):
        raise ValueError("NBA_player_box_and_target_lists_required")
    if len(box_rows) > 100_000 or len(targets) > MAX_UPCOMING_PLAYER_TARGETS:
        raise ValueError("NBA_player_feature_input_budget_exceeded")
    by_player = defaultdict(list)
    seen = set()
    excluded = Counter()
    for row in box_rows:
        if (not isinstance(row, dict) or row.get("sport") != "nba"
                or row.get("independently_verified_player_stats") is not False
                or row.get("historical_prop_settlement_verified") is not False
                or row.get("qualified_for_player_prop_training") is not False
                or row.get("champion_001_modified") is not False):
            raise ValueError("untrusted_NBA_player_box_row")
        player, eid = row.get("player_id"), row.get("event_id")
        if (not isinstance(player, str) or not player.isdecimal()
                or not isinstance(eid, str) or not eid.isdecimal()
                or row.get("source_url") != SOURCE_PREFIX + eid):
            raise ValueError("invalid_ESPN_player_event_identity")
        if (player, eid) in seen:
            raise ValueError("duplicate_ESPN_player_game_box")
        seen.add((player, eid))
        observed = parse_time(row.get("fetched_at_utc"))
        if observed > asof:
            raise ValueError("player_box_observed_after_forecast")
        stamp = row.get("event_start_utc")
        if stamp is None:
            excluded["missing_independent_source_event_start"] += 1
            continue
        start = parse_time(stamp)
        if not start < observed:
            raise ValueError("player_box_source_timestamp_order_invalid")
        if row.get("did_not_play") is True:
            excluded["DNP_not_an_appearance"] += 1
            continue
        if row.get("did_not_play") is not False:
            raise ValueError("player_box_DNP_status_unknown")
        if start + timedelta(hours=LAG_HOURS) > asof:
            excluded["result_not_matured_48h"] += 1
            continue
        stats = {}
        for name in FIELDS:
            value = row.get(name)
            if value is not None and (type(value) not in (int, float)
                                      or not 0 <= value <= 250):
                raise ValueError("invalid_historical_NBA_player_stat")
            stats[name] = value
        if stats["minutes"] is None or stats["minutes"] <= 0:
            excluded["missing_minutes_or_nonappearance"] += 1
            continue
        by_player[player].append({
            **stats, "started": start, "event_id": eid,
            "source_team_id": row.get("team_id")})
    for games in by_player.values():
        games.sort(key=lambda q: (q["started"], q["event_id"]))
    result = {}
    seen_targets = set()
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("invalid_NBA_player_target")
        player, eid = target.get("player_id"), target.get("espn_event_id")
        if (not isinstance(player, str) or not player.isdecimal()
                or not isinstance(eid, str) or not eid.isdecimal()
                or (eid, player) in seen_targets):
            raise ValueError("invalid_or_duplicate_NBA_target_identity")
        seen_targets.add((eid, player))
        tip = parse_time(target.get("start_utc"))
        if tip <= asof:
            raise ValueError("NBA_player_target_already_started")
        eligible = [r for r in by_player[player] if r["started"] < tip]
        result[eid + ":" + player] = {
            "forecast_as_of_utc": asof.isoformat(),
            "scheduled_event_id": eid,
            "historical_espn_player_id": player,
            "current_team_and_active_status_independently_verified": False,
            "source_player_team_ids_observed": sorted({
                str(r["source_team_id"]) for r in eligible if r["source_team_id"] is not None}),
            "player_last5": _window(eligible, 5),
            "player_last10": _window(eligible, 10),
            "box_score_maturity_hours": LAG_HOURS,
            "statistical_projection_calibrated": False,
            "prop_probability": None, "sharp_edge": None,
            "certified_positive_ev_bets": 0,
            "champion_001_modified": False,
        }
    return {"report_type": "V8_NBA_PLAYER_LAST5_LAST10_RESEARCH",
            "players": result, "target_count": len(result),
            "history_appearance_count": sum(len(x) for x in by_player.values()),
            "excluded_history": dict(sorted(excluded.items())),
            "player_prop_model_calibrated": False, "champion_001_modified": False,
            "certified_positive_ev_bets": 0}
