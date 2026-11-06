"""V8 Edge Value research calculation. No implied odds as model probability.

Only independent pregame probability claims and timestamped bookmaker price
observations can enter the indicative leaderboard. This module cannot itself
authenticate receipts or checkout quotes; EVERY result stays research-only.
"""
from datetime import datetime, timezone
import math

from v8_elite_research_gate import breakeven_probability, expected_roi

SPORTS = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league"))
MARKETS = frozenset(("moneyline", "three_way_90_minute"))


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
    if side not in (("home", "away", "draw") if market == "three_way_90_minute" else ("home", "away")):
        raise ValueError("invalid_selection")
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
    }


def rank_research_edges(rows):
    if not isinstance(rows, list):
        raise ValueError("list_required")
    output, seen = [], set()
    for row in rows:
        item = research_edge(row)
        key = (item["league"], item["event_id"], item["market"],
               item["selection"], item["bookmaker"], item["price_recorded_utc"])
        if key in seen:
            raise ValueError("duplicate_market_quote")
        seen.add(key)
        if item["positive_ev_research_only"]:
            output.append(item)
    return sorted(output, key=lambda x: (-x["indicative_ev_roi_percent"], x["league"], x["event_id"]))
