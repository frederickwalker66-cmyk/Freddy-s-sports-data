"""Six-league two-outcome full-game moneyline, spread, and totals research board.

Source prices and lines are aggregator observations only: no checkout receipts,
native model projections, proof of professional flow, real bets or edge claims.
Identifies both sides of one provider-issued primary pregame market snapshot.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

from historical_outcomes import parse_time
from challenger_moneyline_market_baseline import (
    implied, MAX_OVERROUND, MAX_PROVIDER_QUOTE_AGE_SECONDS,
)
from v8_sharp_archive import MAX_RESEARCH_WATCHLIST_AGE_MINUTES
from v8_sharp_probability_display import price_pair_probabilities

GAME_PRICE_SPORTS = frozenset(("nba", "nfl", "ncaaf", "ncaab", "mlb", "nhl"))
ALLOWED = frozenset(("moneyline", "point_spread", "total_points"))
# Aliases apply ONLY in their named sport. Never treat soccer's draw-capable
# winner market as a two-way moneyline. Regulation/OT rules remain unverified.
LEAGUE_MARKET_ALIASES = {
    "mlb": {"run_line": "point_spread", "total_runs": "total_points"},
    "nhl": {"puck_line": "point_spread", "total_goals": "total_points"},
}

def canonical_market(league, market):
    if market in ALLOWED:
        return market
    return LEAGUE_MARKET_ALIASES.get(league, {}).get(market)


SIDES = {"moneyline": ("home", "away"),
         "point_spread": ("home", "away"),
         "total_points": ("over", "under")}
NY = ZoneInfo("America/New_York")


def inspect_full_game_quote(row):
    if not isinstance(row, dict):
        return None, "invalid_row"
    if row.get("league") not in GAME_PRICE_SPORTS:
        return None, "outside_supported_game_price_scope"
    market = canonical_market(row["league"], row.get("market_type"))
    if market not in ALLOWED:
        return None, "outside_full_game_market_scope"
    if (row.get("source") != "sharpapi_rest"
            or row.get("sportsbook") != "draftkings"
            or row.get("record_type") != "pregame_odds_observation"
            or row.get("is_player_prop") is not False
            or row.get("is_main_line") is not True
            or row.get("is_alternate_line") is not False
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None):
        return None, "untrusted_primary_market_or_certification_flags"
    if row.get("selection_type") not in SIDES[market]:
        return None, "unrecognized_market_side"
    eid, home, away = row.get("event_id"), row.get("home_team"), row.get("away_team")
    if any(not isinstance(x, str) or not x.strip() for x in (eid, home, away)) or home == away:
        return None, "missing_provider_game_identity"
    line = row.get("line")
    if market == "moneyline":
        if line is not None:
            return None, "moneyline_has_unexpected_line"
    elif (type(line) not in (int, float) or not math.isfinite(line)
          or (market == "total_points" and line <= 0)):
        return None, "invalid_game_spread_or_total_line"
    odds, dec = row.get("odds_american"), row.get("odds_decimal")
    if (type(odds) not in (int, float) or not math.isfinite(odds)
            or abs(odds) < 100 or type(dec) not in (int, float)
            or not math.isfinite(dec)):
        return None, "invalid_full_game_price"
    expected = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
    if abs(dec - expected) > 0.025:
        return None, "inconsistent_decimal_price"
    try:
        start = parse_time(row["event_start_time"])
        quoted = parse_time(row["timestamp"])
        received = parse_time(row["recorded_at"])
    except (KeyError, ValueError, TypeError, OverflowError):
        return None, "invalid_pregame_clock"
    if not (0 <= (received - quoted).total_seconds()
            <= MAX_PROVIDER_QUOTE_AGE_SECONDS
            and quoted < start and received < start):
        return None, "inplay_or_outdated_provider_receipt"
    key = (row["league"], eid, home, away, start, market, row["sportsbook"])
    return {"key": key, "raw": row, "quoted": quoted, "received": received,
            "start": start, "implied": implied(odds)}, None


def _snapshot(key, at, group):
    market = key[5]
    a, b = SIDES[market]
    first = [q for q in group if q["raw"]["selection_type"] == a]
    second = [q for q in group if q["raw"]["selection_type"] == b]
    if len(first) != 1 or len(second) != 1:
        return None, "unpaired_or_duplicate_game_market"
    first, second = first[0], second[0]
    va = first["raw"]["line"]
    vb = second["raw"]["line"]
    if market == "point_spread" and not math.isclose(va, -vb, abs_tol=1e-7):
        return None, "spread_sides_not_opposites"
    if market == "total_points" and not math.isclose(va, vb, abs_tol=1e-7):
        return None, "total_sides_different"
    total = first["implied"] + second["implied"]
    if not 1 <= total <= MAX_OVERROUND:
        return None, "implausible_full_game_vig"
    latest_receipt = max(first["received"], second["received"])
    return {
        "league": key[0], "provider_event_id": key[1],
        "home_team": key[2], "away_team": key[3],
        "start_utc": key[4].isoformat(),
        "market": market, "source_book_label": key[6],
        "provider_quote_utc": at.isoformat(),
        "source_received_utc": latest_receipt.isoformat(),
        "home_or_over_line": va, "away_or_under_line": vb,
        "home_or_over_odds": first["raw"]["odds_american"],
        "away_or_under_odds": second["raw"]["odds_american"],
        "home_or_over_no_vig_market_share": round(first["implied"] / total, 7),
        # The word "probability" here describes PRICE mathematics only:
        # normalized two-sided market quotes, never model forecasts or EV.
        **price_pair_probabilities(first["implied"], second["implied"]),
        "market_settlement_scope_independently_verified": False,
        "source_market_type": first["raw"]["market_type"],
        "provider_game_id_independently_verified": False,
        "bookmaker_checkout_price_verified": False,
        "native_model_probability_verified": False,
        "certified_positive_ev": False, "bet_ready": False,
    }, None


def summarize_full_game_markets(rows, *, now=None, archive_run_ids=()):
    if not isinstance(rows, list):
        raise ValueError("game_quote_rows_must_be_list")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_game_market_clock_required")
    clock = clock.astimezone(timezone.utc)
    excluded = Counter()
    groups = defaultdict(list)
    valid = Counter()
    for row in rows:
        info, reason = inspect_full_game_quote(row)
        if reason:
            # Other player-prop markets are not a full-game quote error.
            if (isinstance(row, dict) and row.get("league") in GAME_PRICE_SPORTS
                    and canonical_market(row.get("league"), row.get("market_type")) in ALLOWED):
                excluded[reason] += 1
            continue
        if info["received"] > clock:
            excluded["provider_receipt_after_audit_clock"] += 1
            continue
        valid[(info["key"][0], info["key"][5])] += 1
        groups[info["key"]].append(info)
    snapshots = []
    moves = []
    today = clock.astimezone(NY).date()
    for key, items in sorted(groups.items(), key=lambda x: (
            x[0][4], x[0][0], x[0][1], x[0][5])):
        by_quote = defaultdict(list)
        for item in items:
            by_quote[item["quoted"]].append(item)
        accepted = []
        for when, batch in sorted(by_quote.items()):
            snap, reason = _snapshot(key, when, batch)
            if reason:
                excluded[reason] += 1
            else:
                accepted.append(snap)
                snapshots.append(snap)
        for first, second in zip(accepted, accepted[1:]):
            if first["provider_quote_utc"] == second["provider_quote_utc"]:
                continue
            same_line = first["home_or_over_line"] == second["home_or_over_line"]
            delta_line = (None if first["home_or_over_line"] is None
                          else round(second["home_or_over_line"] -
                                     first["home_or_over_line"], 5))
            delta_pp = (round(100 * (
                second["home_or_over_no_vig_market_share"] -
                first["home_or_over_no_vig_market_share"]), 5)
                        if same_line else None)
            if (delta_pp is None and delta_line == 0) or (
                    delta_pp == 0 and delta_line in (None, 0)):
                continue
            moves.append({
                "league": key[0], "provider_event_id": key[1],
                "home_team": key[2], "away_team": key[3],
                "start_utc": key[4].isoformat(), "market": key[5],
                "prior_provider_quote_utc": first["provider_quote_utc"],
                "latest_provider_quote_utc": second["provider_quote_utc"],
                "latest_source_received_utc": second["source_received_utc"],
                "prior_line": first["home_or_over_line"],
                "latest_line": second["home_or_over_line"],
                "line_change": delta_line,
                "same_line_no_vig_market_price_change_pp": delta_pp,
                "changed_line_cannot_compare_probability": not same_line,
                "verified_sharp_money": False, "certified_positive_ev": False,
                "decision": "HOLD_MARKET_REPRICING_RESEARCH_ONLY",
            })
    recent = []
    for snap in snapshots:
        start = parse_time(snap["start_utc"])
        received = parse_time(snap["source_received_utc"])
        if start <= clock or received > clock or start.astimezone(NY).date() != today:
            continue
        minutes = (clock - received).total_seconds() / 60
        if 0 <= minutes <= MAX_RESEARCH_WATCHLIST_AGE_MINUTES:
            recent.append(dict(snap, source_age_minutes=round(minutes, 1)))
    by_game = defaultdict(dict)
    # For each market, show only the most recent paired provider snapshot.
    for snap in sorted(recent, key=lambda x: x["provider_quote_utc"]):
        k = (snap["league"], snap["provider_event_id"], snap["home_team"],
             snap["away_team"], snap["start_utc"])
        by_game[k][snap["market"]] = snap
    board = []
    for k, markets in sorted(by_game.items(), key=lambda x: (x[0][4], x[0][0])):
        board.append({
            "league": k[0], "provider_event_id": k[1],
            "home_team": k[2], "away_team": k[3], "start_utc": k[4],
            "paired_primary_markets": markets,
            "all_three_game_markets_present": len(markets) == 3,
            "independently_verified_provider_event_identity": False,
            "verified_sportsbook_checkout": False,
            "qualified_model_probability": False,
            "certified_positive_ev_bets": 0,
            "decision": "HOLD_RESEARCH_ONLY",
        })
    watch = [m for m in moves if (
        parse_time(m["start_utc"]).astimezone(NY).date() == today
        and parse_time(m["start_utc"]) > clock
        and 0 <= (clock - parse_time(m["latest_source_received_utc"])).total_seconds()
        <= 60 * MAX_RESEARCH_WATCHLIST_AGE_MINUTES)]
    watch.sort(key=lambda m: (
        -abs(m["line_change"] or 0),
        -abs(m["same_line_no_vig_market_price_change_pp"] or 0),
        m["start_utc"], m["provider_event_id"], m["market"]))
    report = {
        "report_type": "v8_six_league_two_outcome_game_markets_archived_research_only",
        "research_date_eastern": today.isoformat(),
        "validated_source_quote_observations_by_league_and_market": {
            f"{k[0]}_{k[1]}": n for k, n in sorted(valid.items())
        },
        "paired_primary_snapshots_historical": len(snapshots),
        "historical_full_game_market_movements": len(moves),
        "today_recent_upcoming_full_games": len(board),
        "today_recent_upcoming_market_movement_observations": len(watch),
        "today_game_market_board": board[:15],
        "today_recent_market_repricing_watchlist": watch[:15],
        "excluded_or_unpaired_reasons": dict(sorted(excluded.items())),
        "archive_run_ids": list(archive_run_ids),
        "independently_verified_model_probabilities": 0,
        "research_market_probabilities_available": len(snapshots),
        "research_price_probabilities_method": "american_odds_implied_and_pair_normalized_no_vig",
        "model_probability_display": "UNAVAILABLE_NOT_MODEL_GENERATED",
        "sharp_bettor_probability_display": "UNAVAILABLE_NO_SHARP_HANDLE_OR_TICKETS",
        "independently_verified_sportsbook_checkout_prices": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0, "stake_usd": 0,
        "champion_001_modified": False,
        "decision": "PASS_NO_INDEPENDENTLY_VERIFIED_FULL_GAME_EV",
        "warning": "Archived provider lines are not confirmed executable checkout quotes. "
                   "Movement at unchanged handicap lines is a market-price observation; "
                   "movement between different spread/total lines cannot be equated to "
                   "the same-outcome probability or a certified positive-EV bet.",
    }
    return report, moves
