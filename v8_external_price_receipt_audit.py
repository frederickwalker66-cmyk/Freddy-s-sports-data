"""Research-only reconciliation of first-observed forecasts and witnessed price receipts.

Provider-labeled SharpAPI odds are NOT direct DraftKings checkout. Signed
third-party observation is evidence of a witness claim, not a signature by
the sportsbook or proof that the quote was executable. Never certify +EV.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import base64
import json
import math
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from challenger_authenticated_chronological_dataset import (
    canon, key_from_path, original_bytes, sha256, read_jsonl)
from challenger_prospective_outcome_validation import instant

MAX_AGE_SECONDS = 120
MAX_FORECAST_ROWS = 100000
VALID_MARKETS = {"moneyline", "three_way_result"}


def exact_first_forecasts(rows, now):
    """Earliest pre-start forecast wins; conflicts never replace originals."""
    selected, excluded = {}, Counter()
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("invalid_forecast_object")
            if (row.get("research_only") is not True or
                    row.get("champion_001_modified") is not False or
                    row.get("certified_prediction") is not False or
                    row.get("bet_ready") is not False):
                raise ValueError("must_remain_uncertified_research")
            league, eid = row["league"], row["event_id"]
            if not (isinstance(league, str) and isinstance(eid, str) and eid.isdigit()):
                raise ValueError("bad_forecast_identity")
            if row.get("market_type") not in VALID_MARKETS:
                raise ValueError("unsupported_game_market")
            if row.get("selection") not in ("home", "away", "draw"):
                raise ValueError("invalid_forecast_side")
            if row["market_type"] == "moneyline" and row["selection"] == "draw":
                raise ValueError("unsupported_moneyline_draw")
            start, time = instant(row["start_utc"]), instant(row["forecast_utc"])
            if not (time <= now and time < start):
                raise ValueError("post_start_forecast")
            prob = row.get("model_probability")
            if type(prob) not in (float, int) or not math.isfinite(prob) or not 0 < prob < 1:
                raise ValueError("invalid_independent_probability")
            if not isinstance(row.get("model_version"), str) or not row["model_version"]:
                raise ValueError("no_model_version")
            key = (league, eid, row["market_type"], row["selection"],
                   row.get("line"), row.get("settlement_scope"))
            if key in selected:
                original = selected[key]
                if instant(original["forecast_utc"]) <= time:
                    excluded["later_forecast_not_first"] += 1
                    continue
                excluded["earlier_original_supersedes_later"] += 1
            selected[key] = row
        except (ValueError, KeyError, TypeError) as e:
            excluded[str(e)] += 1
    return selected, excluded


def expected_checkout_witness(quote):
    keys = ("league", "event_id", "market_type", "selection", "line",
            "settlement_scope", "start_utc", "captured_at_utc",
            "price_american", "source_url", "original_sha256")
    if any(k not in quote for k in keys):
        raise ValueError("missing_exact_bookmaker_quote_fields")
    return {"role": "independent_checkout_observer",
            **{key: quote[key] for key in keys}}


def witness_quote(quote, root, trusted_key, now):
    if trusted_key is None:
        raise ValueError("no_external_checkout_witness_key")
    if not isinstance(quote, dict):
        raise ValueError("invalid_quote")
    if (quote.get("source") != "draftkings_original_checkout_capture"
            or quote.get("provider") != "DraftKings"
            or quote.get("source_scope") != "user_visible_exact_checkout"):
        raise ValueError("not_a_direct_checkout_receipt")
    source = quote.get("source_url")
    if not isinstance(source, str) or not source.startswith("https://sportsbook.draftkings.com/"):
        raise ValueError("unsupported_checkout_origin_claim")
    if quote.get("market_type") not in VALID_MARKETS:
        raise ValueError("unsupported_checkout_market")
    price = quote.get("price_american")
    if type(price) is not int or not (price <= -100 or price >= 100):
        raise ValueError("invalid_american_price")
    captured, start = instant(quote["captured_at_utc"]), instant(quote["start_utc"])
    if not captured <= now or not captured < start:
        raise ValueError("stale_or_post_start_checkout")
    witness = quote.get("external_witness")
    expected = expected_checkout_witness(quote)
    if not isinstance(witness, dict) or set(witness) != {"attestation", "signature_b64", "original_path"}:
        raise ValueError("no_external_checkout_witness")
    if witness["attestation"] != expected:
        raise ValueError("quote_witness_market_mismatch")
    try:
        signature = base64.b64decode(witness["signature_b64"], validate=True)
        trusted_key.verify(signature, canon(expected))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise ValueError("invalid_checkout_witness_signature") from exc
    if sha256(original_bytes(root, witness["original_path"])) != quote["original_sha256"]:
        raise ValueError("checkout_original_bytes_hash_mismatch")
    return captured


def reconcile(forecasts, quotes, root, key=None, now=None):
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    if len(forecasts) > MAX_FORECAST_ROWS or len(quotes) > MAX_FORECAST_ROWS:
        raise ValueError("oversized_quote_or_forecast_batch")
    first, exclusions = exact_first_forecasts(forecasts, now)
    matched, rejected = [], Counter()
    used = set()
    for quote in quotes:
        try:
            capture = witness_quote(quote, root, key, now)
            identity = (quote["league"], quote["event_id"], quote["market_type"],
                        quote["selection"], quote.get("line"), quote["settlement_scope"])
            if identity not in first:
                raise ValueError("no_exact_first_forecast_for_quote")
            f = first[identity]
            if instant(f["start_utc"]) != instant(quote["start_utc"]):
                raise ValueError("game_start_clock_mismatch")
            ftime = instant(f["forecast_utc"])
            if not (ftime <= capture and (capture - ftime).total_seconds() <= MAX_AGE_SECONDS):
                raise ValueError("quote_not_within_forecast_window")
            if identity in used:
                raise ValueError("duplicate_quote_for_first_forecast")
            used.add(identity)
            # Expected-value arithmetic only as a NONCERTIFIED research example.
            odds = quote["price_american"]
            profit_per_unit = odds / 100 if odds > 0 else 100 / abs(odds)
            raw_research_ev = float(f["model_probability"]) * profit_per_unit - (
                1 - float(f["model_probability"]))
            matched.append({
                "league": identity[0], "event_id": identity[1],
                "market_type": identity[2], "selection": identity[3],
                "first_forecast_utc": f["forecast_utc"],
                "witnessed_quote_utc": quote["captured_at_utc"],
                "model_version": f["model_version"],
                "research_ev_not_certified": round(raw_research_ev, 6),
                "bet_ready": False, "certified_positive_ev": False,
                "sportsbook_signed_original_verified": False,
            })
        except (KeyError, TypeError, ValueError, OSError) as exc:
            rejected[str(exc)] += 1
    return {
        "version": "v8-original-forward-external-checkout-research-audit-v1",
        "first_pregame_forecasts_preserved": len(first),
        "later_or_invalid_forecasts_excluded": dict(exclusions),
        "externally_witnessed_quote_pairs_research_only": len(matched),
        "quotes_rejected": dict(rejected),
        "quote_candidates": matched,
        "independently_verified_live_sportsbook_checkout_quotes": 0,
        "certified_independent_model_probabilities": 0,
        "certified_positive_ev_picks": 0,
        "automated_bets_placed": 0,
        "bet_ready": False, "champion_001_modified": False,
        "decision": "HOLD_RESEARCH_WITNESS_IS_NOT_SPORTSBOOK_CERTIFICATION",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--forecasts", default="absent_independent_forward_forecasts.jsonl")
    p.add_argument("--quotes", default="absent_external_direct_checkout_quotes.jsonl")
    p.add_argument("--original-root", default="original_checkout_captures")
    p.add_argument("--checkout-witness-public-key")
    p.add_argument("--out", default="challenger_results/forward_price_witness_audit.json")
    args = p.parse_args(argv)
    key = key_from_path(args.checkout_witness_public_key) if args.checkout_witness_public_key else None
    report = reconcile(read_jsonl(args.forecasts), read_jsonl(args.quotes), args.original_root, key)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canon(report) + b"\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
