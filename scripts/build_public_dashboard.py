"""Publish a minimal, public and fail-closed Freddy's Picks AI dashboard snapshot.

Reads only completed local GitHub Actions artifacts, never provider secrets.
This script NEVER acquires odds, executes a bet or changes Champion-001.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
LEAGUES = ("nba", "nfl", "nhl", "mlb", "ncaaf", "ncaab", "mls", "uefa_champions_league")
MAX_BYTES = 8_000_000
MAX_GAMES = 100
GITHUB = "https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data"


def read_report(path):
    if not path:
        return None
    p = Path(path)
    if not p.is_file() or p.stat().st_size > MAX_BYTES:
        return None
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if obj.tzinfo is None:
        return None
    return obj.astimezone(timezone.utc)


def source_age_minutes(value, now):
    """Age at publication from an aware source timestamp; unavailable is None."""
    when = timestamp(value)
    return round((now - when).total_seconds() / 60, 1) if when else None


def is_fresh_source(age, limit_minutes):
    # Small future skew is tolerated; impossible future timestamps fail closed.
    return age is not None and -1 <= age <= limit_minutes


def clean(value, n=96):
    if not isinstance(value, str):
        return ""
    return "".join(c for c in value if c.isprintable()).strip()[:n]


def number(value, low=0, high=1_000_000):
    if type(value) not in (int, float) or not low <= value <= high:
        return None
    return value


def probability(value):
    p = number(value, 0, 100)
    return round(p, 1) if p is not None else None


def safe_url(run_id):
    return f"{GITHUB}/actions/runs/{run_id}" if type(run_id) is int and run_id > 0 else None


def safe_model(report):
    if (not isinstance(report, dict) or
            report.get("champion_001_modified") is not False or
            report.get("certified_positive_ev_bets") != 0):
        return None
    return report



def build_sport_slates(schedule, *, at, date_et, models=(), live_games=()):
    """Source-dated ESPN game listings for ALL eight leagues, never betting odds.

    Missing or stale schedule artifacts are UNKNOWN, not an invented zero-game slate.
    Schedule data are third-party ESPN observations, not league-certified fixtures.
    """
    base = {lg: {"status": "NO_FRESH_SCHEDULE", "game_count": None,
                 "games": [], "as_of_utc": None, "source": "ESPN scoreboard research"}
            for lg in LEAGUES}
    if (not isinstance(schedule, dict)
            or schedule.get("date_et") != date_et
            or not isinstance(schedule.get("events"), list)
            or len(schedule["events"]) > 600
            or not isinstance(schedule.get("sources"), dict)):
        return base
    at_utc = schedule.get("collected_at_utc")
    if not is_fresh_source(source_age_minutes(at_utc, at), 180):
        return base

    # Only legitimately captured current-day matchups may carry a research lean.
    research_forecasts = {}
    for bundle in models:
        if not bundle or not is_fresh_source(
                source_age_minutes(bundle.get("checked_at_utc"), at), 180):
            continue
        rows = bundle.get("research_only_pregame_predictions") or []
        if not isinstance(rows, list) or len(rows) > 10_000:
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("league") not in LEAGUES:
                continue
            if (row.get("confidence_is_uncalibrated_rule_output") is not True
                    or row.get("native_Champion_001_model_probability") is not None
                    or row.get("verified_live_sportsbook_quote") is not False):
                continue
            key = (row.get("league"), row.get("espn_event_id"))
            p = number(row.get("home_win_research_rule_probability"), 0, 1)
            published = timestamp(row.get("original_forecast_recorded_utc"))
            start = timestamp(row.get("start_utc"))
            if (key not in research_forecasts and p is not None and 0 < p < 1
                    and published is not None and start is not None
                    and published < start and published <= at):
                research_forecasts[key] = (p, start)

    nba_live = {str(row.get("id")): row for row in live_games
                if isinstance(row, dict)}

    for lg in LEAGUES:
        src = schedule["sources"].get(lg)
        if (not isinstance(src, dict) or src.get("status") != "retrieved"
                or src.get("first_day_status") != "retrieved"):
            continue
        checks = src.get("lookahead")
        if not isinstance(checks, list) or not checks or not isinstance(checks[0], dict):
            continue
        check = checks[0]
        expected_hash = check.get("original_source_sha256")
        if (check.get("date_et") != date_et
                or not isinstance(expected_hash, str)
                or len(expected_hash) != 64
                or not all(c in "0123456789abcdef" for c in expected_hash)):
            continue
        source_rows = []
        seen = set()
        for item in schedule["events"]:
            if not isinstance(item, dict) or item.get("league") != lg:
                continue
            if (item.get("requested_date_et") != date_et
                    or item.get("source_original_sha256") != expected_hash
                    or item.get("status") != "scheduled"):
                continue
            game_id = clean(item.get("provider_game_id"), 30)
            away = clean(item.get("away_team"), 65)
            home = clean(item.get("home_team"), 65)
            start = timestamp(item.get("start_utc"))
            observed = timestamp(item.get("observed_at_utc"))
            if (not game_id.isdigit() or game_id in seen
                    or not away or not home or start is None or observed is None
                    or start.astimezone(NY).date().isoformat() != date_et
                    or not is_fresh_source(source_age_minutes(observed.isoformat(), at), 180)):
                continue
            seen.add(game_id)
            research_p = None
            forecast = research_forecasts.get((lg, game_id))
            if forecast and forecast[1] == start:
                research_p = round(forecast[0] * 100, 1)
            elif lg == "nba":
                observed_game = nba_live.get(game_id)
                if observed_game and observed_game.get("away") == away and observed_game.get("home") == home:
                    research_p = probability(observed_game.get("pregame_home_probability_pct"))
            source_rows.append({
                "id": game_id, "away": away, "home": home,
                "start_et": start.astimezone(NY).isoformat(),
                "status": "scheduled", "research_home_probability_pct": research_p,
                "research_probability_type": (
                    "UNCALIBRATED_PREGAME_RULE_NOT_CHAMPION_001"
                    if research_p is not None else "NOT_AVAILABLE"),
                "source_observed_at_utc": observed.isoformat(),
                "verified_sportsbook_odds": False,
                "certified_ev": None,
            })
        listed = number(check.get("raw_events_listed"), 0, 1000)
        # If original source listed games but no identity-qualified events,
        # never claim a zero-game day.
        if not source_rows and listed != 0:
            base[lg]["status"] = "MATCHUPS_UNVERIFIED"
            base[lg]["as_of_utc"] = at_utc
            continue
        source_rows.sort(key=lambda r: (r["start_et"], r["id"]))
        base[lg] = {
            "status": "ESPN_SCHEDULE_OBSERVED" if source_rows else "NO_GAMES_LISTED",
            "game_count": len(source_rows),
            "games": source_rows,
            "as_of_utc": at_utc,
            "source": "ESPN scoreboard research · not official league confirmation",
        }
    return base


def build_markets_by_league(*, models, now):
    """Per-sport quote gates. No NBA price data may leak into other sports."""
    result = {}
    for lg in LEAGUES:
        bundle = next((b for b in models if b and isinstance(
            (b.get("by_league") or {}).get(lg), dict)), None)
        sharp = ((bundle or {}).get("sharp_edge_research") or {}
                 ).get("per_sport_market_evidence") or {}
        evidence = sharp.get(lg) or {}
        q = (((bundle or {}).get("source_quote_freshness") or {}
              ).get("by_league") or {}).get(lg) or {}
        model_age = source_age_minutes((bundle or {}).get("checked_at_utc"), now)
        quote_date = clean(q.get("latest_valid_source_received_utc"), 48) or None
        quote_age = source_age_minutes(quote_date, now)
        if not is_fresh_source(model_age, 180):
            state = "STALE_OR_MISSING_MODEL_REPORT"
        elif not is_fresh_source(quote_age, 120):
            state = "STALE_OR_MISSING_PRICE_RECEIPT"
        else:
            state = "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT"
        current = state == "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT"
        result[lg] = {
            "archived_quotes": number(evidence.get("archived_provider_quote_rows"), 0, 500000),
            "paired_game_markets": (
                number(evidence.get("fresh_paired_game_boards"), 0, 50000) if current else None),
            "paired_prop_markets": (
                number(evidence.get("fresh_paired_player_prop_markets"), 0, 50000) if current else None),
            "odds_receipt_utc": quote_date,
            "odds_age_minutes_at_publication": quote_age,
            "model_age_minutes_at_publication": model_age,
            "price_evidence_state": state,
            "paired_market_reference_current": current,
            "market_blocker": clean(evidence.get("primary_source_blocker"), 80) or "NO_VERIFIED_MARKETS",
            "verified_checkout_prices": 0, "certified_positive_ev": 0,
            "verified_clv": None,
        }
    return result




def build_hourly_public_board(public, *, at, date_et):
    """Fail-closed read-only ESPN source observations across all eight sports.

    Capture time is a retrieval time, NOT the line's original posted time.
    Third-party book labels NEVER qualify as a book checkout or model edge.
    """
    states = {league: {
        "status": "NO_CURRENT_ESPN_SCOREBOARD", "observed_at_utc": None,
        "game_count": None, "line_reference_count": None, "games": [],
        "source": "ESPN scoreboard, source reference only"
    } for league in LEAGUES}
    if (not isinstance(public, dict)
            or public.get("schema") != "freddys-espn-public-hourly-v1"
            or public.get("date_et") != date_et
            or public.get("champion_001_modified") is not False
            or public.get("certified_positive_ev") != 0
            or public.get("provider_checkout_ever_verified") is not False
            or not isinstance(public.get("leagues"), dict)):
        return states
    for league in LEAGUES:
        s = public["leagues"].get(league) or {}
        t = clean(s.get("observed_at_utc"), 48)
        if (s.get("status") != "ESPN_SCOREBOARD_OBSERVED"
                or not is_fresh_source(source_age_minutes(t, at), 100)
                or not isinstance(s.get("games"), list)
                or len(s["games"]) > 120):
            continue
        rows, ids = [], set()
        invalid = False
        for entry in s["games"]:
            if not isinstance(entry, dict):
                invalid = True
                break
            gid = clean(entry.get("id"), 30)
            home = clean(entry.get("home"), 90)
            away = clean(entry.get("away"), 90)
            start = timestamp(entry.get("start_et"))
            state = entry.get("status")
            if (not gid.isdigit() or gid in ids or not home or not away
                    or home == away or start is None or
                    start.astimezone(NY).date().isoformat() != date_et
                    or state not in ("pre", "in", "post")):
                invalid = True
                break
            ids.add(gid)
            m = entry.get("market_reference")
            quote = None
            if isinstance(m, dict) and m.get("direct_checkout_verified") is False and \
                    m.get("market_reference_only") is True and \
                    m.get("bookmaker_quote_timestamp_utc") is None:
                provider = clean(m.get("provider_name"), 64)
                if provider:
                    quote = {
                        "provider": provider,
                        "moneyline_away": m.get("away_moneyline") if
                            type(m.get("away_moneyline")) is int else None,
                        "moneyline_home": m.get("home_moneyline") if
                            type(m.get("home_moneyline")) is int else None,
                        "spread_details": clean(m.get("spread_details"), 55) or None,
                        "total": number(m.get("total"), 0.5, 999.5),
                        "over_price": m.get("over_price") if
                            type(m.get("over_price")) is int else None,
                        "under_price": m.get("under_price") if
                            type(m.get("under_price")) is int else None,
                        "home_spread_price": m.get("home_spread_price") if
                            type(m.get("home_spread_price")) is int else None,
                        "away_spread_price": m.get("away_spread_price") if
                            type(m.get("away_spread_price")) is int else None,
                        "source_observed_at_utc": t,
                        "bookmaker_quote_timestamp_utc": None,
                        "direct_checkout_verified": False,
                        "bet_ready": False,
                        "evidence_class": "PUBLIC_ESPN_BOOK_LABEL_ONLY",
                    }
                    if league in ("mls", "uefa_champions_league"):
                        # No fake two-way settlement for 90-minute 3-way soccer.
                        quote["moneyline_away"] = quote["moneyline_home"] = None
            rows.append({
                "id": gid, "home": home, "away": away,
                "start_et": start.astimezone(NY).isoformat(),
                "status": state,
                "home_score": number(entry.get("home_score"), 0, 300)
                    if state in ("in", "post") else None,
                "away_score": number(entry.get("away_score"), 0, 300)
                    if state in ("in", "post") else None,
                "period": number(entry.get("period"), 0, 25),
                "clock": clean(entry.get("clock"), 18) if state == "in" else "",
                "market_reference": quote,
            })
        if invalid:
            continue
        rows.sort(key=lambda x: (x["start_et"], x["id"]))
        states[league] = {
            "status": "ESPN_PUBLIC_OBSERVED" if rows else "NO_GAMES_LISTED",
            "observed_at_utc": t, "game_count": len(rows),
            "line_reference_count": sum(g["market_reference"] is not None for g in rows),
            "games": rows,
            "source": "ESPN public scoreboard; provider label only, no checkout",
        }
    return states


def build(*, live=None, model=None, all_sports=None, schedule=None, public=None, live_run=None, schedule_run=None,
          model_run=None, all_run=None, at=None):
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_utc_clock_required")
    now = now.astimezone(timezone.utc)
    model = safe_model(model)
    all_sports = safe_model(all_sports)
    date_et = now.astimezone(NY).date().isoformat()

    valid_live = (
        isinstance(live, dict)
        and live.get("champion_001_modified") is False
        and live.get("certified_positive_ev_bets") == 0
        and live.get("wagers_placed") == 0
        and live.get("source_status") == "ESPN_SCOREBOARD_OBSERVED"
        and isinstance(live.get("games"), list)
        and len(live["games"]) <= MAX_GAMES
    )
    received = timestamp(live.get("observed_at_utc")) if valid_live else None
    today = valid_live and live.get("date_et") == date_et
    age = round((now - received).total_seconds()/60, 1) if received else None
    # A delayed or future-dated result is not advertised as a live score.
    valid_live = bool(today and received and -1 <= age <= 180)
    games = []
    if valid_live:
        for row in live["games"]:
            if not isinstance(row, dict):
                continue
            status = row.get("source_event_state")
            if status not in ("pre", "in", "post"):
                status = "unknown"
            game_id = clean(row.get("espn_event_id"), 30)
            away = clean(row.get("away_team"), 65)
            home = clean(row.get("home_team"), 65)
            if not game_id.isdigit() or not (away and home):
                continue
            pb = probability(row.get("pregame_rule_home_win_percent"))
            # Source itself verifies exact event, team, and pre-tipoff capture.
            # If unavailable, do not backfill with a market-implied percentage.
            if live.get("pregame_rule_context_status") != "EXACT_MATCHED_UNCALIBRATED_PREGAME_RESEARCH_ONLY":
                pb = None
            pace_home = number(row.get("pace_extrapolated_final_home_points"),0,200)
            pace_away = number(row.get("pace_extrapolated_final_away_points"),0,200)
            pace_total = number(row.get("pace_extrapolated_final_total_points"),0,350)
            if status != "in" or row.get("projection_status") != "IN_GAME_UNCALIBRATED_PACE_ESTIMATE":
                pace_home = pace_away = pace_total = None
            games.append({
                "id": game_id,
                "away": away, "home": home,
                "start_et": clean(row.get("scheduled_start_et"), 48),
                "status": status,
                "away_score": number(row.get("score_away"),0,300) if status in ("in","post") else None,
                "home_score": number(row.get("score_home"),0,300) if status in ("in","post") else None,
                "period": number(row.get("period"),0,10) if status in ("in","post") else None,
                "clock": clean(row.get("clock"),12) if status == "in" else "",
                "pregame_home_probability_pct": pb,
                "pregame_home_probability_time_utc": clean(row.get("pregame_rule_probability_source_time_utc"),48)
                    if pb is not None else "",
                "pace_home": pace_home, "pace_away": pace_away, "pace_total": pace_total,
                "pace_status": clean(row.get("projection_status"),64),
            })
    games.sort(key=lambda x:(x["start_et"],x["id"]))

    reference_model = model or all_sports or {}
    references = []
    for bundle in (model, all_sports):
        if not bundle:
            continue
        references.append(bundle)
    sports = {}
    for sport in LEAGUES:
        info = None
        for bundle in references:
            row = (bundle.get("by_league") or {}).get(sport)
            if isinstance(row, dict):
                info = row
                break
        if not info:
            sports[sport] = {"status": "No synced research report", "forecasts": None,
                             "research_freshness": "NO_SYNCED_REPORT", "age_minutes": None}
        else:
            source_age = source_age_minutes(bundle.get("checked_at_utc"), now)
            sports[sport] = {
                "status": clean(info.get("execution_status"),50) or "Unverified",
                "research_freshness": (
                    "RECENT_RESEARCH" if is_fresh_source(source_age, 180)
                    else "STALE_RESEARCH" if source_age is not None
                    else "UNKNOWN_RESEARCH_TIME"),
                "age_minutes": source_age,
                "forecasts": number(info.get("uncalibrated_pregame_forecast_rows"),0,10000),
                "team_last5": number(info.get("complete_team_last5"),0,100000),
                "team_last10": number(info.get("complete_team_last10"),0,100000),
                "player_last5": number(info.get("complete_player_last5"),0,100000),
                "player_last10": number(info.get("complete_player_last10"),0,100000),
                "as_of_utc": clean(bundle.get("checked_at_utc"),48),
            }
    sharp = (reference_model.get("sharp_edge_research") or {})
    nba_market = (sharp.get("per_sport_market_evidence") or {}).get("nba") or {}
    quotes = (reference_model.get("source_quote_freshness") or {}).get("by_league") or {}
    q_nba = quotes.get("nba") or {}
    calibration = (reference_model.get("recalibration_and_oos_readiness") or {})
    # Model output fields are optional across V8 revisions: never guess.
    metrics = {
        "archived_quotes": number(nba_market.get("archived_provider_quote_rows"),0,500000),
        "paired_game_markets": number(nba_market.get("fresh_paired_game_boards"),0,50000),
        "paired_prop_markets": number(nba_market.get("fresh_paired_player_prop_markets"),0,50000),
        "recent_raw_quotes": number(q_nba.get("today_upcoming_quote_rows_within_120m"),0,500000),
        "odds_receipt_utc": clean(q_nba.get("latest_valid_source_received_utc"),48) or None,
        "odds_age_minutes_at_model_run": number(q_nba.get("latest_valid_archive_receipt_age_minutes"),0,100000),
        "market_blocker": clean(nba_market.get("primary_source_blocker"),80) or "Not verified",
        "verified_checkout_prices": 0,
        "certified_positive_ev": 0,
        "verified_clv": None,
    }
    if valid_live:
        live_quote = clean(live.get("latest_archived_nba_quote_utc"),48)
        if live_quote:
            metrics["odds_receipt_utc"] = live_quote
        recent = number(live.get("today_unstarted_nba_price_rows_within_120m"),0,500000)
        if recent is not None:
            metrics["recent_raw_quotes"] = recent
    # A green workflow or archived quote count cannot imply that its markets
    # are fresh today. Preserve historical counts, but suppress stale paired
    # market counts from current-coverage widgets (N/A, not fabricated zero).
    model_age = source_age_minutes(reference_model.get("checked_at_utc"), now)
    quote_age = source_age_minutes(metrics["odds_receipt_utc"], now)
    if not is_fresh_source(model_age, 180):
        evidence_state = "STALE_OR_MISSING_MODEL_REPORT"
    elif not is_fresh_source(quote_age, 120):
        evidence_state = "STALE_OR_MISSING_PRICE_RECEIPT"
    else:
        evidence_state = "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT"
    metrics["price_evidence_state"] = evidence_state
    metrics["paired_market_reference_current"] = evidence_state == "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT"
    metrics["model_age_minutes_at_publication"] = model_age
    metrics["odds_age_minutes_at_publication"] = quote_age
    if not metrics["paired_market_reference_current"]:
        metrics["paired_game_markets"] = None
        metrics["paired_prop_markets"] = None
        metrics["recent_raw_quotes"] = None
    health = {
        "champion_frozen": True,
        "calibration_status": clean(calibration.get("status") or calibration.get("persisted_nba_original_forward_calibration_status"),90) or "Not independently certified",
        "graded_forecasts": None,
        "forward_forecasts": None,
        "betting_state": "HOLD",
        "research_only": True,
    }
    if isinstance(calibration, dict):
        health["graded_forecasts"] = number(calibration.get("nba_original_graded_outcomes"),0,500000)
        health["forward_forecasts"] = number(calibration.get("nba_original_archived_forecasts"),0,500000)
    slates = build_sport_slates(schedule, at=now, date_et=date_et,
                               models=references, live_games=games)
    per_league_market = build_markets_by_league(models=references, now=now)
    # Preserve the historic NBA top-level keys for older web clients;
    # per-league fields are the canonical all-eight-sport view.
    if per_league_market.get("nba"):
        per_league_market["nba"] = {
            **per_league_market["nba"],
            **{key: metrics[key] for key in (
                "archived_quotes", "paired_game_markets", "paired_prop_markets",
                "odds_receipt_utc", "odds_age_minutes_at_publication",
                "model_age_minutes_at_publication", "price_evidence_state",
                "paired_market_reference_current", "market_blocker",
                "certified_positive_ev", "verified_checkout_prices", "verified_clv")}}
    public_board = build_hourly_public_board(public, at=now, date_et=date_et)
    # Publish only data from vetted reports; never raw API payloads or secrets.
    return {
        "schema": "freddys-picks-ai-public-v1",
        "generated_at_utc": now.isoformat(),
        "reference_date_eastern": date_et,
        "live_source_status": "SOURCE_OBSERVED" if valid_live else "AWAITING_FRESH_PUBLIC_SCOREBOARD",
        "live_observed_at_utc": received.isoformat() if valid_live else None,
        "live_age_minutes_at_publication": age if valid_live else None,
        "live_scoreboard_not_continuous": True,
        "games": games, "leagues": sports,
        "slates": slates, "market_by_league": per_league_market,
        "public_hourly_board": public_board,
        "market": metrics, "model": health,
        "sources": {
            "github": GITHUB,
            "run_nba": safe_url(model_run),
            "run_all": safe_url(all_run),
            "live": safe_url(live_run),
            "schedule": safe_url(schedule_run),
        },
        "disclaimer": "Public research observations. No authenticated DraftKings checkout, independently calibrated live model, or certified positive-EV bets.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-report")
    parser.add_argument("--model-report")
    parser.add_argument("--all-sports-report")
    parser.add_argument("--schedule-report")
    parser.add_argument("--public-report")
    parser.add_argument("--schedule-run", type=int)
    parser.add_argument("--live-run", type=int)
    parser.add_argument("--model-run", type=int)
    parser.add_argument("--all-run", type=int)
    parser.add_argument("--out", default="docs/data/dashboard.json")
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build(
        live=read_report(args.live_report),
        model=read_report(args.model_report),
        all_sports=read_report(args.all_sports_report),
        schedule=read_report(args.schedule_report),
        public=read_report(args.public_report),
        live_run=args.live_run, schedule_run=args.schedule_run,
        model_run=args.model_run,
        all_run=args.all_run,
    )
    output.write_text(json.dumps(snapshot,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"scoreboard":snapshot["live_source_status"],
                      "games":len(snapshot["games"]),
                      "paired_game_markets":snapshot["market"]["paired_game_markets"],
                      "certified_ev":snapshot["market"]["certified_positive_ev"],
                      "published":str(output)},sort_keys=True))


if __name__ == "__main__":
    main()
