"""Fail-closed ESPN schedule corroboration for archived odds research.

Matches each odds-provider event ID to exactly one *future* ESPN scheduled game,
with the same sport, normalized home and away names, and a start within 60s.
This is not a sportsbook quote, independent result adjudication, live bet, or
certified player availability. Incomplete/outdated schedules stay quarantined.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from crossfeed_reconcile import norm
from independent_schedule_review import ingest_schedule, SOURCES
from historical_outcomes import parse_time

MAX_DAYS = 3
MAX_AHEAD_DAYS = 7
MAX_START_DISAGREEMENT_SECONDS = 60


def _name(value):
    return norm(value)


def _quote_identity(row, now):
    if not isinstance(row, dict) or row.get("league") not in SOURCES:
        return None
    if row.get("certified_prediction") is not False or row.get("model_probability") is not None:
        return None
    if row.get("sportsbook") != "draftkings" or not row.get("event_id"):
        return None
    home, away = _name(row.get("home_team")), _name(row.get("away_team"))
    if not home or not away or home == away:
        return None
    try:
        start = parse_time(row["event_start_time"])
        received = parse_time(row["recorded_at"])
    except (TypeError, KeyError, ValueError, OverflowError):
        return None
    if not (received <= now < start and received < start and
            start <= now + timedelta(days=MAX_AHEAD_DAYS)):
        return None
    return (str(row["event_id"]), row["league"], home, away, start)


def build_manifest(rows, schedules, now):
    if now.tzinfo is None:
        raise ValueError("current time requires timezone")
    now = now.astimezone(timezone.utc)
    if not isinstance(rows, list) or not isinstance(schedules, list):
        raise ValueError("expected lists")
    schedule_events = []
    invalid_schedule = 0
    for snapshot in schedules:
        if (not isinstance(snapshot, dict)
                or not isinstance(snapshot.get("events"), list)):
            raise ValueError("invalid independent schedule payload")
        observed = parse_time(snapshot["collected_at_utc"])
        if observed > now:
            raise ValueError("future independent schedule")
        for event in snapshot["events"]:
            try:
                start = parse_time(event["start_utc"])
                captured = parse_time(event["observed_at_utc"])
                url = urlparse(event["source_url"])
                home, away = _name(event["home_team"]), _name(event["away_team"])
                event_id = str(event["provider_game_id"])
                if (url.scheme != "https" or url.hostname != "site.api.espn.com"
                        or event.get("status") != "scheduled"
                        or event.get("league") not in SOURCES
                        or not event_id.isdigit() or not home or not away or home == away
                        or not observed <= captured <= now < start):
                    raise ValueError("non-prospective or untrusted schedule")
            except (KeyError, TypeError, ValueError, OverflowError):
                invalid_schedule += 1
                continue
            schedule_events.append((event, start, home, away))
    # Identical ESPN date-endpoint repeats are expected; de-duplicate
    # by league and ESPN ID. Conflicting contents make the identity ambiguous.
    unique = {}
    conflicts = set()
    for event, start, home, away in schedule_events:
        key = (event["league"], str(event["provider_game_id"]))
        signature = (start, home, away)
        if key in unique and unique[key][0] != signature:
            conflicts.add(key)
        else:
            unique[key] = (signature, event)
    candidates = [(ev, sig[0], sig[1], sig[2])
                  for k, (sig, ev) in unique.items() if k not in conflicts]

    source_groups = defaultdict(list)
    for row in rows:
        identity = _quote_identity(row, now)
        if identity is not None:
            source_groups[identity[0]].append(identity[1:])
    manifest = {}
    rejected = Counter()
    for provider_id, group in source_groups.items():
        identities = {(lg, h, a, start) for lg, h, a, start in group}
        if len(identities) != 1:
            rejected["conflicting_provider_event_identity"] += 1
            continue
        league, home, away, start = next(iter(identities))
        hits = [
            e for e, st, h, a in candidates
            if e["league"] == league and home == h and away == a
            and abs((st - start).total_seconds()) <= MAX_START_DISAGREEMENT_SECONDS
        ]
        if len(hits) != 1:
            rejected["missing_or_ambiguous_espn_match"] += 1
            continue
        ev = hits[0]
        manifest[provider_id] = {
            "event_id": provider_id, "league": league,
            "home_team": group_to_original(rows, provider_id, "home_team"),
            "away_team": group_to_original(rows, provider_id, "away_team"),
            "start_utc": ev["start_utc"], "source_url": ev["source_url"],
            "espn_event_id": str(ev["provider_game_id"]),
            "espn_observed_at_utc": ev["observed_at_utc"],
            "corroboration": "ESPN public schedule; automated research only",
        }
    output = {
        "events": list(manifest.values()),
        "provenance": "automated_ESPN_schedule_unique_crosswalk_research_only",
        "schedule_events_seen": len(schedule_events),
        "invalid_schedule_rows": invalid_schedule,
        "conflicting_espn_ids": len(conflicts),
        "provider_event_ids_seen": len(source_groups),
        "provider_event_ids_matched": len(manifest),
        "provider_event_ids_quarantined": dict(sorted(rejected.items())),
        "independent_sportsbook_price_verified": False,
        "certified_model_predictions": 0,
        "bet_ready_selections": 0,
        "champion_001_modified": False,
    }
    return output


def group_to_original(rows, provider_id, field):
    # The exact observed spelling is preserved for the downstream validator.
    for row in rows:
        if isinstance(row, dict) and str(row.get("event_id")) == provider_id:
            return row[field]
    raise ValueError("unreachable missing provider event")


def collect_snapshot_days(rows, now):
    et_today = now.astimezone(ZoneInfo("America/New_York")).date()
    days = set()
    for row in rows:
        identity = _quote_identity(row, now)
        if identity is None:
            continue
        event_day = identity[4].astimezone(ZoneInfo("America/New_York")).date()
        if 0 <= (event_day - et_today).days <= MAX_AHEAD_DAYS:
            days.add(event_day)
    return sorted(days)[:MAX_DAYS]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--odds", required=True)
    p.add_argument("--outdir", required=True)
    args = p.parse_args(argv)
    rows = [json.loads(line) for line in Path(args.odds).read_text(encoding="utf8").splitlines()
            if line.strip()]
    now = datetime.now(timezone.utc)
    dates = collect_snapshot_days(rows, now)
    snapshots = [ingest_schedule(day.isoformat(), now=now) for day in dates]
    report = build_manifest(rows, snapshots, datetime.now(timezone.utc))
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k != "events"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
