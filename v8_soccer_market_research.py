"""Strict research-only soccer 90-minute match odds parser.

No provider calls. Two-outcome moneylines are NEVER substituted for 3-way
home/draw/away results. Asian handicaps and ambiguous "moneyline" fields
are quarantined until their actual settlement rules are demonstrated.
All percentages here are normalized *bookmaker prices*, never forecasts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

from historical_outcomes import parse_time
from challenger_moneyline_market_baseline import (
    implied, MAX_OVERROUND, MAX_PROVIDER_QUOTE_AGE_SECONDS,
)
from v8_sharp_archive import MAX_RESEARCH_WATCHLIST_AGE_MINUTES

SOCCER_LEAGUES = frozenset(("mls", "uefa_champions_league"))
SOCCER_MARKETS = {
    "three_way_90_minute": ("home", "draw", "away"),
    "total_goals_90_minute": ("over", "under"),
}
# Exact provider names documented Nov 2026. Treat a soccer "moneyline"
# as 1X2 ONLY when all three home/draw/away outcomes pair at one timestamp.
SOURCE_MARKET_MAPPING = {
    "moneyline": "three_way_90_minute",
    "moneyline_3-way": "three_way_90_minute",
    "three_way_90_minute": "three_way_90_minute",
    "total_goals": "total_goals_90_minute",
    "total_goals_90_minute": "total_goals_90_minute",
}
NY = ZoneInfo("America/New_York")


def inspect_soccer_quote(row):
    if not isinstance(row, dict):
        return None, "invalid_row"
    league = row.get("league")
    if league not in SOCCER_LEAGUES:
        return None, "outside_soccer_scope"
    market = SOURCE_MARKET_MAPPING.get(row.get("market_type"))
    if market not in SOCCER_MARKETS:
        return None, "ambiguous_or_unimplemented_soccer_settlement"
    if (row.get("source") != "sharpapi_rest"
            or row.get("sportsbook") != "draftkings"
            or row.get("record_type") != "pregame_odds_observation"
            or row.get("is_player_prop") is not False
            or row.get("is_main_line") is not True
            or row.get("is_alternate_line") is not False
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None):
        return None, "untrusted_soccer_quote"
    side = row.get("selection_type")
    if side not in SOCCER_MARKETS[market]:
        return None, "invalid_soccer_outcome"
    eid, home, away = row.get("event_id"), row.get("home_team"), row.get("away_team")
    if (any(not isinstance(x, str) or not x.strip() for x in (eid, home, away))
            or home.strip().casefold() == away.strip().casefold()):
        return None, "missing_soccer_event_identity"
    line = row.get("line")
    if market == "three_way_90_minute":
        if line is not None:
            return None, "three_way_market_with_unexpected_line"
    elif (type(line) not in (int, float) or not math.isfinite(line)
          or line <= 0 or not math.isclose(line % 1, 0.5, abs_tol=1e-8)):
        # Integer goals can push and quarter-goals can half-win/half-lose.
        # Those are NOT simple binary outcomes; quarantine until modeled.
        return None, "soccer_goal_total_requires_exact_half_goal_line"
    odds, dec = row.get("odds_american"), row.get("odds_decimal")
    if (type(odds) not in (int, float) or not math.isfinite(odds)
            or abs(odds) < 100
            or type(dec) not in (int, float) or not math.isfinite(dec)):
        return None, "invalid_soccer_price"
    expected = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
    if abs(dec - expected) > 0.025:
        return None, "inconsistent_soccer_price"
    try:
        start = parse_time(row["event_start_time"])
        quoted = parse_time(row["timestamp"])
        received = parse_time(row["recorded_at"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "invalid_soccer_pregame_clocks"
    if not (0 <= (received - quoted).total_seconds()
            <= MAX_PROVIDER_QUOTE_AGE_SECONDS
            and quoted < start and received < start):
        return None, "stale_or_inplay_soccer_quote"
    key = (league, eid, home, away, start, market, row["sportsbook"])
    return {"key": key, "raw": row, "quoted": quoted,
            "received": received, "implied": implied(odds)}, None


def summarize_soccer_markets(rows, *, now=None, archive_run_ids=()):
    if not isinstance(rows, list):
        raise ValueError("soccer_quote_rows_must_be_list")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("aware_soccer_market_clock_required")
    clock = clock.astimezone(timezone.utc)
    rejected, grouped = Counter(), defaultdict(list)
    for row in rows:
        item, reason = inspect_soccer_quote(row)
        if reason:
            if isinstance(row, dict) and row.get("league") in SOCCER_LEAGUES:
                rejected[reason] += 1
            continue
        if item["received"] > clock:
            rejected["receipt_after_audit_time"] += 1
            continue
        grouped[item["key"], item["quoted"]].append(item)
    paired = []
    for (key, quoted), records in sorted(grouped.items(), key=lambda x: (
            x[0][0][4], x[0][0][0], x[0][0][1], x[0][1])):
        market = key[5]
        sides = SOCCER_MARKETS[market]
        by_side = {side: [r for r in records
                          if r["raw"]["selection_type"] == side] for side in sides}
        if any(len(v) != 1 for v in by_side.values()) or len(records) != len(sides):
            rejected["unpaired_duplicate_or_missing_soccer_outcomes"] += 1
            continue
        if market == "total_goals_90_minute":
            if not math.isclose(by_side["over"][0]["raw"]["line"],
                                by_side["under"][0]["raw"]["line"], abs_tol=1e-7):
                rejected["soccer_total_goal_lines_disagree"] += 1
                continue
        overround = sum(by_side[side][0]["implied"] for side in sides)
        if not 1 <= overround <= MAX_OVERROUND:
            rejected["implausible_soccer_market_overround"] += 1
            continue
        last_received = max(x["received"] for x in (by_side[k][0] for k in sides))
        paired.append({
            "league": key[0], "provider_event_id": key[1],
            "home_team": key[2], "away_team": key[3],
            "start_utc": key[4].isoformat(), "market": market,
            "provider_quote_utc": quoted.isoformat(),
            "source_received_utc": last_received.isoformat(),
            "source_book_label": key[6],
            "source_market_types": sorted({r["raw"]["market_type"] for r in records}),
            "exact_90_minute_outcome_scope_verified": False,
            "goal_total_line": (by_side["over"][0]["raw"]["line"]
                                if market == "total_goals_90_minute" else None),
            "american_odds_by_outcome": {
                side: by_side[side][0]["raw"]["odds_american"] for side in sides
            },
            "normalized_no_vig_market_shares": {
                side: round(by_side[side][0]["implied"] / overround, 7)
                for side in sides
            },
            "bookmaker_checkout_price_verified": False,
            "independent_model_probability_verified": False,
            "certified_positive_ev": False, "bet_ready": False,
        })
    today = clock.astimezone(NY).date()
    latest = {}
    for snap in paired:
        start, received = parse_time(snap["start_utc"]), parse_time(snap["source_received_utc"])
        if not (start > clock and start.astimezone(NY).date() == today
                and received <= clock
                and 0 <= (clock - received).total_seconds() / 60
                <= MAX_RESEARCH_WATCHLIST_AGE_MINUTES):
            continue
        key = (snap["league"], snap["provider_event_id"], snap["market"])
        if (key not in latest
                or snap["provider_quote_utc"] > latest[key]["provider_quote_utc"]):
            latest[key] = snap
    board = sorted(latest.values(), key=lambda x: (
        x["start_utc"], x["league"], x["provider_event_id"], x["market"]))
    return {
        "report_type": "v8_soccer_exact_90_minute_3way_and_goals_research_only",
        "research_date_eastern": today.isoformat(),
        "supported_leagues": sorted(SOCCER_LEAGUES),
        "three_outcome_moneyline_and_draw_paired_only": True,
        "soccer_asian_handicap_supported": False,
        "soccer_quarter_goal_settlement_supported": False,
        "non_90_minute_soccer_market_promotion_allowed": False,
        "historical_exact_paired_market_snapshots": len(paired),
        "today_recent_exact_soccer_markets": len(board),
        "today_soccer_game_market_board": board[:30],
        "excluded_or_unpaired_reasons": dict(sorted(rejected.items())),
        "archive_run_ids": list(archive_run_ids),
        "model_probability_display": "UNAVAILABLE_NOT_MODEL_GENERATED",
        "independently_verified_sportsbook_checkout_prices": 0,
        "certified_positive_ev_bets": 0, "automated_wagers": 0,
        "champion_001_modified": False, "stake_usd": 0,
        "decision": "HOLD_NO_INDEPENDENTLY_VERIFIED_SOCCER_MARKET_EV",
    }
