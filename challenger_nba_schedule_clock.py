"""Independent NBA league schedule clock evidence for rejected near-time quotes.

This does NOT add events to the approved ESPN crosswalk, modify odds or
validate checkout prices. It only determines whether NBA's published scheduled
start aligns with ESPN, the odds provider, or neither. All five-minute/ten-
minute and ambiguous cases remain unaccepted for betting or model evaluation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from historical_outcomes import parse_time
from crossfeed_reconcile import norm

NBA_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
NBA_TODAY_SCOREBOARD_URL = (
    "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
)
NBA_ALLOWED_URLS = (NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL)
NBA_STATS_SCOREBOARD_V3 = "https://stats.nba.com/stats/scoreboardv3"


def stats_scoreboard_url(game_day_et):
    """Build an exact, NBA-owned, date-bounded scoreboard URL; no arbitrary URL."""
    if not isinstance(game_day_et, str):
        raise ValueError("invalid official NBA game day")
    try:
        parsed = date.fromisoformat(game_day_et)
    except ValueError as exc:
        raise ValueError("invalid official NBA game day") from exc
    if parsed.isoformat() != game_day_et:
        raise ValueError("noncanonical official NBA game day")
    return f"{NBA_STATS_SCOREBOARD_V3}?GameDate={game_day_et}&LeagueID=00"

MAX_BYTES = 18_000_000
MAX_ACCEPTED_CLOCK_DIFF_SECONDS = 60

def nba_team_name(value):
    if not isinstance(value, str):
        return ""
    cleaned = norm(value)
    # NBA official CDN can say "LA Clippers"; odds feeds can say "Los Angeles
    # Clippers". This is a narrowly specified alias, NOT nickname guessing.
    return "los angeles clippers" if cleaned == "la clippers" else cleaned


def fetch_official_schedule(url=NBA_SCHEDULE_URL, opener=None):
    """Retrieve league-owned JSON with browser-style headers; no proxy sources."""
    # Only our two known CDN resources and a canonical date-specific NBA Stats
    # scoreboard are permitted. Error responses remain failures, never evidence.
    valid = url in NBA_ALLOWED_URLS
    if not valid and isinstance(url, str) and url.startswith(
            NBA_STATS_SCOREBOARD_V3 + "?GameDate="):
        day = url[len(NBA_STATS_SCOREBOARD_V3 + "?GameDate="):].split("&", 1)[0]
        try:
            valid = url == stats_scoreboard_url(day)
        except ValueError:
            valid = False
    if not valid:
        raise ValueError("untrusted NBA schedule URL")
    req = Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
    })
    # Pass opener explicitly for deterministic tests; no automatic retry storm.
    with (opener or urlopen)(req, timeout=18) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized NBA schedule")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("invalid NBA schedule")
    return obj


def source_failure_label(exc):
    """Report HTTP status without disclosing URLs with credentials or response bodies."""
    if isinstance(exc, HTTPError):
        return f"HTTP_{exc.code}" if isinstance(exc.code, int) else "HTTPError"
    if isinstance(exc, TimeoutError):
        return "TimeoutError"
    if isinstance(exc, URLError):
        return "URLError"
    return type(exc).__name__


def load_official_payload(fetcher=fetch_official_schedule, date_et=None):
    """Check league-owned endpoints, preserving denials and never assuming success.

    The date-specific NBA Stats v3 endpoint is a third possible source only
    when the unresolved evidence identifies one unambiguous Eastern game date.
    CDN and NBA Stats may both deny hosted clients. No WAF bypass is attempted.
    """
    errors = {}
    urls = list(NBA_ALLOWED_URLS)
    if date_et is not None:
        urls.append(stats_scoreboard_url(date_et))
    for url in urls:
        # One additional attempt only for transient timeouts. HTTP 403 is an
        # access denial, not a retryable source, and must remain quarantined.
        for attempt in range(2):
            try:
                payload = fetcher(url)
                if not isinstance(payload, dict):
                    raise ValueError("invalid NBA source")
                official_nba_events(payload)
                return payload, url, errors
            except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                label = source_failure_label(exc)
                if label == "TimeoutError" and attempt == 0:
                    continue
                errors[url] = label
                break
    return None, None, errors


def official_nba_events(payload):
    if not isinstance(payload, dict):
        raise ValueError("NBA source must be a JSON object")
    league = payload.get("leagueSchedule")
    board = payload.get("scoreboard")
    if isinstance(league, dict) and isinstance(league.get("gameDates"), list):
        day_groups = league["gameDates"]
        source_kind = "season_schedule"
    elif isinstance(board, dict) and isinstance(board.get("games"), list):
        if (board.get("leagueId") != "00" or
                not isinstance(board.get("gameDate"), str)):
            raise ValueError("invalid NBA today's scoreboard identity")
        try:
            datetime.fromisoformat(board["gameDate"])
        except ValueError as exc:
            raise ValueError("invalid NBA scoreboard game date") from exc
        day_groups = [{"games": board["games"]}]
        source_kind = "daily_scoreboard"
    else:
        raise ValueError("missing NBA official schedule dates")
    result = []
    seen_ids = {}
    for day in day_groups:
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
                start = parse_time(game["gameDateTimeUTC"] if source_kind == "season_schedule" else game["gameTimeUTC"])
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


def compare_clocks(manifest, official_payload, observed, source_error=None, source_url=None, source_errors=None):
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
    board = (official_payload.get("scoreboard")
             if isinstance(official_payload, dict) else None)
    scoreboard_date = board.get("gameDate") if isinstance(board, dict) else None
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
        game_day_et = espn_start.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        if state == "unavailable":
            classification = "official_schedule_unavailable"
        elif scoreboard_date is not None and scoreboard_date != game_day_et:
            classification = "official_scoreboard_date_mismatch"
            possible = []
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
        "official_nba_source_url": source_url or (
            NBA_TODAY_SCOREBOARD_URL if scoreboard_date is not None else NBA_SCHEDULE_URL),
        "official_nba_source_errors": source_errors or {},
        "official_nba_scoreboard_game_date_et": scoreboard_date,
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
    payload, url, errors = None, None, {}
    if has_nba:
        dates = set()
        for e in evidence:
            if isinstance(e, dict) and e.get("league") == "nba":
                t = parse_time(e["espn_start_utc"])
                dates.add(t.astimezone(ZoneInfo("America/New_York")).date().isoformat())
        # Multiple games on different days require different scoreboards. Do not
        # use a day's official data to corroborate another day.
        game_day = next(iter(dates)) if len(dates) == 1 else None
        payload, url, errors = load_official_payload(date_et=game_day)
        if len(dates) > 1:
            errors["date_scoped_nba_stats_fallback"] = "multiple_game_days"
    source_error = "nba_official_sources_unavailable" if has_nba and payload is None else None
    result = compare_clocks(
        manifest, payload, observed, source_error, source_url=url,
        source_errors=errors)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
