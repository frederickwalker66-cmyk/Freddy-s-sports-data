"""Read-only, privacy-preserving audit of a placed or proposed parlay.

This is *not* a betting engine. User-entered odds, results and source labels
are untrusted; no native win probability, certified EV, independent sharp flow,
realized CLV, or settlement may be inferred from them. Champion-001 is frozen.
Personal bet receipts must stay outside a public GitHub repository.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
from pathlib import Path

ALLOWED_LEAGUES = frozenset((
    "nba", "nfl", "nhl", "mlb", "ncaaf", "ncaab", "mls", "uefa_champions_league",
))
ALLOWED_MARKETS = frozenset((
    "moneyline", "point_spread", "total_points", "player_prop",
))
MIN_CENTS = Decimal("0.01")


def _time(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + "_missing")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(label + "_invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(label + "_must_have_timezone")
    return result.astimezone(timezone.utc)


def _cash(value, label, *, allow_zero=False):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError(label + "_invalid")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(label + "_invalid") from exc
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError(label + "_invalid")
    if amount != amount.quantize(MIN_CENTS):
        raise ValueError(label + "_requires_cents_precision")
    return amount


def _odds(value):
    if type(value) is not int or value == 0 or abs(value) < 100:
        raise ValueError("invalid_american_odds")
    return Decimal(1) + (Decimal(value) / 100 if value > 0
                         else Decimal(100) / Decimal(-value))


def _valid_line(value):
    return type(value) in (int, float) and math.isfinite(value)


def audit_ticket(ticket):
    """Fail closed on outcomes, CLV, model probabilities, and joint parlay EV.

    Inputs document *reported* ticket facts only. They are never treated as
    independently authenticated receipts, verified active athletes, or
    externally settled outcomes. A separate independently audited review
    process is required to certify any of those claims.
    """
    if not isinstance(ticket, dict):
        raise ValueError("ticket_must_be_object")
    if ticket.get("schema_version") != 1 or type(ticket.get("schema_version")) is not int:
        raise ValueError("unsupported_ticket_schema_version")
    kind = ticket.get("ticket_kind")
    if kind not in ("placed", "research"):
        raise ValueError("ticket_kind_must_be_placed_or_research")
    legs = ticket.get("legs")
    if not isinstance(legs, list) or not 1 <= len(legs) <= 25:
        raise ValueError("leg_count_must_be_1_to_25")
    if not isinstance(ticket.get("bookmaker"), str) or not ticket["bookmaker"].strip():
        raise ValueError("bookmaker_required")
    accepted = None
    payout = {"displayed_payout_usd": None, "calculated_payout_usd": None,
              "reported_payout_math_matches": None, "break_even_price_percent": None}
    if kind == "placed":
        accepted = _time(ticket.get("accepted_at"), "accepted_at")
        stake = _cash(ticket.get("stake_usd"), "stake_usd")
        decimal_odds = _odds(ticket.get("accepted_american_odds"))
        calculated = (stake * decimal_odds).quantize(MIN_CENTS, rounding=ROUND_HALF_UP)
        given = ticket.get("displayed_total_payout_usd")
        displayed = _cash(given, "displayed_total_payout_usd") if given is not None else None
        payout = {
            "stake_usd": str(stake),
            "accepted_american_odds": ticket["accepted_american_odds"],
            "displayed_payout_usd": str(displayed) if displayed is not None else None,
            "calculated_payout_usd": str(calculated),
            "reported_payout_math_matches": displayed == calculated if displayed is not None else None,
            "break_even_price_percent": round(float(100 / decimal_odds), 4),
        }
    else:
        # Proposed/research picks must NEVER be represented as accepted bets.
        if any(key in ticket for key in ("accepted_at", "stake_usd",
                                         "accepted_american_odds", "displayed_total_payout_usd")):
            raise ValueError("research_ticket_cannot_have_accepted_wager")
    by_event, by_player = defaultdict(list), defaultdict(list)
    duplicate_check = set()
    outcome_claims = 0
    model_claims = 0
    close_claims = 0
    for idx, leg in enumerate(legs, 1):
        if not isinstance(leg, dict):
            raise ValueError("leg_must_be_object")
        league, market = leg.get("league"), leg.get("market")
        if league not in ALLOWED_LEAGUES or market not in ALLOWED_MARKETS:
            raise ValueError("unsupported_league_or_market")
        event, selection = leg.get("event_id"), leg.get("selection")
        if not isinstance(event, str) or not event.strip():
            raise ValueError("event_id_required")
        if not isinstance(selection, str) or not selection.strip():
            raise ValueError("selection_required")
        start = _time(leg.get("event_start"), "event_start")
        if accepted is not None and accepted >= start:
            raise ValueError("accepted_after_event_start")
        line = leg.get("line")
        if market in ("point_spread", "total_points", "player_prop"):
            if not _valid_line(line):
                raise ValueError("exact_market_line_required")
        elif line is not None:
            raise ValueError("moneyline_must_not_have_handicap_line")
        player = leg.get("player_name")
        stat = leg.get("prop_stat")
        if market == "player_prop":
            if not isinstance(player, str) or not player.strip():
                raise ValueError("player_name_required")
            if not isinstance(stat, str) or not stat.strip():
                raise ValueError("prop_stat_required")
        elif player is not None or stat is not None:
            raise ValueError("nonprop_must_not_have_player_fields")
        signature = (league, event, market, selection.strip().lower(), line,
                     (player or "").strip().lower(), (stat or "").strip().lower())
        if signature in duplicate_check:
            raise ValueError("duplicate_exact_leg")
        duplicate_check.add(signature)
        by_event[(league, event)].append(idx)
        if market == "player_prop":
            by_player[(league, event, player.strip().casefold())].append(idx)
        outcome_claims += int("reported_outcome" in leg)
        model_claims += int("model_probability" in leg)
        close_claims += int("closing_quote" in leg)
    same_game = [
        {"league": league, "event_id": event, "leg_numbers": numbers}
        for (league, event), numbers in sorted(by_event.items()) if len(numbers) > 1
    ]
    same_player = [
        {"league": league, "event_id": event,
         "player_name_as_supplied": player, "leg_numbers": numbers}
        for (league, event, player), numbers in sorted(by_player.items()) if len(numbers) > 1
    ]
    warnings = []
    if same_game:
        warnings.append("same_game_legs_are_correlated_do_not_multiply_independent_probabilities")
    if same_player:
        warnings.append("same_player_props_require_joint_outcome_model")
    if outcome_claims:
        warnings.append("user_reported_outcomes_unverified_no_settlement_grading")
    if model_claims:
        warnings.append("user_supplied_probabilities_not_native_calibrated_forecasts")
    if close_claims:
        warnings.append("closing_quote_claims_not_independent_authenticated_clv")
    if payout["reported_payout_math_matches"] is False:
        warnings.append("displayed_payout_disagrees_with_american_odds_check_boost_and_receipt")
    return {
        "report_type": "FREDDYS_PLACED_VS_RESEARCH_PARLAY_AUDIT",
        "ticket_kind": kind,
        "reported_placed_bets": 1 if kind == "placed" else 0,
        "research_ticket_count": 0 if kind == "placed" else 1,
        "leg_count": len(legs),
        "payout_price_math": payout,
        "same_event_groups": same_game,
        "same_player_groups": same_player,
        "correlation_risk_flagged": bool(same_game),
        "warning_codes": warnings,
        "reported_outcome_claim_count_not_graded": outcome_claims,
        "reported_model_probability_claim_count_not_certified": model_claims,
        "reported_closing_quote_claim_count_not_verified": close_claims,
        "independently_verified_outcomes": 0,
        "parlay_settlement": None,
        "actual_winnings_usd": None,
        "joint_model_win_probability_percent": None,
        "certified_parlay_expected_value_percent": None,
        "verified_realized_clv_percent": None,
        "independently_certified_calibration": False,
        "certified_positive_ev_bets": 0,
        "champion_001_modified": False,
        "automated_wagers": 0,
        "decision": "HOLD_NO_INDEPENDENTLY_CERTIFIED_PROBABILITY_PRICE_AND_SETTLEMENT",
        "requires": [
            "original authenticated sportsbook accepted ticket and exact combined price",
            "independent calibrated pregame probability for the exact joint parlay settlement",
            "verified independent outcomes for every settled leg",
            "matched same-settlement authenticated entry and closing prices before computing CLV",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticket-file", required=True,
                   help="LOCAL private JSON receipt; never upload it to a public repository")
    p.add_argument("--output", required=True, help="LOCAL read-only audit output JSON")
    args = p.parse_args(argv)
    source = Path(args.ticket_file)
    if not source.is_file() or source.is_symlink():
        raise ValueError("ticket_file_must_be_local_regular_file")
    target = Path(args.output)
    if target.resolve() == source.resolve():
        raise ValueError("audit_output_must_not_overwrite_original_receipt")
    if target.is_symlink():
        raise ValueError("audit_output_symlink_not_allowed")
    ticket = json.loads(source.read_text(encoding="utf-8"))
    result = audit_ticket(ticket)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "legs": result["leg_count"],
                      "report": str(target), "certified_bets": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
