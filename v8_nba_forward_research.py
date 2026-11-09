"""NBA forward research forecasts: actual pre-tipoff recorded probabilities.

Uses verified-shape ESPN historical published scores RECORDED NOW plus original
ESPN schedule HTTP bytes captured NOW. Elo v0 K20/HA60 uses only previously
matured score history under a conservative 48h assumed result delay.
These are ORIGINAL forward-time research records (not retrospective replay),
but NOT independently certified predictions or Champion-001 shadow picks.
No sportsbook implied-probability substitution, paid APIs, or wagers.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from challenger_elo_walkforward import K, HOME_ADV, pregame_probability, validate_game
from historical_outcomes import collect as collect_scores, parse_time
from independent_schedule_review import download_json_original

NY = ZoneInfo("America/New_York")
VERSION = "v8-nba-elo-forward-research-v0-fixed-k20-ha60"
MIN_HISTORY_GAMES = 80
MAX_HISTORY_DAYS = 35
DEFAULT_HISTORY_DAYS = 21
SETTLEMENT_ASSUMPTION_HOURS = 48
MAX_FUTURE_DAYS = 2
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?"


def _iso(d):
    if not isinstance(d, datetime) or d.tzinfo is None:
        raise ValueError("aware_clock_required")
    return d.astimezone(timezone.utc).isoformat()


def _now(clock):
    return parse_time(_iso(clock()))


def _event(event, day, received_at, source_url, raw_hash):
    if (not isinstance(event, dict) or not isinstance(event.get("season"), dict)
            or event["season"].get("type") != 2):
        return None
    state = event.get("status", {})
    if not isinstance(state, dict) or not isinstance(state.get("type"), dict):
        return None
    if state["type"].get("state") != "pre":
        return None
    comp = event.get("competitions")
    if not isinstance(comp, list) or len(comp) != 1 or not isinstance(comp[0], dict):
        return None
    teams = comp[0].get("competitors")
    if not isinstance(teams, list) or len(teams) != 2:
        return None
    identity = {}
    for team in teams:
        if not isinstance(team, dict) or team.get("homeAway") not in ("home", "away"):
            return None
        meta = team.get("team")
        if not isinstance(meta, dict):
            return None
        tid, name = str(meta.get("id") or ""), meta.get("displayName")
        if not tid.isdigit() or not isinstance(name, str) or not name.strip():
            return None
        if team["homeAway"] in identity:
            return None
        identity[team["homeAway"]] = (tid, name.strip())
    if set(identity) != {"home", "away"} or identity["home"][0] == identity["away"][0]:
        return None
    event_id = str(event.get("id") or "")
    if not event_id.isdigit():
        return None
    try:
        start = parse_time(event.get("date") or comp[0].get("date"))
    except (ValueError, TypeError):
        return None
    if (start <= received_at or start.astimezone(NY).date() != day
            or start > received_at + timedelta(days=MAX_FUTURE_DAYS)):
        return None
    return {
        "league": "nba", "espn_event_id": event_id,
        "start_utc": start.isoformat(),
        "home_team_espn_id": identity["home"][0],
        "away_team_espn_id": identity["away"][0],
        "home_team": identity["home"][1], "away_team": identity["away"][1],
        "schedule_original_received_at_utc": received_at.isoformat(),
        "schedule_original_sha256_local_receipt": raw_hash,
        "schedule_source_url": source_url,
    }


def parse_schedule_original(payload, raw, day, received_at, source_url):
    if not isinstance(payload, dict) or not isinstance(raw, bytes):
        raise ValueError("original_schedule_bytes_and_payload_required")
    if not 0 < len(raw) <= 5_000_000 or json.loads(raw) != payload:
        raise ValueError("schedule_original_bytes_not_consistent")
    games = payload.get("events")
    if not isinstance(games, list) or len(games) >= 500:
        raise ValueError("schedule_response_missing_or_truncated")
    h = hashlib.sha256(raw).hexdigest()
    found, keys = [], set()
    for event in games:
        obj = _event(event, day, received_at, source_url, h)
        if obj is None:
            continue
        if obj["espn_event_id"] in keys:
            raise ValueError("duplicated_future_espn_event_id")
        found.append(obj)
        keys.add(obj["espn_event_id"])
    return found


def _ratings(history, asof, min_history=MIN_HISTORY_GAMES):
    if not isinstance(history, list):
        raise ValueError("historical_result_list_required")
    seen, eligible = set(), []
    for row in history:
        league, when, eid, home, away, y = validate_game(row)
        if league != "nba" or y not in (0, 1):
            raise ValueError("invalid_NBA_historical_full_game_result")
        if eid in seen:
            raise ValueError("duplicate_NBA_history_event")
        seen.add(eid)
        captured = parse_time(row.get("retrieved_at_utc"))
        if not when < captured <= asof:
            raise ValueError("historical_source_not_captured_prior_to_forecast")
        if when + timedelta(hours=SETTLEMENT_ASSUMPTION_HOURS) > asof:
            continue
        eligible.append((when, eid, home, away, y))
    eligible.sort(key=lambda z: (z[0], z[1]))
    if len(eligible) < min_history:
        return None, len(eligible)
    rating = defaultdict(lambda: 1500.)
    pending = []
    for when, eid, home, away, y in eligible:
        matured = [x for x in pending if x[0] <= when]
        pending = [x for x in pending if x[0] > when]
        for _, h, a, final, p in matured:
            delta = K * (final - p)
            rating[h] += delta
            rating[a] -= delta
        # Events with exactly equal starts must see the SAME old ratings;
        # their updates are held until >48h later.
        expected = pregame_probability(rating[home], rating[away])
        pending.append((when + timedelta(hours=SETTLEMENT_ASSUMPTION_HOURS),
                        home, away, y, expected))
    for _, h, a, final, p in pending:
        delta = K * (final - p)
        rating[h] += delta
        rating[a] -= delta
    return dict(rating), len(eligible)


def project(history, schedule, coverage, asof):
    """Independent output is a genuine clock-time research forecast, not a bet."""
    when = parse_time(_iso(asof))
    if not isinstance(coverage, dict) or coverage.get("leagues") != ["nba"]:
        raise ValueError("missing_original_NBA_history_source_coverage")
    if coverage.get("champion_001_modified") is not False:
        raise ValueError("original_champion_integrity_not_established")
    source = coverage.get("by_league", {}).get("nba", {})
    days = source.get("days_attempted")
    succeeded = source.get("days_ok")
    failed = source.get("days_failed")
    if (type(days) is not int or not 1 <= days <= MAX_HISTORY_DAYS
            or type(succeeded) is not int or type(failed) is not int
            or succeeded < 0 or failed < 0 or days != succeeded + failed):
        raise ValueError("historical_source_coverage_did_not_reconcile")
    if coverage.get("total_completed_results") != len(history):
        raise ValueError("historical_result_count_disagreement")
    if not isinstance(schedule, list):
        raise ValueError("future_original_schedule_required")
    reasons = Counter()
    rating = None
    qualified_history = 0
    if failed:
        reasons["incomplete_historical_published_result_source_days"] += failed
    else:
        rating, qualified_history = _ratings(history, when)
        if rating is None:
            reasons["insufficient_prior_matured_NBA_games"] += 1
    records, seen = [], set()
    for event in schedule:
        if not isinstance(event, dict) or event.get("league") != "nba":
            raise ValueError("invalid_future_NBA_schedule")
        event_id = event.get("espn_event_id")
        if event_id in seen:
            raise ValueError("duplicate_future_NBA_identity")
        seen.add(event_id)
        start = parse_time(event["start_utc"])
        observed = parse_time(event["schedule_original_received_at_utc"])
        if not observed <= when < start:
            reasons["event_started_before_completed_forecast"] += 1
            continue
        home, away = event["home_team_espn_id"], event["away_team_espn_id"]
        if not isinstance(home, str) or not isinstance(away, str) or home == away:
            raise ValueError("invalid_NBA_team_ids")
        if rating is None:
            continue
        p = pregame_probability(rating.get(home, 1500.), rating.get(away, 1500.))
        if not 0 < p < 1:
            raise ValueError("invalid_forecast_probability")
        records.append({
            "record_type": "v8_genuine_forward_clocktime_NBA_Elo_research_only",
            "league": "nba", "espn_event_id": event_id,
            "home_team": event["home_team"], "away_team": event["away_team"],
            "home_team_espn_id": home, "away_team_espn_id": away,
            "start_utc": start.isoformat(), "forecast_recorded_utc": when.isoformat(),
            "schedule_original_received_at_utc": observed.isoformat(),
            "schedule_source_url": event["schedule_source_url"],
            "schedule_original_sha256_local_receipt":
                event["schedule_original_sha256_local_receipt"],
            "model_version": VERSION,
            "model_probability_home_win_research_only": round(p, 9),
            "estimated_away_win_probability_research_only": round(1-p, 9),
            "historical_matured_games_available_at_forecast": qualified_history,
            "assumed_result_maturity_hours": SETTLEMENT_ASSUMPTION_HOURS,
            "official_result_verified": False,
            "model_probability_independently_calibrated": False,
            "source_original_publisher_signed": False,
            "outcome_observed_at_utc": None,
            "outcome": None,
            "champion_001_shadow_certified": False,
            "qualifies_for_original_champion_shadow_quota": False,
            "forecast_reconstructed_after_game": False,
            "certified_prediction": False,
            "verified_positive_ev": False, "stake_usd": 0, "bet_ready": False,
            "champion_001_modified": False,
        })
    report = {
        "stage": "v8_elo_genuine_forward_clocktime_research_only",
        "captured_at_utc": when.isoformat(),
        "source_days_attempted": days,
        "source_days_succeeded": succeeded,
        "source_days_failed": failed,
        "history_games_retrieved": len(history),
        "matured_NBA_history_games": qualified_history,
        "future_schedule_events_seen": len(schedule),
        "forward_research_probabilities_recorded_before_tipoff": len(records),
        "research_lane": VERSION,
        "original_github_actions_receipt_external_verification": False,
        "original_champion_001_predictions_certified": 0,
        "v8_research_forward_predictions": len(records),
        "independently_certified_v8_predictions": 0,
        "independently_verified_draftkings_checkout_odds": 0,
        "certified_positive_ev_bets": 0, "automated_wagers": 0,
        "champion_001_modified": False, "bet_ready": False,
        "hold_reasons": dict(sorted(reasons.items())),
        "warning": ("Forecasts recorded before kickoff are research-only in a "
                    "separate V8 Elo lane. History contains published ESPN scores "
                    "captured now, and assumes 48h game-result maturity. A local "
                    "digest and GitHub timestamp are not publisher-signed independent "
                    "model/source authentication. No independent calibration, "
                    "injuries or executable sportsbook prices. Champion-001 shadows=0.")
    }
    return records, report


def capture(output_dir, *, history_days=DEFAULT_HISTORY_DAYS,
            fetch_schedule=download_json_original,
            history_collector=collect_scores,
            clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    first = _now(clock)
    if type(history_days) is not int or not 1 <= history_days <= MAX_HISTORY_DAYS:
        raise ValueError("historical_days_must_be_1_to_35")
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError("forward_captures_require_fresh_empty_directory")
    root.mkdir(parents=True, exist_ok=True)
    yesterday = first.astimezone(NY).date() - timedelta(days=1)
    # Each public historical scoreboard response is timestamped AFTER arrival
    # by the collector, not backdated to the game.
    history, coverage = history_collector(("nba",), history_days, yesterday)
    now = _now(clock)
    if now.astimezone(NY).date() != first.astimezone(NY).date():
        raise ValueError("scan_crossed_NY_calendar_date")
    future, failures, hashes = [], [], {}
    for delta in range(2):
        day = first.astimezone(NY).date() + timedelta(days=delta)
        url = BASE + urlencode({"dates": day.strftime("%Y%m%d"), "limit": 500})
        try:
            result = fetch_schedule(url)
            received = _now(clock)
            if (received < first or
                    received.astimezone(NY).date() != first.astimezone(NY).date()):
                raise ValueError("schedule_clock_regressed_or_crossed_eastern_day")
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError("original_schedule_response_bytes_required")
            parsed, raw = result
            items = parse_schedule_original(parsed, raw, day, received, url)
            filename = f"nba_original_future_schedule_{day:%Y%m%d}.json"
            with (root / filename).open("xb") as stream:
                stream.write(raw)
            hashes[day.isoformat()] = hashlib.sha256(raw).hexdigest()
            future.extend(items)
        except (ValueError, TypeError, TimeoutError, OSError, KeyError) as exc:
            failures.append({"date_et": day.isoformat(), "failure_class": type(exc).__name__})
    forecast_time = _now(clock)
    if forecast_time.astimezone(NY).date() != first.astimezone(NY).date():
        raise ValueError("forward_forecast_crossed_NY_calendar_date")
    records, report = project(history, future, coverage, forecast_time)
    if failures:
        report["schedule_source_day_failures"] = failures
        report["hold_reasons"]["missing_future_schedule_source_days"] = len(failures)
    report["schedule_original_sha256_local_receipts"] = hashes
    report["history_collection_started_at_utc"] = first.isoformat()
    report["github_action_run_id_self_reported"] = __import__("os").environ.get("GITHUB_RUN_ID")
    report["github_action_sha_self_reported"] = __import__("os").environ.get("GITHUB_SHA")
    (root / "NBA_FORWARD_FORECASTS.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in records),
        encoding="utf-8")
    (root / "NBA_FORWARD_RESEARCH_STATUS.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / "NBA_HISTORICAL_SOURCE_COVERAGE.json").write_text(
        json.dumps(coverage, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return records, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-days", type=int, default=DEFAULT_HISTORY_DAYS)
    ap.add_argument("--output-dir", default="v8_results/nba_forward")
    args = ap.parse_args(argv)
    forecast, report = capture(args.output_dir, history_days=args.history_days)
    print(json.dumps({
        "stage": report["stage"],
        "recorded_forward_research_forecasts": len(forecast),
        "certified_champion_shadows": 0, "certified_positive_ev_bets": 0,
        "source_days_failed": report["source_days_failed"],
        "hold_reasons": report["hold_reasons"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
