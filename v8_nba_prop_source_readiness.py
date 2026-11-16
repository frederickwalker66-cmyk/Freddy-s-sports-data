"""NBA player-prop source readiness: precise, zero-provider-call evidence gaps.

This is not an odds collector, betting model, forecast, or verified sportsbook
checkout. It reviews original saved SharpAPI research rows and the currently
configured *nominal* UTC collector schedule. GitHub cron may run late.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from v8_sharp_player_props import inspect_player_prop, summarize_player_props
from v8_sharp_archive import MAX_RESEARCH_WATCHLIST_AGE_MINUTES

NY = ZoneInfo("America/New_York")
# Keep synchronized with collect-sharpapi.yml; this is NOT an authorization
# to add provider calls or change an existing daily API budget.
SHARPAPI_NOMINAL_UTC_HOURS = (16, 20, 23)
MAX_ROWS = 150_000


def _next_nominal_utc(clock, hours):
    for day_offset in range(2):
        day = (clock + timedelta(days=day_offset)).date()
        for hour in hours:
            candidate = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
            if candidate > clock:
                return candidate.isoformat()
    raise ValueError("invalid_collector_schedule")


def inspect_nba_prop_capture(rows, *, now=None, archive_run_ids=()):
    """Audit only original source rows; never produce a model p or approve bets."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("bounded_original_quotes_required")
    if not isinstance(archive_run_ids, (tuple, list)) or any(
            type(x) is not int or x <= 0 for x in archive_run_ids):
        raise ValueError("original_archive_run_ids_required")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_capture_clock_required")
    clock = clock.astimezone(timezone.utc)
    today = clock.astimezone(NY).date()
    nba_rows = [r for r in rows if isinstance(r, dict)
                and r.get("league") == "nba" and r.get("is_player_prop") is True]
    summary, _ = summarize_player_props(nba_rows, now=clock,
                                        archive_run_ids=archive_run_ids)
    valid, rejected = [], Counter()
    for row in nba_rows:
        quote, reason = inspect_player_prop(row)
        if reason:
            rejected[reason] += 1
        elif quote["received"] > clock or quote["quote"] > clock:
            rejected["future_archive_observation"] += 1
        else:
            valid.append(quote)
    latest = max((q["received"] for q in valid), default=None)
    upcoming = [q for q in valid if q["start"] > clock and
                q["start"].astimezone(NY).date() == today]
    recent = [q for q in upcoming if
              0 <= (clock - q["received"]).total_seconds() / 60
              <= MAX_RESEARCH_WATCHLIST_AGE_MINUTES]
    fresh_pairs = summary["today_recent_two_sided_prop_markets"]
    if not nba_rows:
        blocker = "NO_ARCHIVED_NBA_PLAYER_PROP_SOURCE_ROWS"
    elif not valid:
        blocker = "NO_VALID_EXACT_NBA_PLAYER_IDENTITY_AND_QUOTES"
    elif not upcoming:
        blocker = "NO_QUOTES_FOR_TODAYS_UNSTARTED_NBA_PROPS"
    elif not recent:
        blocker = "TODAYS_NBA_PROP_QUOTES_STALE"
    elif not fresh_pairs:
        blocker = "NO_FRESH_TWO_SIDED_SAME_LINE_NBA_PROP_MARKETS"
    else:
        blocker = "RESEARCH_PRICES_ONLY_MISSING_INDEPENDENT_MODEL_ROSTER_AND_CHECKOUT"
    return {
        "report_type": "NBA_PLAYER_PROP_SOURCE_READINESS_RESEARCH_ONLY",
        "as_of_utc": clock.isoformat(),
        "nba_prop_archived_source_rows": len(nba_rows),
        "valid_exact_nba_player_prop_rows": len(valid),
        "rejected_original_prop_rows_by_reason": dict(sorted(rejected.items())),
        "source_player_identity_by_provider_name_only_rows":
            summary["valid_provider_name_only_quote_observations_research_only"],
        "historical_two_sided_exact_line_snapshots":
            summary["two_sided_same_line_snapshots"],
        "today_unstarted_game_valid_prop_rows": len(upcoming),
        "today_unstarted_game_recent_prop_rows": len(recent),
        "today_unstarted_game_stale_prop_rows": len(upcoming) - len(recent),
        "today_fresh_two_sided_exact_line_research_markets": fresh_pairs,
        "latest_valid_original_archive_capture_utc":
            latest.isoformat() if latest else None,
        "minutes_since_latest_valid_capture":
            round((clock - latest).total_seconds() / 60, 1) if latest else None,
        "maximum_research_quote_age_minutes": MAX_RESEARCH_WATCHLIST_AGE_MINUTES,
        "sharpapi_collector_nominal_utc_hours": list(SHARPAPI_NOMINAL_UTC_HOURS),
        "next_nominal_scheduled_collector_utc":
            _next_nominal_utc(clock, SHARPAPI_NOMINAL_UTC_HOURS),
        "schedule_does_not_guarantee_execution_or_provider_data": True,
        "provider_calls_made_by_this_report": 0,
        "archive_run_ids": list(archive_run_ids),
        "primary_source_blocker": blocker,
        "independently_verified_native_champion_player_prop_probability": False,
        "independently_verified_challenger_out_of_sample_prop_calibration": False,
        "independently_confirmed_player_active": False,
        "direct_draftkings_checkout_price_verified": False,
        "verified_professional_sharp_flow": False,
        "eligible_for_ev_certification": False,
        "certified_positive_ev_bets": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "next_action": (
            "Check the next scheduled collector result and its exact original "
            "NBA prop receipts; review player ID, both same-line sides, and "
            "quote freshness. A new provider call or added schedule may incur "
            "charges and requires explicit approval. Recover authenticated "
            "native pregame forecast/version and independently settled "
            "holdout data before fitting calibration or claiming value."
        ),
    }


def render_nba_prop_capture(report):
    """Readable gap report; percentages and bet selections are intentionally absent."""
    keys = (
        ("Archived NBA prop rows", "nba_prop_archived_source_rows"),
        ("Valid original NBA prop rows", "valid_exact_nba_player_prop_rows"),
        ("Historical exact-line pairs", "historical_two_sided_exact_line_snapshots"),
        ("Today's future-game valid rows", "today_unstarted_game_valid_prop_rows"),
        ("Today's recent rows", "today_unstarted_game_recent_prop_rows"),
        ("Today's exact-line recent pairs", "today_fresh_two_sided_exact_line_research_markets"),
        ("Latest valid archived quote (UTC)", "latest_valid_original_archive_capture_utc"),
        ("Age in minutes", "minutes_since_latest_valid_capture"),
        ("Next nominal SharpAPI collection (UTC)", "next_nominal_scheduled_collector_utc"),
    )
    lines = ["# NBA Player-Prop Source Readiness", "",
             "**Research only — no verified bet or model-derived EV.**", "",
             f"**Primary blocker:** {report['primary_source_blocker']}", ""]
    for label, key in keys:
        val = report[key]
        lines.append(f"- **{label}:** {val if val is not None else 'N/A'}")
    lines.extend(["", "## Exact reasons for rejected raw player props"])
    for reason, count in report["rejected_original_prop_rows_by_reason"].items():
        lines.append(f"- {reason}: {count}")
    lines.extend(["", "## Next action", report["next_action"], "",
                  "Nominal collector scheduling does not prove a provider run, "
                  "a current checkout price, a confirmed active player, "
                  "a native model probability or a positive EV. All remain HOLD.", ""])
    return "\n".join(lines)
