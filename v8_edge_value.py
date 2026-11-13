"""V8 Edge Value research calculation. No implied odds as model probability.

Only independent pregame probability claims and timestamped bookmaker price
observations can enter the indicative leaderboard. This module cannot itself
authenticate receipts or checkout quotes; EVERY result stays research-only.
"""
from datetime import datetime, timezone
import math

from v8_elite_research_gate import breakeven_probability, expected_roi

SPORTS = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league"))
MARKETS = frozenset(("moneyline", "point_spread", "total_points", "three_way_90_minute", "player_prop"))
# Exact stat/settlement targets; different markets and player identities must
# never share a probability simply because the same game is involved.
PLAYER_PROP_STATS = {
    "nba": frozenset(("points", "rebounds", "assists", "three_pointers_made",
                      "steals", "blocks", "turnovers", "points_rebounds_assists")),
    "nfl": frozenset(("passing_yards", "passing_touchdowns", "rushing_yards",
                      "rushing_touchdowns", "receiving_yards", "receptions",
                      "receiving_touchdowns")),
}


def instant(value):
    if not isinstance(value, str):
        raise ValueError("missing_time")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def research_edge(row):
    if not isinstance(row, dict):
        raise ValueError("row_not_object")
    league = row.get("league")
    if league not in SPORTS:
        raise ValueError("unsupported_league")
    market = row.get("market")
    if market not in MARKETS:
        raise ValueError("unsupported_market")
    if (league in ("mls", "uefa_champions_league")) != (market == "three_way_90_minute"):
        raise ValueError("league_market_scope_mismatch")
    if market == "player_prop" and league not in PLAYER_PROP_STATS:
        raise ValueError("unsupported_player_prop_league")
    if market in ("point_spread", "total_points") and league not in ("nba", "nfl"):
        raise ValueError("exact_game_spread_total_model_supported_for_nba_nfl_only")
    if league == "nfl" and market == "moneyline":
        # V8's NFL Elo forecasts are conditional on NOT a tie; using them
        # directly as full-moneyline win probabilities is a category error.
        if (row.get("model_target") != "NFL_fullgame_moneyline_ties_refunds_reviewed"
                or row.get("independent_market_settlement_review") is not True):
            raise ValueError("nfl_conditional_elo_is_not_a_market_moneyline")
    if not isinstance(row.get("event_id"), str) or not row["event_id"].strip():
        raise ValueError("event_id_missing")
    if row.get("champion_001_modified") is not False:
        raise ValueError("champion_integrity_unverified")
    if row.get("model_probability_source") != "native_independent_pregame":
        raise ValueError("market_implied_probability_not_allowed")
    if not isinstance(row.get("model_version"), str) or not row["model_version"].strip():
        raise ValueError("model_version_required")
    if row.get("independent_model_review") is not True or row.get("independent_price_review") is not True:
        raise ValueError("review_attestations_required")
    bookmaker = row.get("bookmaker")
    if not isinstance(bookmaker, str) or not bookmaker.strip():
        raise ValueError("bookmaker_missing")
    side = row.get("selection")
    allowed = (("over", "under") if market in ("player_prop", "total_points") else
               ("home", "away", "draw") if market == "three_way_90_minute"
               else ("home", "away"))
    if side not in allowed:
        raise ValueError("invalid_selection")
    # Exact full-game market probabilities must target the selected handicap
    # and the exact settlement event; inferred moneyline p is NOT a cover p.
    # Require half-point lines to avoid push handling from non-binary outcomes.
    game_fields = {}
    if market in ("point_spread", "total_points"):
        line = row.get("line")
        target = f"{league}_fullgame_{'point_spread_cover' if market == 'point_spread' else 'total_points_overunder'}"
        if (type(line) not in (int, float) or not math.isfinite(line)
                or (market == "total_points" and line <= 0)
                or abs(line * 2 - round(line * 2)) > 1e-7
                or int(round(abs(line) * 2)) % 2 != 1
                or row.get("is_alternate_line") is not False):
            raise ValueError("exact_non_alt_half_point_game_market_required")
        if (row.get("model_target") != target
                or row.get("independent_market_settlement_review") is not True
                or row.get("independent_exact_line_model_review") is not True):
            raise ValueError("exact_line_spread_total_model_and_settlement_review_required")
        game_fields = {"line": float(line), "model_target": target,
                       "game_handicap_and_settlement_reviewed": True}
    elif market == "moneyline" and row.get("line") is not None:
        raise ValueError("moneyline_must_not_have_handicap_line")
    prop_fields = {}
    if market == "player_prop":
        player_id, player_name, stat, line = (
            row.get("player_id"), row.get("player_name"),
            row.get("prop_stat"), row.get("line"))
        if (type(player_id) not in (str, int) or not str(player_id).strip()
                or not isinstance(player_name, str) or not player_name.strip()
                or stat not in PLAYER_PROP_STATS[league]
                or type(line) not in (int, float) or not math.isfinite(line)
                or line < 0 or row.get("is_alternate_line") is not False):
            raise ValueError("exact_non_alt_player_stat_line_required")
        if (row.get("independent_player_active_review") is not True
                or row.get("independent_prop_stat_settlement_review") is not True
                or row.get("independent_prop_model_review") is not True):
            raise ValueError("player_availability_stat_and_model_review_required")
        prop_fields = {
            "player_id": str(player_id), "player_name": player_name.strip(),
            "prop_stat": stat, "line": float(line),
            "independent_player_active_claim_not_authenticated_here": True,
        }
    start, captured, quote = (instant(row.get(k)) for k in (
        "start_utc", "model_forecast_recorded_utc", "price_recorded_utc"))
    if not captured < start or not quote < start:
        raise ValueError("not_pregame")
    if abs((quote - captured).total_seconds()) > 900:
        raise ValueError("price_and_forecast_not_near_in_time")
    p = row.get("model_probability")
    if type(p) not in (float, int) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("invalid_native_model_probability")
    odds = row.get("american_odds")
    implied = breakeven_probability(odds)
    roi = expected_roi(p, odds)
    return {
        "league": league, "event_id": row["event_id"],
        "market": market, "selection": side, "bookmaker": bookmaker,
        "price_recorded_utc": quote.isoformat(),
        "model_version": row["model_version"],
        "indicative_model_probability": p,
        "american_odds": odds,
        "break_even_probability": round(implied, 8),
        "indicative_edge_percentage_points": round(100 * (p - implied), 5),
        "indicative_ev_roi_percent": round(100 * roi, 5),
        "positive_ev_research_only": roi > 0,
        "verified_executable_checkout_price": False,
        "independent_receipt_authentication_performed": False,
        "certified_prediction": False, "bet_ready": False, "stake_usd": 0,
        **game_fields, **prop_fields,
    }


def rank_research_edges(rows):
    if not isinstance(rows, list):
        raise ValueError("list_required")
    output, seen = [], set()
    for row in rows:
        item = research_edge(row)
        key = (item["league"], item["event_id"], item["market"],
               item["selection"], item["bookmaker"], item["price_recorded_utc"],
               item.get("player_id"), item.get("prop_stat"), item.get("line"))
        if key in seen:
            raise ValueError("duplicate_market_quote")
        seen.add(key)
        if item["positive_ev_research_only"]:
            output.append(item)
    return sorted(output, key=lambda x: (-x["indicative_ev_roi_percent"], x["league"], x["event_id"]))
