"""Independent NBA league schedule clock evidence for rejected near-time quotes.

This does NOT add events to the approved ESPN crosswalk, modify odds or
validate checkout prices. It only determines whether NBA's published scheduled
start aligns with ESPN, the odds provider, or neither. All five-minute/ten-
minute and ambiguous cases remain unaccepted for betting or model evaluation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from historical_outcomes import parse_time
from crossfeed_reconcile import norm

NBA_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
MAX_BYTES = 18_000_000
MAX_ACCEPTED_CLOCK_DIFF_SECONDS = 60

def nba_team_name(value):
    if not isinstance(value, str):
        return ""
    cleaned = norm(value)
    # NBA official CDN can say "LA Clippers"; odds feeds can say "Los Angeles
    # Clippers". This is a narrowly specified alias, NOT nickname guessing.
    return "los angeles clippers" if cleaned == "la clippers" else cleaned


def fetch_official_schedule(url=NBA_SCHEDULE_URL):
    if url != NBA_SCHEDULE_URL:
        raise ValueError("unexpected NBA schedule URL")
    req = Request(url, headers={"User-Agent": "FreddysPicks-NBAScheduleClockAudit/1.0",
                                "Accept": "application/json"})
    with urlopen(req, timeout=18) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("oversized NBA schedule")
    obj = json.loads(payload)
    if not isinstance(obj, dict):
        raise ValueError("invalid NBA schedule")
    return obj


def official_nba_events(payload):
    if not isinstance(payload, dict):
        raise ValueError("NBA source must be a JSON object")
    league = payload.get("leagueSchedule")
    if not isinstance(league, dict) or not isinstance(league.get("gameDates"), list):
        raise ValueError("missing NBA official schedule dates")
    result = []
    seen_ids = {}
    for day in league["gameDates"]:
        if not isinstance(day, dict) or not isinstance(day.get("games"), list):
            raise ValueError("malformed NBA gameDate")
        for game in day["games"]:
            if not isinstance(game, dict):
                continue
            if game.get("gameStatus") not in (1, "1"):
                continue
            try:
                home, away = game["homeTeam"], game["awayTeam"]
                home_name = nba_team_name(home["teamCity"] + " " + home["teamName"])
                away_name = nba_team_name(away["teamCity"] + " " + away["teamName"])
                start = parse_time(game["gameDateTimeUTC"])
                game_id = str(game["gameId"])
                if (not game_id.isdigit() or not home_name or not away_name
                        or home_name == away_name):
                    continue
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            signature = (start, home_name, away_name)
            if game_id in seen_ids and seen_ids[game_id] != signature:
                raise ValueError("conflicting NBA game ID")
            if game_id in seen_ids:
                continue
            seen_ids[game_id] = signature
            result.append({"official_nba_game_id": game_id,
                           "start": start, "home": home_name, "away": away_name})
    return result


def compare_clocks(manifest, official_payload, observed, source_error=None):
    if not isinstance(manifest, dict) or not isinstance(
            manifest.get("near_time_event_evidence_research_only"), list):
        raise ValueError("missing near-time manifest")
    if observed.tzinfo is None:
        raise ValueError("observation timestamp must be timezone-aware")
    if (manifest.get("bet_ready_selections") != 0
            or manifest.get("champion_001_modified") is not False
            or manifest.get("near_time_mismatches_promoted") != 0
            or manifest.get("independent_sportsbook_price_verified") is not False):
        raise ValueError("unsafe schedule manifest")
    if official_payload is None:
        games = []
        state = "unavailable"
    else:
        games = official_nba_events(official_payload)
        state = "retrieved"
    observed = observed.astimezone(timezone.utc)
    cases, counts = [], Counter()
    seen = set()
    for evidence in manifest["near_time_event_evidence_research_only"]:
        if not isinstance(evidence, dict) or evidence.get("league") != "nba":
            continue
        event_id = evidence.get("provider_event_id")
        if (not isinstance(event_id, str) or not event_id or event_id in seen
                or evidence.get("matched_for_research") is not False):
            raise ValueError("invalid/duplicate quarantined provider event")
        seen.add(event_id)
        provider_start = parse_time(evidence["provider_start_utc"])
        espn_start = parse_time(evidence["espn_start_utc"])
        delta = int((provider_start - espn_start).total_seconds())
        if (delta != evidence.get("signed_provider_minus_espn_seconds")
                or not 60 < abs(delta) <= 900):
            raise ValueError("inconsistent near-time evidence")
        home = nba_team_name(evidence.get("home_team"))
        away = nba_team_name(evidence.get("away_team"))
        if not home or not away or home == away:
            raise ValueError("ambiguous NBA team identification")
        possible = [g for g in games if g["home"] == home and g["away"] == away
                    and abs((g["start"] - espn_start).total_seconds()) <= 24*3600]
        if state == "unavailable":
            classification = "official_schedule_unavailable"
        elif len(possible) > 1:
            classification = "ambiguous_nba_schedule_identity"
        elif not possible:
            classification = "no_unique_official_nba_schedule_match"
        else:
            verified = possible[0]["start"]
            nba_vs_espn = int((verified - espn_start).total_seconds())
            nba_vs_provider = int((verified - provider_start).total_seconds())
            if abs(nba_vs_espn) <= MAX_ACCEPTED_CLOCK_DIFF_SECONDS:
                classification = "nba_clock_agrees_with_espn"
            elif abs(nba_vs_provider) <= MAX_ACCEPTED_CLOCK_DIFF_SECONDS:
                classification = "nba_clock_agrees_with_provider"
            else:
                classification = "nba_clock_disagrees_with_both"
        record = {
            "provider_event_id": event_id,
            "espn_event_id": str(evidence.get("espn_event_id") or ""),
            "provider_minus_espn_seconds": delta,
            "nba_clock_classification": classification,
            "remains_quarantined": True,
            "automatically_accepted_as_schedule_match": False,
        }
        if len(possible) == 1 and state == "retrieved":
            record["official_nba_game_id"] = possible[0]["official_nba_game_id"]
            record["nba_start_utc"] = possible[0]["start"].isoformat()
        cases.append(record)
        counts[classification] += 1
    return {
        "report_type": "independent_nba_clock_diagnostic_not_bet_ready",
        "observed_at_utc": observed.isoformat(),
        "official_nba_source_url": NBA_SCHEDULE_URL,
        "official_nba_source_status": state,
        "official_nba_source_error_type": source_error,
        "official_nba_schedule_games_parsed": len(games),
        "nba_near_time_events_checked": len(cases),
        "classification_counts": dict(sorted(counts.items())),
        "cases": sorted(cases, key=lambda r: r["provider_event_id"]),
        "near_time_mismatches_promoted": 0,
        "independently_verified_sportsbook_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "Public schedule reconciliation is diagnostic only. Every near-time event remains quarantined.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schedule-manifest", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    manifest = json.loads(Path(args.schedule_manifest).read_text(encoding="utf8"))
    evidence = manifest.get("near_time_event_evidence_research_only", [])
    if not isinstance(evidence, list):
        raise ValueError("invalid manifest evidence")
    has_nba = any(isinstance(x, dict) and x.get("league") == "nba" for x in evidence)
    observed = datetime.now(timezone.utc)
    payload, source_error = None, None
    if has_nba:
        try:
            payload = fetch_official_schedule()
        except (OSError, ValueError, TypeError, OverflowError) as exc:
            source_error = type(exc).__name__
    result = compare_clocks(manifest, payload, observed, source_error)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
