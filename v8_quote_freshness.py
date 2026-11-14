"""Why archived research odds are/are not current for an exact upcoming market.

Read-only, original-receipt observability. Nothing here upgrades an aggregator
price to a sportsbook checkout quote, validates a player, or proves model EV.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from historical_outcomes import parse_time
from v8_sharp_archive import MAX_RESEARCH_WATCHLIST_AGE_MINUTES

NY = ZoneInfo("America/New_York")
MAX_ARCHIVED_QUOTE_ROWS = 150000


def quote_freshness(rows, *, leagues, now=None, fresh_paired_by_league=None,
                    archive_run_ids=()):
    if not isinstance(rows, list) or len(rows) > MAX_ARCHIVED_QUOTE_ROWS:
        raise ValueError("bounded_original_archive_rows_required")
    if (not isinstance(leagues, (tuple,list)) or not leagues
            or len(set(leagues)) != len(leagues)
            or any(not isinstance(x,str) or not x for x in leagues)):
        raise ValueError("explicit_leagues_required")
    if (not isinstance(archive_run_ids,(tuple,list))
            or any(type(x) is not int or x<=0 for x in archive_run_ids)):
        raise ValueError("original_archive_run_ids_required")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock,datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_market_freshness_clock_required")
    clock = clock.astimezone(timezone.utc)
    paired = fresh_paired_by_league or {}
    if not isinstance(paired,dict) or any(
            name not in leagues or type(count) is not int or count < 0
            for name,count in paired.items()):
        raise ValueError("invalid_paired_market_evidence")
    today = clock.astimezone(NY).date()
    result = {}
    for lg in leagues:
        records = Counter()
        last_capture = None
        last_quote = None
        latest_upcoming_today = None
        for row in rows:
            if not isinstance(row,dict) or row.get("league") != lg:
                continue
            records["archived_source_rows_for_league"] += 1
            if (row.get("source") != "sharpapi_rest"
                    or row.get("sportsbook") != "draftkings"
                    or row.get("record_type") != "pregame_odds_observation"
                    or row.get("certified_prediction") is not False
                    or row.get("model_probability") is not None):
                records["untrusted_source_identity_or_certification_flags"] += 1
                continue
            try:
                received = parse_time(row.get("recorded_at"))
                quote = parse_time(row.get("timestamp"))
                start = parse_time(row.get("event_start_time"))
            except (ValueError,TypeError,KeyError,OverflowError):
                records["malformed_source_timestamp"] += 1
                continue
            if (not quote <= received < start
                    or received > clock or quote > clock):
                records["future_or_inplay_or_inconsistent_source_receipt"] += 1
                continue
            records["authentic_format_pregame_archive_rows"] += 1
            last_capture = max(last_capture,received) if last_capture else received
            last_quote = max(last_quote,quote) if last_quote else quote
            if start <= clock:
                records["already_started_game_quote_rows"] += 1
                continue
            records["still_upcoming_quote_rows"] += 1
            if start.astimezone(NY).date() != today:
                records["upcoming_other_date_quote_rows"] += 1
                continue
            records["today_upcoming_original_quote_rows"] += 1
            age = (clock-received).total_seconds()/60
            latest_upcoming_today = (max(latest_upcoming_today,received)
                                     if latest_upcoming_today else received)
            if age <= MAX_RESEARCH_WATCHLIST_AGE_MINUTES:
                records["today_upcoming_within_120m_quote_rows"] += 1
            else:
                records["today_upcoming_older_than_120m_quote_rows"] += 1
        count = paired.get(lg,0)
        if records["archived_source_rows_for_league"] == 0:
            stage = "NO_ARCHIVED_PROVIDER_QUOTES"
        elif last_capture is None:
            stage = "NO_VALID_PREGAME_SOURCE_RECEIPTS"
        elif records["today_upcoming_original_quote_rows"] == 0:
            stage = "NO_ARCHIVED_QUOTES_FOR_TODAYS_UNSTARTED_EVENTS"
        elif records["today_upcoming_within_120m_quote_rows"] == 0:
            stage = "TODAYS_UPCOMING_SOURCE_QUOTES_STALE"
        elif count == 0:
            stage = "RECENT_RAW_QUOTES_BUT_NO_EXACT_PAIRED_MARKETS"
        else:
            stage = "RECENT_EXACT_PAIRED_RESEARCH_MARKETS_NOT_CHECKOUT"
        result[lg] = {
            "league": lg,
            "source_readiness": stage,
            "archived_source_rows_for_league": records["archived_source_rows_for_league"],
            "valid_pregame_original_receipt_rows": records[
                "authentic_format_pregame_archive_rows"],
            "rejected_rows_by_reason": {
                x:records[x] for x in (
                    "untrusted_source_identity_or_certification_flags",
                    "malformed_source_timestamp",
                    "future_or_inplay_or_inconsistent_source_receipt")
                if records[x]
            },
            "latest_valid_source_received_utc": (
                last_capture.isoformat() if last_capture else None),
            "latest_valid_provider_quote_utc": (
                last_quote.isoformat() if last_quote else None),
            "latest_valid_archive_receipt_age_minutes": (
                round((clock-last_capture).total_seconds()/60,1)
                if last_capture else None),
            "today_upcoming_quote_rows_in_archive": records[
                "today_upcoming_original_quote_rows"],
            "today_upcoming_quote_rows_within_120m": records[
                "today_upcoming_within_120m_quote_rows"],
            "today_upcoming_quote_rows_older_than_120m": records[
                "today_upcoming_older_than_120m_quote_rows"],
            "upcoming_other_date_quote_rows": records[
                "upcoming_other_date_quote_rows"],
            "historical_started_quote_rows": records[
                "already_started_game_quote_rows"],
            "latest_today_upcoming_source_received_utc": (
                latest_upcoming_today.isoformat() if latest_upcoming_today else None),
            "fresh_exact_paired_market_groups": count,
            "does_not_establish_live_executable_draftkings_prices": True,
            "independent_model_probability_available": False,
            "certified_positive_ev_bets": 0,
            "decision": "HOLD_NO_CERTIFIED_EDGE",
        }
    return {
        "report_type": "v8_archived_pregame_source_freshness_research_v1",
        "checked_at_utc": clock.isoformat(),
        "reference_date_eastern": today.isoformat(),
        "research_freshness_max_age_minutes": MAX_RESEARCH_WATCHLIST_AGE_MINUTES,
        "archive_run_ids": list(archive_run_ids),
        "by_league": result,
        "provider_collection_network_calls": 0,
        "does_not_dispatch_paid_collector": True,
        "sharp_flow_authenticated": False,
        "bookmaker_checkout_authenticated": False,
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "warning": (
            "Age and original receipt format explain source readiness, not "
            "accuracy, completeness of the bookmaker board, settlement, "
            "player availability, independently generated model probability or EV. "
            "Collector cron is best-effort, not a guarantee of fresh prices."
        ),
    }
