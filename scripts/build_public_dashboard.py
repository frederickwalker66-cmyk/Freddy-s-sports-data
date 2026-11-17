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


def recent(age, limit_minutes):
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


def build(*, live=None, model=None, all_sports=None, live_run=None,
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
                    "RECENT_RESEARCH" if recent(source_age, 180)
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
    if not recent(model_age, 180):
        evidence_state = "STALE_OR_MISSING_MODEL_REPORT"
    elif not recent(quote_age, 120):
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
        "market": metrics, "model": health,
        "sources": {
            "github": GITHUB,
            "run_nba": safe_url(model_run),
            "run_all": safe_url(all_run),
            "live": safe_url(live_run),
        },
        "disclaimer": "Public research observations. No authenticated DraftKings checkout, independently calibrated live model, or certified positive-EV bets.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-report")
    parser.add_argument("--model-report")
    parser.add_argument("--all-sports-report")
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
        live_run=args.live_run,
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
