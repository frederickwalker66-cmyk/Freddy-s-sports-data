"""Prospective eight-league pregame evidence capture (research only).

Sources: ESPN public schedule + completed-game history captured as-of this run;
OPTIONAL older GitHub artifacts from SharpAPI, SportsGameOdds, official NBA/MLB
source scan. Neither an odds aggregator nor a roster archive establishes direct
DraftKings checkout prices, player availability, or verified model forecasts.
No prior historical features are retroactively certified.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from historical_outcomes import collect, parse_time
from independent_schedule_review import SOURCES, ingest_schedule

LEAGUES = tuple(SOURCES)
MAX_HISTORY_DAYS = 21
MIN_PRIOR = 3
WINDOW = 5
LAG_HOURS = 48
ALLOWED_ODDS_SOURCES = {"sharpapi_rest", "sportsgameodds_v2"}


def name_key(value):
    if not isinstance(value, str):
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def read_jsonl(path):
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return [json.loads(s) for s in p.read_text(encoding="utf8").splitlines() if s.strip()]


def read_report(path):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    obj = json.loads(p.read_text(encoding="utf8"))
    if not isinstance(obj, dict):
        raise ValueError("source report must be an object")
    return obj


def provenance(paths):
    items = []
    for role, path in paths.items():
        if not path:
            items.append({"role": role, "status": "not_supplied"})
            continue
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(str(p))
        raw = p.read_bytes()
        items.append({"role": role, "status": "read", "name": p.name,
                      "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    return items


def validated_odds(row, now):
    """Reject anything not actually archived before the future kickoff."""
    if not isinstance(row, dict):
        return None, "invalid_row"
    if (row.get("source") not in ALLOWED_ODDS_SOURCES
            or row.get("sportsbook") != "draftkings"
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None):
        return None, "not_quarantined_draftkings_research"
    try:
        start = parse_time(row["event_start_time"])
        quote = parse_time(row["timestamp"])
        received = parse_time(row["recorded_at"])
        if (start <= now or quote > received or received > now
                or received >= start or quote >= start):
            return None, "stale_or_after_start"
        if not 0 <= (received - quote).total_seconds() <= 900:
            return None, "old_or_future_provider_quote"
        if not 0 <= (now - received).total_seconds() <= 900:
            return None, "archive_quote_stale_at_snapshot"
        price = row.get("odds_american")
        if type(price) not in (int, float) or abs(price) < 100:
            return None, "invalid_odds"
        if not row.get("event_id") or not row.get("selection") or not row.get("market_type"):
            return None, "missing_market_identity"
    except (ValueError, KeyError, TypeError, OverflowError):
        return None, "invalid_odds_timestamp"
    return (start, quote, received), None


def team_form(history, team, game_start, scan):
    cutoff = game_start - timedelta(hours=LAG_HOURS)
    eligible = []
    for g in history:
        if not isinstance(g, dict) or g.get("record_type") != "historical_completed_game_research":
            continue
        try:
            past = parse_time(g["event_start_utc"])
            retrieved = parse_time(g["retrieved_at_utc"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (past < cutoff and retrieved <= scan and retrieved < game_start):
            continue
        home, away = name_key(g.get("home_team")), name_key(g.get("away_team"))
        if home != team and away != team:
            continue
        if type(g.get("home_score")) is not int or type(g.get("away_score")) is not int:
            continue
        diff = (g["home_score"] - g["away_score"]) * (1 if home == team else -1)
        eligible.append((past, str(g.get("espn_event_id") or ""), diff,
                         g.get("source_url")))
    # Unique ESPN game IDs in case multiple date endpoints repeat the same game.
    unique = {}
    for g in eligible:
        if g[1]:
            unique[g[1]] = g
    last = sorted(unique.values(), key=lambda g: (g[0], g[1]))[-WINDOW:]
    if len(last) < MIN_PRIOR:
        return None
    return {"last_games": len(last),
            "win_rate": round(sum(g[2] > 0 for g in last) / len(last), 6),
            "margin_average": round(sum(g[2] for g in last) / len(last), 6),
            "prior_espn_event_ids": [g[1] for g in last],
            "source_urls": [g[3] for g in last],
            "retrieval_asof_utc": scan.isoformat(),
            "result_start_embargo_hours": LAG_HOURS,
            "historical_original_publication_times_verified": False}


def build(snapshot, history, odds, official, now, coverage=None):
    if now.tzinfo is None:
        raise ValueError("capture time must include timezone")
    now = now.astimezone(timezone.utc)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("events"), list):
        raise ValueError("invalid ESPN schedule input")
    scan_at = parse_time(snapshot["collected_at_utc"])
    if scan_at > now:
        raise ValueError("schedule from the future")
    if not isinstance(history, list) or not isinstance(odds, list):
        raise ValueError("history and odds must be lists")
    if coverage is not None and not isinstance(coverage, dict):
        raise ValueError("history coverage must be an object")

    valid_quotes = []
    dropped = Counter()
    for quote in odds:
        timestamps, reason = validated_odds(quote, now)
        if reason:
            dropped[reason] += 1
        else:
            valid_quotes.append((quote, timestamps))
    if official and (official.get("champion_001_modified") is not False
                     or official.get("model_probabilities_generated") != 0
                     or official.get("player_props_cleared") != 0):
        raise ValueError("official archive unexpectedly promoted bets")

    events = []
    keys = set()
    for entry in snapshot["events"]:
        if not isinstance(entry, dict) or entry.get("league") not in LEAGUES:
            continue
        if entry.get("status") != "scheduled" or not entry.get("provider_game_id"):
            continue
        try:
            start = parse_time(entry["start_utc"])
            observed = parse_time(entry["observed_at_utc"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (start > now >= observed >= scan_at):
            continue
        home, away = name_key(entry.get("home_team")), name_key(entry.get("away_team"))
        if not home or not away or home == away:
            continue
        source_url = entry.get("source_url")
        parsed = urlparse(source_url or "")
        if parsed.scheme != "https" or parsed.hostname != "site.api.espn.com":
            continue
        key = (entry["league"], str(entry["provider_game_id"]))
        if key in keys:
            raise ValueError("duplicate ESPN schedule event")
        keys.add(key)
        events.append((entry, start, home, away))

    # A provider quote must resolve to exactly one independent schedule event.
    matched_quotes = defaultdict(list)
    for q, (qstart, quoted, received) in valid_quotes:
        matches = [entry for entry, start, h, a in events
                   if q.get("league") == entry["league"]
                   and name_key(q.get("home_team")) == h
                   and name_key(q.get("away_team")) == a
                   and abs((qstart - start).total_seconds()) <= 600]
        if len(matches) != 1:
            dropped["event_not_uniquely_matched"] += 1
            continue
        matched = matches[0]
        matched_quotes[(matched["league"], str(matched["provider_game_id"]))].append({
            "odds_provider": q["source"], "odds_provider_event_id": q["event_id"],
            "market_type": q["market_type"], "selection": q["selection"],
            "selection_type": q.get("selection_type"),
            "line": q.get("line"), "odds_american": q["odds_american"],
            "provider_updated_at_utc": quoted.isoformat(),
            "received_at_utc": received.isoformat(),
            "player_id_research_only": q.get("player_id"),
            "direct_draftkings_checkout_verified": False,
            "market_primary_line_verified": False,
            "player_available_verified": False,
        })

    official_start = None
    if official:
        official_start = parse_time(official["retrieved_at_utc"])
    records = []
    for entry, start, home, away in events:
        league = entry["league"]
        key = (league, str(entry["provider_game_id"]))
        history_for_league = [x for x in history if x.get("league") == league]
        fh = team_form(history_for_league, home, start, now)
        fa = team_form(history_for_league, away, start, now)
        official_status = None
        official_capture_before_game = False
        if official and official_start is not None:
            if league == "nba":
                official_status = official.get("sources", {}).get("nba", {}).get("status")
            elif league == "mlb":
                official_status = official.get("sources", {}).get("mlb_roster", {}).get("status")
            official_capture_before_game = official_status is not None and official_start < start and official_start <= now
        obs = matched_quotes.get(key, [])
        records.append({
            "record_type": "prospective_evidence_snapshot_research_only",
            "league": league, "espn_schedule_event_id": key[1],
            "home_team": entry["home_team"], "away_team": entry["away_team"],
            "event_start_utc": start.isoformat(), "snapshot_completed_at_utc": now.isoformat(),
            "schedule_source_url": entry["source_url"],
            "schedule_observed_at_utc": entry["observed_at_utc"],
            "home_team_form": fh, "away_team_form": fa,
            "team_form_available_for_both_teams": fh is not None and fa is not None,
            "odds_observations": obs,
            "league_source_inventory_status": official_status,
            "league_source_scan_before_event": official_capture_before_game,
            "player_level_status_parsed_and_verified": False,
            "historical_asof_provenance_for_prior_seasons_verified": False,
            "draftkings_direct_checkout_verified": False,
            "model_probability": None, "certified_prediction": False,
            "qualified_for_challenger_backtest": False,
            "bet_ready": False, "champion_001_modified": False,
        })
    counts = Counter(x["league"] for x in records)
    report = {
        "stage": "challenger_prospective_eight_league_evidence_research_only",
        "captured_at_utc": now.isoformat(),
        "scheduled_pregame_events": len(records),
        "by_league": {l: {
            "upcoming_events": counts[l],
            "both_teams_have_3plus_prior_published_results":
                sum(x["league"] == l and x["team_form_available_for_both_teams"] for x in records),
            "archived_draftkings_labeled_odds_observations":
                sum(len(x["odds_observations"]) for x in records if x["league"] == l),
        } for l in LEAGUES},
        "quote_rows_received": len(odds), "quote_rows_valid_asof_scan": len(valid_quotes),
        "quotes_rejected_or_unlinked": dict(sorted(dropped.items())),
        "official_source_report_supplied": bool(official),
        "history_coverage": coverage,
        "verified_historical_training_examples": 0,
        "direct_draftkings_checkout_quotes_verified": 0,
        "verified_player_availability_entries": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("This is a prospective snapshot, not a historical as-of archive "
                    "or certified forecast. Aggregator odds are not direct DraftKings "
                    "checkout; league inventory does not establish player availability. "
                    "No training or wager promotion."),
    }
    return records, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date-et")
    parser.add_argument("--history-days", type=int, default=14)
    parser.add_argument("--sharp-jsonl")
    parser.add_argument("--sgo-jsonl")
    parser.add_argument("--official-report")
    parser.add_argument("--output-dir", default="prospective_pregame")
    args = parser.parse_args(argv)
    if not 1 <= args.history_days <= MAX_HISTORY_DAYS:
        parser.error("history-days must be 1 to 21")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    utc_now = datetime.now(timezone.utc)
    day = args.date_et or utc_now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    # This makes no SharpAPI/SportsGameOdds calls and cannot retrieve paid odds.
    schedule = ingest_schedule(day, now=utc_now)
    prior_day = date.fromisoformat(day) - timedelta(days=1)
    results, coverage = collect(LEAGUES, args.history_days, prior_day)
    finish = datetime.now(timezone.utc)
    odds = read_jsonl(args.sharp_jsonl) + read_jsonl(args.sgo_jsonl)
    official = read_report(args.official_report)
    records, report = build(schedule, results, odds, official, finish, coverage)
    report["evidence_files"] = provenance({
        "sharpapi_odds": args.sharp_jsonl, "sportsgameodds_odds": args.sgo_jsonl,
        "official_source_report": args.official_report,
    })
    for filename, payload in (("espn_schedule_capture.json", schedule),
                              ("historical_score_capture.json", coverage)):
        (out / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf8")
    (out / "historical_published_results.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in results), encoding="utf8")
    (out / "prospective_event_evidence.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in records), encoding="utf8")
    (out / "prospective_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
