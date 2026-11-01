"""SportsDataIO NBA schedule corroboration, isolated research-only adapter.

Never logs API keys, alters the ESPN crosswalk, promotes events, or creates picks.
A valid SportsDataIO subscription is necessary but is not tested by offline CI.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone, timedelta
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


def parse_games_with_diagnostics(rows):
    """Parse provider Game fields with explicit, independently checkable clocks.

    SportsDataIO documents DateTimeUTC as *UTC*, though actual NBA JSON
    serializes it without a Z/offset. Interpret only this named field as UTC.
    DateTime (when supplied) is Eastern wall time and must agree, including
    on daylight-saving transition days. Reject conflicting timestamps rather
    than silently overriding a source. Do not infer UTC from DateTime.
    """
    if not isinstance(rows, list):
        raise ValueError("unexpected SportsDataIO game list")
    reasons = Counter()
    repeated = Counter(
        row["GameID"] for row in rows if isinstance(row, dict)
        and type(row.get("GameID")) is int and row["GameID"] > 0
    )
    parsed = []
    naive_utc_accepted = 0
    eastern = ZoneInfo("America/New_York")
    for game in rows:
        if not isinstance(game, dict):
            reasons["non_object_row"] += 1
            continue
        game_id = game.get("GameID")
        if type(game_id) is not int or game_id <= 0:
            reasons["invalid_game_id"] += 1
            continue
        if repeated[game_id] > 1:
            reasons["duplicate_game_id"] += 1
            continue
        if game.get("Deleted") is True or game.get("Status") in ("Canceled", "Cancelled", "NotNecessary"):
            reasons["deleted_or_cancelled_game"] += 1
            continue
        home, away = game.get("HomeTeam"), game.get("AwayTeam")
        if (not isinstance(home, str) or not isinstance(away, str)
                or home.strip().upper() not in NBA_TEAM_NAMES
                or away.strip().upper() not in NBA_TEAM_NAMES
                or NBA_TEAM_NAMES[home.strip().upper()] == NBA_TEAM_NAMES[away.strip().upper()]):
            reasons["unknown_or_conflicting_team_codes"] += 1
            continue
        raw_utc = game.get("DateTimeUTC")
        if not isinstance(raw_utc, str) or "T" not in raw_utc:
            reasons["missing_or_invalid_utc_clock"] += 1
            continue
        try:
            parsed_utc = datetime.fromisoformat(raw_utc.replace("Z", "+00:00"))
            is_naive = parsed_utc.tzinfo is None
            if is_naive:
                start = parsed_utc.replace(tzinfo=timezone.utc)
            elif parsed_utc.utcoffset() != timedelta(0):
                reasons["non_utc_offset_in_utc_field"] += 1
                continue
            else:
                start = parsed_utc.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            reasons["missing_or_invalid_utc_clock"] += 1
            continue
        raw_local = game.get("DateTime")
        if raw_local is not None:
            if not isinstance(raw_local, str) or "T" not in raw_local:
                reasons["invalid_eastern_clock"] += 1
                continue
            try:
                parsed_local = datetime.fromisoformat(raw_local.replace("Z", "+00:00"))
                if parsed_local.tzinfo is not None:
                    parsed_local = parsed_local.astimezone(eastern)
                if parsed_local.replace(tzinfo=None) != start.astimezone(eastern).replace(tzinfo=None):
                    reasons["utc_eastern_clock_disagreement"] += 1
                    continue
            except (TypeError, ValueError, OverflowError):
                reasons["invalid_eastern_clock"] += 1
                continue
        parsed.append({"id": str(game_id), "home": home.strip().upper(),
                       "away": away.strip().upper(), "start": start})
        if is_naive:
            naive_utc_accepted += 1
    return parsed, {
        "provider_rows_received": len(rows),
        "accepted_unique_games": len(parsed),
        "naive_named_utc_clocks_validated": naive_utc_accepted,
        "rejection_causes": dict(sorted(reasons.items())),
    }


def parsed_games(rows):
    """Backward-compatible research-only parser interface."""
    return parse_games_with_diagnostics(rows)[0]

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
    by_day, errors, parser_diagnostics = {}, {}, {}
    for day in days:
        # Missing credentials are a configuration blocker, not an empty NBA
        # slate. Produce an explicit diagnostic without sending a network call
        # or exposing the credential in the resulting report.
        if not isinstance(key, str) or not key.strip():
            errors[day] = "credential_not_configured"
            by_day[day] = []
            continue
        try:
            by_day[day], parser_diagnostics[day] = parse_games_with_diagnostics(fetcher(day, key))
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
        "api_key_configured": isinstance(key, str) and bool(key.strip()),
        "requested_game_days": days,
        "source_errors_by_day": errors,
        "qualified_utc_games_by_day": {d: len(g) for d, g in by_day.items()},
        "provider_rows_by_day": {d: v["provider_rows_received"] for d, v in parser_diagnostics.items()},
        "naive_named_utc_clocks_validated_by_day": {
            d: v["naive_named_utc_clocks_validated"] for d, v in parser_diagnostics.items()},
        "parser_rejection_causes_by_day": {
            d: v["rejection_causes"] for d, v in parser_diagnostics.items()},
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


def probe_day(day, key, fetcher=fetch_games):
    """One-date provider smoke test; never certifies bets or game matches."""
    schedule_url(day)
    report = {
        "report_type": "sportsdataio_nba_source_live_smoke_research_only",
        "game_day_et": day,
        "api_key_configured": isinstance(key, str) and bool(key.strip()),
        "source_status": "credential_not_configured",
        "provider_rows_received": 0,
        "accepted_unique_games": 0,
        "naive_named_utc_clocks_validated": 0,
        "parser_rejection_causes": {},
        "source_error": None,
        "independently_verified_sportsbook_prices": 0,
        "near_time_mismatches_promoted": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
    }
    if not report["api_key_configured"]:
        return report
    try:
        games, d = parse_games_with_diagnostics(fetcher(day, key))
        report["provider_rows_received"] = d["provider_rows_received"]
        report["accepted_unique_games"] = len(games)
        report["naive_named_utc_clocks_validated"] = d["naive_named_utc_clocks_validated"]
        report["parser_rejection_causes"] = d["rejection_causes"]
        report["source_status"] = (
            "validated_nonempty" if games else
            "provider_returned_empty" if not d["provider_rows_received"] else
            "all_provider_rows_rejected"
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
        report["source_status"] = "provider_unavailable"
        report["source_error"] = (
            "HTTP_" + str(exc.code) if isinstance(exc, HTTPError)
            else type(exc).__name__
        )
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--schedule-manifest")
    mode.add_argument("--probe-day", help="Eastern game date YYYY-MM-DD; provider-only smoke test")
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    if args.probe_day:
        report = probe_day(args.probe_day, os.environ.get("SPORTSDATAIO_API_KEY", ""))
    else:
        manifest = json.loads(Path(args.schedule_manifest).read_text(encoding="utf8"))
        report = corroborate(manifest, os.environ.get("SPORTSDATAIO_API_KEY", ""))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not args.probe_day or report["source_status"] == "validated_nonempty" else 1


if __name__ == "__main__":
    raise SystemExit(main())
