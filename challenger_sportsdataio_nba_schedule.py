"""SportsDataIO NBA schedule corroboration, isolated research-only adapter.

Never logs API keys, alters the ESPN crosswalk, promotes events, or creates picks.
A valid SportsDataIO subscription is necessary but is not tested by offline CI.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_nba_schedule_clock import nba_team_name
from historical_outcomes import parse_time

BASE = "https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/"
MAX_BYTES = 3_000_000
CLOCK_LIMIT_SECONDS = 60

NBA_TEAM_NAMES = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GS": "Golden State Warriors",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NO": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans",
    "NY": "New York Knicks",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHO": "Phoenix Suns",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SA": "San Antonio Spurs",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "UTAH": "Utah Jazz",
    "WAS": "Washington Wizards",
    "WSH": "Washington Wizards"
}



def schedule_url(day):
    if not isinstance(day, str):
        raise ValueError("invalid game day")
    parsed = date.fromisoformat(day)
    if parsed.isoformat() != day:
        raise ValueError("noncanonical game day")
    return BASE + day


def fetch_games(day, key, opener=None):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("missing SportsDataIO API key")
    req = Request(schedule_url(day), headers={
        "Ocp-Apim-Subscription-Key": key.strip(),
        "Accept": "application/json",
        "User-Agent": "FreddysPicksAI-Research/1.0",
    })
    with (opener or urlopen)(req, timeout=18) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized schedule")
    games = json.loads(raw)
    if not isinstance(games, list):
        raise ValueError("unexpected SportsDataIO schedule shape")
    return games


def parsed_games(rows):
    """Require unambiguous IDs, team codes and timezone-aware UTC start fields.

    SportsDataIO may expose naive DateTime strings in Eastern local time;
    never silently interpret those as UTC. A DateTimeUTC field is accepted
    only if it explicitly contains a UTC offset or Z suffix.
    """
    output, seen = [], set()
    for game in rows:
        if not isinstance(game, dict):
            continue
        game_id = game.get("GameID")
        home, away = game.get("HomeTeam"), game.get("AwayTeam")
        start_raw = game.get("DateTimeUTC")
        if not (isinstance(game_id, int) and game_id > 0 and
                isinstance(home, str) and isinstance(away, str) and
                isinstance(start_raw, str) and
                home.upper() in NBA_TEAM_NAMES and away.upper() in NBA_TEAM_NAMES and
                NBA_TEAM_NAMES[home.upper()] != NBA_TEAM_NAMES[away.upper()] and
                (start_raw.endswith("Z") or "+" in start_raw or
                 start_raw.endswith("+00:00"))):
            continue
        try:
            start = parse_time(start_raw)
        except (ValueError, TypeError, OverflowError):
            continue
        if start.tzinfo is None or game_id in seen:
            continue
        seen.add(game_id)
        output.append({"id": str(game_id), "home": home.upper(),
                       "away": away.upper(), "start": start.astimezone(timezone.utc)})
    return output


def corroborate(manifest, key, fetcher=fetch_games):
    if (manifest.get("bet_ready_selections") != 0 or
            manifest.get("champion_001_modified") is not False or
            manifest.get("near_time_mismatches_promoted") != 0 or
            manifest.get("independent_sportsbook_price_verified") is not False):
        raise ValueError("unsafe input manifest")
    evidence = manifest.get("near_time_event_evidence_research_only")
    if not isinstance(evidence, list):
        raise ValueError("missing near-time evidence")
    nba = [x for x in evidence if isinstance(x, dict) and x.get("league") == "nba"]
    days = sorted({parse_time(x["espn_start_utc"]).astimezone(
        ZoneInfo("America/New_York")).date().isoformat() for x in nba})
    by_day, errors = {}, {}
    for day in days:
        try:
            by_day[day] = parsed_games(fetcher(day, key))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
            errors[day] = ("HTTP_" + str(exc.code)) if isinstance(exc, HTTPError) else type(exc).__name__
            by_day[day] = []
    cases, seen_ids = [], set()
    for x in nba:
        event_id = x.get("provider_event_id")
        if (not isinstance(event_id, str) or not event_id or event_id in seen_ids
                or x.get("matched_for_research") is not False):
            raise ValueError("invalid quarantined event")
        seen_ids.add(event_id)
        espn = parse_time(x["espn_start_utc"])
        provider = parse_time(x["provider_start_utc"])
        delta = int((provider - espn).total_seconds())
        if delta != x.get("signed_provider_minus_espn_seconds") or not 60 < abs(delta) <= 900:
            raise ValueError("inconsistent clock evidence")
        day = espn.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        home = nba_team_name(x.get("home_team"))
        away = nba_team_name(x.get("away_team"))
        if not home or not away or home == away:
            raise ValueError("ambiguous NBA team identity")
        possible = [g for g in by_day[day]
                    if nba_team_name(NBA_TEAM_NAMES[g["home"]]) == home
                    and nba_team_name(NBA_TEAM_NAMES[g["away"]]) == away
                    and abs((g["start"] - espn).total_seconds()) <= 86400]
        if day in errors:
            classification = "sportsdataio_source_unavailable"
        elif len(possible) > 1:
            classification = "sportsdataio_ambiguous_team_and_day"
        elif not possible:
            classification = "sportsdataio_no_unique_team_and_day_match"
        else:
            start = possible[0]["start"]
            if abs((start - espn).total_seconds()) <= CLOCK_LIMIT_SECONDS:
                classification = "sportsdataio_clock_agrees_with_espn"
            elif abs((start - provider).total_seconds()) <= CLOCK_LIMIT_SECONDS:
                classification = "sportsdataio_clock_agrees_with_provider"
            else:
                classification = "sportsdataio_clock_disagrees_with_both"
        record = {"provider_event_id": event_id, "classification": classification,
                  "remains_quarantined": True,
                  "automatically_accepted_as_schedule_match": False}
        if len(possible) == 1 and day not in errors:
            record["sportsdataio_game_id"] = possible[0]["id"]
            record["sportsdataio_start_utc"] = possible[0]["start"].isoformat()
        cases.append(record)
    return {
        "report_type": "sportsdataio_nba_schedule_diagnostic_research_only",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_key_configured": bool(key),
        "requested_game_days": days,
        "source_errors_by_day": errors,
        "qualified_utc_games_by_day": {d: len(g) for d, g in by_day.items()},
        "nba_near_time_events_checked": len(cases),
        "classification_counts": dict(Counter(c["classification"] for c in cases)),
        "cases": cases,
        "near_time_mismatches_promoted": 0,
        "independently_verified_sportsbook_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "Entitlement and UTC schedule coverage diagnostic only. Explicit team-code crosswalk and UTC clocks are research-only; never automatic event approval.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schedule-manifest", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    manifest = json.loads(Path(args.schedule_manifest).read_text(encoding="utf8"))
    report = corroborate(manifest, os.environ.get("SPORTSDATAIO_API_KEY", ""))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
