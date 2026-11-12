"""Freddy's Picks AI V8: conservative cross-sportsbook arbitrage research.

No provider calls, wagers, verified checkouts, model probabilities or certified
profits. Quotes may be user-supplied or historical provider observations.
A positive mathematical screen DOES NOT establish an executable arbitrage:
prices can move, limits differ, markets can be voided and settlement terms vary.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import product
import argparse
import json
import math
from pathlib import Path
import re

LEAGUES = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab",
                     "mls", "uefa_champions_league"))
MARKET_SIDES = {
    "moneyline": ("home", "away"),
    "point_spread": ("home", "away"),
    "total_points": ("over", "under"),
    "player_prop": ("over", "under"),
    "three_way_90_minute": ("home", "draw", "away"),
}
SCOPE_PATTERN = re.compile(r"^[a-z0-9_]{5,90}$")
MAX_QUOTE_AGE_SECONDS = 120
MAX_GROUP_SKEW_SECONDS = 30
MAX_ROWS = 50000
MAX_BOOKS_PER_SIDE = 12
MAX_RESULT_GROUPS = 1000
CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _time(raw):
    if not isinstance(raw, str) or not raw:
        raise ValueError("missing_timestamp")
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def _decimal(raw):
    if type(raw) not in (int, float, str):
        raise ValueError("invalid_decimal")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError("invalid_decimal") from None
    if not value.is_finite():
        raise ValueError("non_finite_decimal")
    return value


def american_decimal(price):
    """Positive American odds and negative American odds -> decimal payout."""
    if type(price) is not int or abs(price) < 100 or abs(price) > 100000:
        raise ValueError("invalid_american_odds")
    return (Decimal(1) + Decimal(price) / HUNDRED if price > 0
            else Decimal(1) + HUNDRED / Decimal(abs(price)))


def _safe_name(raw, *, minimum=1):
    if not isinstance(raw, str) or len(raw.strip()) < minimum:
        raise ValueError("missing_exact_identity")
    return raw.strip()


def _parse(row, now):
    if not isinstance(row, dict):
        raise ValueError("row_not_object")
    lg, market = row.get("league"), row.get("market_type")
    if lg not in LEAGUES or market not in MARKET_SIDES:
        raise ValueError("unsupported_sport_or_market")
    if market == "three_way_90_minute" and lg not in ("mls", "uefa_champions_league"):
        raise ValueError("three_way_only_for_soccer")
    if lg in ("mls", "uefa_champions_league") and market != "three_way_90_minute":
        raise ValueError("soccer_other_settlements_not_supported")
    if market == "player_prop" and lg not in ("nba", "nfl"):
        raise ValueError("unsupported_player_prop_league")
    # A two-way NFL ML can refund on a tie, so two tickets are NOT a
    # guaranteed profitable two-outcome partition across every result.
    if lg == "nfl" and market == "moneyline":
        raise ValueError("nfl_tie_void_risk_moneyline_not_supported")
    if (row.get("record_type") != "pregame_odds_observation"
            or row.get("source") not in ("sharpapi_rest", "manual_research")
            or row.get("is_main_line") is not True
            or row.get("is_alternate_line") is not False
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None
            or row.get("is_live") not in (None, False)):
        raise ValueError("not_safe_primary_pregame_research_quote")
    side = row.get("selection_type")
    if side not in MARKET_SIDES[market]:
        raise ValueError("unrecognized_market_outcome")
    book = _safe_name(row.get("sportsbook"), minimum=2).casefold()
    event = _safe_name(row.get("event_id"))
    home = _safe_name(row.get("home_team"), minimum=2)
    away = _safe_name(row.get("away_team"), minimum=2)
    if home == away:
        raise ValueError("same_team_identity")
    scope = row.get("settlement_scope")
    if not isinstance(scope, str) or not SCOPE_PATTERN.fullmatch(scope):
        raise ValueError("explicit_settlement_scope_required")
    if market == "three_way_90_minute" and scope != "regulation_90_minutes":
        raise ValueError("soccer_regulation_scope_required")
    start = _time(row.get("event_start_utc") or row.get("event_start_time"))
    quoted = _time(row.get("quote_at_utc") or row.get("timestamp"))
    observed = _time(row.get("observed_at_utc") or row.get("recorded_at"))
    if not (quoted <= observed <= now < start):
        raise ValueError("quote_not_current_pregame")
    if ((observed - quoted).total_seconds() > MAX_QUOTE_AGE_SECONDS
            or (now - observed).total_seconds() > MAX_QUOTE_AGE_SECONDS):
        raise ValueError("stale_source_or_research_quote")
    odds = row.get("odds_american")
    decimal = american_decimal(odds)
    if row.get("odds_decimal") is not None:
        if abs(_decimal(row["odds_decimal"]) - decimal) > Decimal("0.025"):
            raise ValueError("inconsistent_decimal_odds")
    player_id = None
    stat = None
    handicap = None
    if market == "point_spread":
        line = _decimal(row.get("line"))
        handicap = line if side == "home" else -line
    elif market in ("total_points", "player_prop"):
        handicap = _decimal(row.get("line"))
        if handicap <= 0:
            raise ValueError("nonpositive_total_or_prop_line")
    elif row.get("line") is not None:
        raise ValueError("moneyline_has_unexpected_handicap")
    if market == "player_prop":
        player_id = _safe_name(row.get("player_id"), minimum=2)
        stat = _safe_name(row.get("prop_stat") or row.get("player_stat"), minimum=3)
    if market == "three_way_90_minute":
        if not row.get("draw_included_in_outcome_partition", False):
            raise ValueError("three_way_draw_scope_not_attested")
    key = (lg, event, home, away, start, market, scope, player_id,
           stat, handicap)
    return {"key": key, "side": side, "book": book, "decimal": decimal,
            "american": odds, "quoted": quoted, "observed": observed,
            "source": row["source"]}


def _stakes(legs, bankroll):
    weights = [Decimal(1) / leg["decimal"] for leg in legs]
    total = sum(weights)
    size = []
    for weight in weights[:-1]:
        size.append((bankroll * weight / total).quantize(CENT, rounding=ROUND_HALF_UP))
    size.append(bankroll - sum(size))
    if any(x <= 0 for x in size):
        return None
    payout = min(amount * leg["decimal"] for amount, leg in zip(size, legs))
    net = payout - bankroll
    if net <= 0:
        return None
    return {"stakes": size, "payout": payout, "profit": net,
            "inverse_sum": total}


def scan_arbitrage(rows, *, now=None, bankroll=100):
    """Evaluate exact-market theoretical cross-book mismatches, never bet.

    The caller must supply already obtained snapshots. Inputs never authorize
    checkout, real staking, betting account interaction or claim of genuine
    guaranteed profit. No market-implied probability is used as a model p.
    """
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("quotes_list_or_budget_invalid")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    now = now.astimezone(timezone.utc)
    stake_budget = _decimal(bankroll)
    if stake_budget < Decimal("1") or stake_budget > Decimal("10000"):
        raise ValueError("research_bankroll_outside_range")
    if stake_budget != stake_budget.quantize(CENT):
        raise ValueError("research_bankroll_must_be_cents")
    rejected = Counter()
    accepted = defaultdict(list)
    books_seen = set()
    for row in rows:
        try:
            info = _parse(row, now)
        except (ValueError, TypeError, OverflowError, KeyError) as exc:
            rejected[str(exc)] += 1
            continue
        accepted[(info["key"], info["side"], info["book"])].append(info)
        books_seen.add(info["book"])
    # Book's current offer supersedes its earlier quote: never pick a better
    # historical price when a newer quote at that book has replaced it.
    grouped = defaultdict(lambda: defaultdict(list))
    for (key, side, book), items in accepted.items():
        best_time = max((x["quoted"], x["observed"]) for x in items)
        latest = [x for x in items
                  if (x["quoted"], x["observed"]) == best_time]
        if len({x["american"] for x in latest}) != 1:
            rejected["conflicting_latest_same_book_prices"] += len(latest)
            continue
        grouped[key][side].append(latest[0])
    opportunities = []
    groups_checked = 0
    crossbook_groups = 0
    for key, market_sides in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        if groups_checked >= MAX_RESULT_GROUPS:
            rejected["group_budget_exceeded"] += 1
            break
        groups_checked += 1
        needed = MARKET_SIDES[key[5]]
        if not all(market_sides.get(outcome) for outcome in needed):
            rejected["not_full_outcome_partition"] += 1
            continue
        allbooks = {q["book"] for o in needed for q in market_sides[o]}
        if len(allbooks) < 2:
            rejected["single_book_no_crossbook_arbitrage"] += 1
            continue
        crossbook_groups += 1
        # Limit complexity without assuming discarded odds constitute proof.
        choices = []
        for side in needed:
            ranked = sorted(market_sides[side],
                            key=lambda q: (-q["decimal"], q["book"]))
            if len(ranked) > MAX_BOOKS_PER_SIDE:
                rejected["book_choice_budget_truncated"] += 1
            choices.append(ranked[:MAX_BOOKS_PER_SIDE])
        winner = None
        for combo in product(*choices):
            if len({leg["book"] for leg in combo}) < 2:
                continue
            times = [leg["quoted"] for leg in combo]
            if (max(times) - min(times)).total_seconds() > MAX_GROUP_SKEW_SECONDS:
                continue
            if sum(Decimal(1) / leg["decimal"] for leg in combo) >= 1:
                continue
            sizing = _stakes(combo, stake_budget)
            if not sizing:
                continue
            if winner is None or sizing["profit"] > winner[1]["profit"]:
                winner = (combo, sizing)
        if winner is None:
            continue
        legs, sized = winner
        opp = {
            "league": key[0], "event_id": key[1],
            "home_team": key[2], "away_team": key[3],
            "event_start_utc": key[4].isoformat(), "market_type": key[5],
            "settlement_scope_claimed_by_sources": key[6],
            "player_id": key[7], "player_stat": key[8],
            "canonical_home_spread_or_total_or_prop_line":
                str(key[9]) if key[9] is not None else None,
            "source_outcomes_complete_under_claimed_scope": True,
            "legs": [
                {"side": side, "sportsbook": q["book"],
                 "american_odds": q["american"],
                 "decimal_odds": float(q["decimal"]),
                 "research_stake_usd": str(stake),
                 "quote_at_utc": q["quoted"].isoformat(),
                 "observed_at_utc": q["observed"].isoformat(),
                 "quote_source": q["source"]}
                for side, q, stake in zip(needed, legs, sized["stakes"])
            ],
            "inverse_decimal_odds_sum": round(float(sized["inverse_sum"]), 7),
            "theoretical_roi_percent": round(
                float((Decimal(1) / sized["inverse_sum"] - 1) * HUNDRED), 4),
            "theoretical_min_payout_usd": str(
                sized["payout"].quantize(CENT, rounding=ROUND_HALF_UP)),
            "theoretical_min_profit_usd": str(
                sized["profit"].quantize(CENT, rounding=ROUND_HALF_UP)),
            "actual_bookmaker_checkout_prices_verified": False,
            "independent_settlement_rule_equivalence_verified": False,
            "real_bet_or_execution_confirmed": False,
            "decision": "HOLD_THEORETICAL_ARBITRAGE_NOT_EXECUTABLE",
        }
        opportunities.append(opp)
    opportunities.sort(key=lambda o: (-o["theoretical_roi_percent"],
                                      o["event_start_utc"], o["event_id"]))
    return {
        "stage": "v8_all_sports_crossbook_arbitrage_research_only",
        "as_of_utc": now.isoformat(),
        "input_quote_rows": len(rows),
        "accepted_sportsbook_names": sorted(books_seen),
        "exact_market_groups_checked": groups_checked,
        "multi_book_exact_market_groups": crossbook_groups,
        "theoretical_arbitrage_candidates": len(opportunities),
        "candidates": opportunities[:25],
        "research_stake_budget_usd": str(stake_budget),
        "excluded_or_unsupported": dict(sorted(rejected.items())),
        "independently_verified_checkout_quotes": 0,
        "independently_verified_settlement_rules": 0,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "native_model_probability_required": False,
        "native_model_probability_fabricated": False,
        "status": ("HOLD_THEORETICAL_CROSSBOOK_PRICE_GAPS_REQUIRE_EXECUTION_CHECK"
                   if opportunities else "HOLD_NO_VERIFIABLE_CROSSBOOK_ARBITRAGE"),
        "warning": ("Mathematical screens are NOT guarantees or verified bet opportunities. "
                    "Source book labels and settlement_scope strings are unauthenticated; "
                    "different sportsbook terms, NFL ties, voids/pushes, stake limits, fees, "
                    "unavailable offers and changing odds can erase gains. "
                    "No wagers, paid requests or Champion changes."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quotes", required=True,
                    help="Local JSONL already-captured matched sportsbook observations")
    ap.add_argument("--output", default="v8_results/ARBITRAGE_RESEARCH.json")
    ap.add_argument("--bankroll", type=str, default="100.00",
                    help="Illustrative stake cap only; never a real bet")
    args = ap.parse_args(argv)
    p = Path(args.quotes)
    if not p.is_file():
        raise FileNotFoundError(p)
    lines = p.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_ROWS:
        raise ValueError("quote_file_budget_exceeded")
    rows = [json.loads(s) for s in lines if s.strip()]
    report = scan_arbitrage(rows, bankroll=args.bankroll)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "theoretical_candidates": report["theoretical_arbitrage_candidates"],
                      "verified_bets": 0, "output": str(dest)}, sort_keys=True))


if __name__ == "__main__":
    main()
