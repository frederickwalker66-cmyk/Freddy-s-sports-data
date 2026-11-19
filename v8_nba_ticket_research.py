"""Fail-closed, exact-line audit of a *named* NBA research parlay.

Only already-captured, bounded, paired SharpAPI research reports are inspected.
No provider calls, wagers, Champion modifications, certified EV or fake prices.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import unicodedata
from zoneinfo import ZoneInfo

from v8_parlay_risk_audit import audit_ticket

NY = ZoneInfo("America/New_York")
# Research-only archives are not checkout prices. Old/future/no-time
# observations must not be labeled as today's exact-price references.
MAX_RESEARCH_QUOTE_AGE_SECONDS = 600


def _quote_age_minutes(value, *, clock, game_start):
    """Age of a genuine pregame archive receipt; None means not usable."""
    try:
        captured = _date(value)
    except (ValueError, TypeError, OverflowError):
        return None
    age = (clock - captured).total_seconds()
    if not 0 <= age <= MAX_RESEARCH_QUOTE_AGE_SECONDS or captured >= game_start:
        return None
    return round(age / 60, 2)


def _quoted_odds(value):
    return type(value) is int and abs(value) >= 100 and value != 0



def _clock(value=None):
    result = value or datetime.now(timezone.utc)
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise ValueError("aware_ticket_audit_clock_required")
    return result.astimezone(timezone.utc)


def _date(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("ticket_start_requires_timezone")
    return dt.astimezone(timezone.utc)


def _name(value):
    if not isinstance(value, str):
        return None
    # Diacritic removal/LA alias are matching aids for RESEARCH only.
    # Neither certifies an athlete's provider ID or active roster status.
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    result = " ".join(folded.split())
    return {"la clippers": "los angeles clippers"}.get(result, result)


def _source_safe(report, key):
    if not isinstance(report, dict):
        raise ValueError("missing_" + key + "_research_report")
    if report.get("certified_positive_ev_bets") != 0 or report.get("champion_001_modified") is not False:
        raise ValueError("untrusted_" + key + "_report")
    return report


def _compare_reference(leg, full_games, props, *, clock):
    # Match exact game, UTC start, market/selection, player and same numeric
    # threshold. A player name is NOT a verified roster identity.
    market, side = leg["market"], leg["selection"]
    for entry in ((full_games.get("today_game_market_board") or []) if market != "player_prop"
                  else (props.get("today_player_prop_market_probability_board") or {}).get("nba", [])):
        if not isinstance(entry, dict) or entry.get("league") != "nba":
            continue
        if (_name(entry.get("home_team")) != _name(leg.get("home_team"))
                or _name(entry.get("away_team")) != _name(leg.get("away_team"))):
            continue
        try:
            start = _date(entry["start_utc"])
        except (KeyError, ValueError, TypeError):
            continue
        if start <= clock or abs((start - _date(leg["event_start"])).total_seconds()) > 60:
            continue
        if market == "player_prop":
            if (side not in ("over", "under")
                    or _name(entry.get("player_name")) != _name(leg.get("player_name"))
                    or entry.get("prop_stat") != leg.get("prop_stat")
                    or entry.get("line") != leg.get("line")):
                continue
            if (entry.get("active_player_independently_verified") is not False
                    or entry.get("player_identity_independently_verified") is not False
                    or entry.get("bet_ready") is not False):
                raise ValueError("prop_unverified_receipt_illegally_promoted")
            quote_age = _quote_age_minutes(entry.get("last_capture_utc"),
                                          clock=clock, game_start=start)
            if (quote_age is None
                    or not _quoted_odds(entry.get("over_american_odds"))
                    or not _quoted_odds(entry.get("under_american_odds"))):
                continue
            return {
                "research_source_price": entry.get(side + "_american_odds"),
                "captured_at_utc": entry.get("last_capture_utc"),
                "research_quote_age_minutes": quote_age,
                "source_player_name_only_unverified": True,
            }
        pair = (entry.get("paired_primary_markets") or {}).get(market)
        if not isinstance(pair, dict) or side not in ("home", "away", "over", "under"):
            continue
        first = side in ("home", "over")
        prefix = "home_or_over" if first else "away_or_under"
        if pair.get(prefix + "_line") != leg.get("line"):
            continue
        if (entry.get("verified_sportsbook_checkout") is not False
                or entry.get("qualified_model_probability") is not False
                or pair.get("bookmaker_checkout_price_verified") is not False
                or pair.get("native_model_probability_verified") is not False):
            raise ValueError("game_unverified_receipt_illegally_promoted")
        quote_age = _quote_age_minutes(pair.get("source_received_utc"),
                                      clock=clock, game_start=start)
        if (quote_age is None
                or not _quoted_odds(pair.get("home_or_over_odds"))
                or not _quoted_odds(pair.get("away_or_under_odds"))):
            continue
        return {
            "research_source_price": pair.get(prefix + "_odds"),
            "captured_at_utc": pair.get("source_received_utc"),
            "research_quote_age_minutes": quote_age,
            "source_player_name_only_unverified": False,
        }
    return None


def audit_named_ticket(ticket, game_report, prop_report, *, now=None):
    """Run existing correlation gate, then a separately qualified exact-line audit."""
    clock = _clock(now)
    prior = audit_ticket(ticket)
    if ticket.get("ticket_kind") != "research" or prior["leg_count"] != len(ticket["legs"]):
        raise ValueError("research_ticket_only")
    if any(leg.get("league") != "nba" for leg in ticket["legs"]):
        raise ValueError("nba_only_ticket_required")
    games = _source_safe(game_report, "game")
    props = _source_safe(prop_report, "prop")
    day = clock.astimezone(NY).date().isoformat()
    ticket_date = ticket.get("ticket_date_et")
    if not isinstance(ticket_date, str) or len(ticket_date) != 10:
        raise ValueError("ticket_date_et_required")
    expired = ticket_date != day
    rows = []
    for n, leg in enumerate(ticket["legs"], 1):
        if any(not isinstance(leg.get(k), str) or not leg[k] for k in
               ("home_team", "away_team", "event_start", "selection", "market")):
            raise ValueError("ticket_requires_exact_matchup_and_start")
        if _date(leg["event_start"]).astimezone(NY).date().isoformat() != ticket_date:
            raise ValueError("leg_date_does_not_match_ticket_date")
        reference = None if expired else _compare_reference(leg, games, props, clock=clock)
        source_status = ("EXPIRED_REFERENCE_DATE" if expired else
                         "PAIRED_PROVIDER_REFERENCE_NOT_CHECKOUT" if reference else
                         "NO_RECENT_EXACT_TWO_SIDED_ARCHIVE_REFERENCE")
        rejected_previously = (
            str(leg.get("prior_disposition", "")).upper() in ("HOLD", "PASS", "REJECT")
        )
        rows.append({
            "leg_number": n,
            "selection_as_requested": leg["selection"],
            "event_id_as_supplied_not_provider_verified": leg["event_id"],
            "market": leg["market"],
            "line": leg.get("line"),
            "player": leg.get("player_name"),
            "previously_reported_odds_not_current": leg.get("prior_reference_odds"),
            "source_market_status": source_status,
            "fresh_archived_price_not_executable": reference["research_source_price"] if reference else None,
            "archived_capture_utc": reference["captured_at_utc"] if reference else None,
            "reference_quote_age_minutes": reference["research_quote_age_minutes"] if reference else None,
            "previously_held_or_rejected": rejected_previously,
            "eligible_for_certified_parlay": False,
            "model_probability": None,
            "certified_expected_value": None,
            "verified_checkout_price": None,
            "action": "HOLD",
        })
    return {
        "report_type": "NBA_EXACT_NAMED_RESEARCH_TICKET_SHARP_EDGE_V1",
        "ticket_date_et": ticket_date,
        "checked_at_utc": clock.isoformat(),
        "legs": rows,
        "leg_count": len(rows),
        "current_qualified_two_sided_reference_count": sum(
            x["source_market_status"] == "PAIRED_PROVIDER_REFERENCE_NOT_CHECKOUT" for x in rows),
        "same_event_groups": prior["same_event_groups"],
        "same_player_groups": prior["same_player_groups"],
        "correlation_risk_flagged": prior["correlation_risk_flagged"],
        "structural_risk_flags": prior["structural_risk_flags"],
        "previously_held_or_rejected_leg_numbers": prior["prior_pass_hold_reject_leg_numbers"],
        "max_archive_reference_age_seconds": MAX_RESEARCH_QUOTE_AGE_SECONDS,
        "certified_eight_leg_locks": 0,
        "eight_leg_betting_verdict": "NO_LOCK_PASS_UNTIL_EIGHT_INDEPENDENT_MARKET_APPROVALS",
        "verified_champion_001_probabilities": 0,
        "verified_checkout_prices": 0,
        "certified_positive_ev_bets": 0,
        "certified_joint_parlay_win_probability": None,
        "certified_parlay_expected_value": None,
        "wagers_placed": 0,
        "champion_001_modified": False,
        "decision": "HOLD_NO_AUTHENTICATED_NATIVE_PROBABILITY_AND_CHECKOUT",
        "source_notice": "Only pregame SharpAPI paired references captured in the last ten minutes; not executable prices, roster verification or certified model EV. Never recycle prior HOLD/PASS/REJECT legs as approved.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticket", required=True)
    p.add_argument("--games", required=True)
    p.add_argument("--props", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    ticket = json.loads(Path(args.ticket).read_text(encoding="utf-8"))
    games = json.loads(Path(args.games).read_text(encoding="utf-8"))
    props = json.loads(Path(args.props).read_text(encoding="utf-8"))
    report = audit_named_ticket(ticket, games, props)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "ticket_legs_audited": report["leg_count"],
        "current_archived_two_sided_references": report["current_qualified_two_sided_reference_count"],
        "same_game_clusters": len(report["same_event_groups"]),
        "certified_bets": report["certified_positive_ev_bets"],
        "decision": report["decision"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
