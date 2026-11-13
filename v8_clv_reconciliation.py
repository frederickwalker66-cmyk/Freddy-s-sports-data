"""Read-only NBA closing-price reconciliation for LOCAL, private receipts.

Reprices use *exactly the same* event, market, selection, stat, line and
bookmaker. Prices and receipt metadata supplied by a user are not independently
authenticated merely by supplying hashes. This tool returns indicative
matched-price movement, NOT certified realized CLV, bettor edge or ROI.
Original private betting receipts should never be pushed to a public repo.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from decimal import Decimal
import argparse
import json
from pathlib import Path

from historical_outcomes import parse_time

MARKETS = {"moneyline", "point_spread", "total_points", "player_prop"}


def decimal_odds(n):
    if type(n) is not int or -99 <= n <= 99:
        raise ValueError("invalid_american_odds")
    return (Decimal(1) + (Decimal(n) / 100 if n > 0
            else Decimal(100) / Decimal(-n)))


def key(row):
    if not isinstance(row, dict):
        raise ValueError("price_receipt_must_be_object")
    if row.get("league") != "nba" or row.get("market") not in MARKETS:
        raise ValueError("NBA_exact_supported_market_required")
    for field in ("event_id", "sportsbook", "selection"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError("CLV_missing_receipt_identity_" + field)
    player = row.get("player_id")
    stat = row.get("prop_stat")
    if row["market"] == "player_prop":
        if not isinstance(player, str) or not player or not isinstance(stat, str) or not stat:
            raise ValueError("CLV_player_prop_requires_exact_ID_and_stat")
    elif player is not None or stat is not None:
        raise ValueError("CLV_nonplayer_market_has_player_identity")
    line = row.get("line")
    if row["market"] == "moneyline":
        if line is not None:
            raise ValueError("CLV_moneyline_must_not_have_line")
    elif type(line) not in (int, float) or not -1000 <= line <= 1000:
        raise ValueError("CLV_exact_market_line_required")
    decimal_odds(row.get("odds_american"))
    start, timestamp = parse_time(row.get("event_start_utc")), parse_time(
        row.get("quote_recorded_utc"))
    if not timestamp < start:
        raise ValueError("CLV_inplay_or_future_quote")
    return (
        row["event_id"], row["sportsbook"].lower(), row["market"],
        row["selection"].strip().lower(), line, player, stat, start,
    ), timestamp


def reconcile(entries, closing_quotes):
    """Compare matched reported prices; never attest to actual CLV."""
    if not isinstance(entries, list) or not isinstance(closing_quotes, list):
        raise ValueError("CLV_entry_close_arrays_required")
    if len(entries) > 1000 or len(closing_quotes) > 1000:
        raise ValueError("CLV_receipt_budget_exceeded")
    close_by_key = {}
    for close in closing_quotes:
        sig, ts = key(close)
        if sig in close_by_key:
            raise ValueError("CLV_multiple_closing_quotes_ambiguous")
        if not sig[-1] - timedelta(minutes=15) <= ts < sig[-1]:
            raise ValueError("CLV_quote_not_within_final_15_minutes")
        close_by_key[sig] = (close, ts)
    seen = set()
    paired, rejected = [], Counter()
    for entry in entries:
        sig, ts = key(entry)
        if sig in seen:
            raise ValueError("CLV_duplicate_original_market_entry")
        seen.add(sig)
        close = close_by_key.get(sig)
        if close is None:
            rejected["missing_identical_same_book_close"] += 1
            continue
        receipt, close_ts = close
        if ts >= close_ts:
            rejected["entry_not_before_close"] += 1
            continue
        entry_price = decimal_odds(entry["odds_american"])
        close_price = decimal_odds(receipt["odds_american"])
        improvement = (entry_price / close_price - 1) * Decimal(100)
        paired.append({
            "event_id": sig[0], "market": sig[2], "selection": sig[3],
            "line": sig[4], "player_id": sig[5], "prop_stat": sig[6],
            "entry_quote_utc": ts.isoformat(), "close_quote_utc": close_ts.isoformat(),
            "reported_entry_american": entry["odds_american"],
            "reported_close_american": receipt["odds_american"],
            "indicative_price_advantage_percent": round(float(improvement), 4),
            "original_receipts_independently_authenticated": False,
            "verified_realized_clv_percent": None,
        })
    return {
        "report_type": "NBA_REPORTED_ENTRY_TO_CLOSING_PRICE_RESEARCH_ONLY",
        "entry_quotes_supplied": len(entries),
        "closing_quotes_supplied": len(closing_quotes),
        "exact_same_book_event_market_line_pairs": len(paired),
        "indicative_matched_price_changes": paired,
        "unmatched_entry_reasons": dict(sorted(rejected.items())),
        "independent_source_custody_and_executable_quote_verified": False,
        "verified_realized_clv_percent": None,
        "certified_positive_ev_bets": 0, "champion_001_modified": False,
        "decision": "RESEARCH_ONLY_NO_AUTHENTICATED_CLV",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--local-input", required=True,
                   help="Private JSON with entries and closing_quotes; do NOT commit it")
    p.add_argument("--local-output", required=True)
    a = p.parse_args(argv)
    src, dst = Path(a.local_input), Path(a.local_output)
    if not src.is_file() or src.is_symlink() or dst.is_symlink() or src.resolve() == dst.resolve():
        raise ValueError("CLV_requires_separate_regular_local_input_and_output")
    data = json.loads(src.read_text(encoding="utf-8"))
    report = reconcile(data["entries"], data["closing_quotes"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"],
                      "research_only_exact_price_pairs": report["exact_same_book_event_market_line_pairs"],
                      "verified_realized_clv_percent": None}, sort_keys=True))


if __name__ == "__main__":
    main()
