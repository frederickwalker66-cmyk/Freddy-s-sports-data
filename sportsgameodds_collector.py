"""SportsGameOdds v2 DraftKings pregame evidence collector — RESEARCH ONLY.

Runs separately from SharpAPI and Champion-001. Source/bookmaker IDs are not
official league IDs. Quotes are never interpreted as model probabilities.
SportsGameOdds docs: https://sportsgameodds.com/docs/basics/quickstart
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://api.sportsgameodds.com/v2/events"
MAX_QUOTE_AGE_SECONDS = 900  # Research intake only; the independent audit still requires <=120 seconds.
MAX_PAGES = 3
MAX_EVENTS_PER_PAGE = 25
# Scheduled coverage uses the eight leagues documented for the Amateur/free plan.
# Extra leagues must be checked against the user's /leagues entitlement before enabling.
LEAGUE_SPORTS = {
    "nba": "basketball", "wnba": "basketball", "ncaab": "basketball",
    "nfl": "football", "ncaaf": "football",
    "mlb": "baseball", "nhl": "hockey",
    "mls": "soccer", "uefa_champions_league": "soccer",
}
AMERICAN = re.compile(r"^[+-]?[0-9]{3,5}$")


def utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp missing")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone missing")
    return result.astimezone(timezone.utc)


def price(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    raw = str(value).strip()
    if not AMERICAN.fullmatch(raw):
        return None
    result = int(raw)
    return result if abs(result) >= 100 else None


def line_number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def long_name(entry):
    if not isinstance(entry, dict):
        return None
    names = entry.get("names")
    candidate = names.get("long") if isinstance(names, dict) else None
    if not candidate:
        candidate = entry.get("name")
    return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None


def normalize_event(event, received_at):
    """Return conservative main-market rows and per-reason drop statistics."""
    drops = Counter()
    if not isinstance(event, dict):
        return [], Counter({"invalid_event": 1})
    league = str(event.get("leagueID", "")).lower()
    event_id = event.get("eventID")
    teams = event.get("teams")
    status = event.get("status")
    if (league not in LEAGUE_SPORTS or not isinstance(event_id, str)
            or not event_id or not isinstance(teams, dict)
            or not isinstance(status, dict)):
        return [], Counter({"missing_event_identity": 1})
    home = long_name(teams.get("home"))
    away = long_name(teams.get("away"))
    if not home or not away or home == away:
        return [], Counter({"missing_team_names": 1})
    if any(status.get(field) is True for field in ("started", "live", "completed", "cancelled", "ended")):
        return [], Counter({"event_not_pregame": 1})
    # The live SGO v2 event schema locates kickoff under status.startsAt.
    start_str = status.get("startsAt") or event.get("startTime")
    try:
        start = utc(start_str)
    except (TypeError, ValueError, OverflowError):
        return [], Counter({"invalid_event_time": 1})
    if start <= received_at:
        return [], Counter({"event_not_pregame": 1})
    all_odds = event.get("odds")
    if not isinstance(all_odds, dict):
        return [], Counter({"missing_odds": 1})
    players = event.get("players") if isinstance(event.get("players"), dict) else {}
    rows = []
    for odd_id, odd in all_odds.items():
        if not isinstance(odd, dict) or not isinstance(odd_id, str):
            drops["invalid_market"] += 1
            continue
        # Restrict to full-game primary-market query. No period/alt-line leakage.
        if odd.get("periodID") != "game" or any(odd.get(k) is True for k in ("started", "ended", "cancelled")):
            drops["period_or_market_closed"] += 1
            continue
        book = odd.get("byBookmaker")
        dk = book.get("draftkings") if isinstance(book, dict) else None
        if not isinstance(dk, dict) or dk.get("available") is not True:
            drops["draftkings_unavailable"] += 1
            continue
        american = price(dk.get("odds"))
        if american is None:
            drops["invalid_draftkings_price"] += 1
            continue
        try:
            updated_at = utc(dk.get("lastUpdatedAt"))
            age = (received_at - updated_at).total_seconds()
            if not 0 <= age <= MAX_QUOTE_AGE_SECONDS or updated_at >= start:
                raise ValueError("stale or future quote")
        except (TypeError, ValueError, OverflowError):
            drops["stale_missing_or_future_quote_time"] += 1
            continue
        bet_type = odd.get("betTypeID")
        side = odd.get("sideID")
        entity = odd.get("statEntityID")
        stat = odd.get("statID")
        if not isinstance(stat, str) or not re.fullmatch(r"[A-Za-z0-9_+]+", stat):
            drops["unknown_stat"] += 1
            continue
        sel_type, market_type, selection, number, player_id, player_name = None, None, None, None, None, None
        if bet_type == "ml" and entity in ("home", "away") and side in ("home", "away") and entity == side:
            market_type = "moneyline"
            sel_type = side
            selection = home if side == "home" else away
        elif bet_type == "sp" and entity in ("home", "away") and side in ("home", "away") and entity == side:
            market_type = ("run_line" if league == "mlb" else
                           "puck_line" if league == "nhl" else
                           "goal_spread" if LEAGUE_SPORTS[league] == "soccer" else "point_spread")
            sel_type = side
            selection = home if side == "home" else away
            number = line_number(dk.get("spread"))
        elif bet_type == "ou" and side in ("over", "under"):
            sel_type = side
            number = line_number(dk.get("overUnder"))
            if entity in ("all", "home", "away"):
                market_type = "total_" + stat
                selection = (("Home " if entity == "home" else "Away " if entity == "away" else "")
                             + side.title())
            elif isinstance(odd.get("playerID"), str) and odd.get("playerID") == entity:
                player_id = odd["playerID"]
                player = players.get(player_id)
                if isinstance(player, dict):
                    player_name = long_name(player)
                if not isinstance(player_name, str) or not player_name.strip():
                    drops["player_name_missing"] += 1
                    continue
                market_type = "player_" + stat
                selection = player_name.strip() + " " + side.title()
        if not market_type or not selection or (bet_type in ("ou", "sp") and number is None):
            drops["unsupported_or_missing_line"] += 1
            continue
        decimal = 1 + (american / 100 if american > 0 else 100 / abs(american))
        rows.append({
            "id": "sgo:" + event_id + ":" + odd_id + ":draftkings",
            "record_type": "pregame_odds_observation",
            "source": "sportsgameodds_v2",
            "sportsbook": "draftkings",
            "sport": LEAGUE_SPORTS[league],
            "league": league,
            "event_id": "sgo:" + event_id,
            "provider_event_id": event_id,
            "provider_odd_id": odd_id,
            "home_team": home, "away_team": away,
            "market_type": market_type, "selection": selection,
            "selection_type": sel_type,
            "player_name": player_name, "player_id": player_id,
            "line": number, "odds_american": american,
            "odds_decimal": round(decimal, 5),
            # SGO's default includeAltLines=false does not independently
            # establish an audited primary line: fail closed on this field.
            "is_main_line": False, "is_alternate_line": False,
            "is_player_prop": player_id is not None,
            "event_start_time": start.isoformat(),
            "timestamp": updated_at.isoformat(),
            "recorded_at": received_at.isoformat(),
            "source_age_seconds": round(age, 2),
            "certified_prediction": False,
            "model_probability": None, "model_name": None,
            "cross_provider_identity_verified": False,
            "draftkings_price_independently_verified": False,
        })
    return rows, drops


def get_page(api_key, leagues, limit, cursor=None):
    params = {"leagueID": ",".join(leagues), "oddsAvailable": "true",
              "started": "false", "live": "false", "ended": "false", "cancelled": "false",
              "includeAltLines": "false", "bookmakerID": "draftkings",
              "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    request = Request(ENDPOINT + "?" + urlencode(params),
                      headers={"x-api-key": api_key, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        # Never log credentials, raw provider response, or request headers.
        raise RuntimeError("SportsGameOdds HTTP " + str(exc.code) + (" (check stored API key validity)" if exc.code == 401 else "")) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise RuntimeError("SportsGameOdds request failed") from None
    if not isinstance(payload, dict) or payload.get("success") is False or not isinstance(payload.get("data"), list):
        raise RuntimeError("SportsGameOdds reported an error or unexpected schema")
    return payload


def collect(api_key, leagues, max_pages=1, limit=25, pause_seconds=2, fetch=get_page, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    seen, rows, skips, pages = set(), [], Counter(), []
    cursor = None
    previous = set()
    for page in range(max_pages):
        if page:
            time.sleep(pause_seconds)
        data = fetch(api_key, leagues, limit, cursor)
        recorded = clock()
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise RuntimeError("Invalid API response")
        for event in data["data"]:
            event_rows, reasons = normalize_event(event, recorded)
            skips.update(reasons)
            for row in event_rows:
                signature = (row["id"], row["timestamp"], row["odds_american"], row["line"])
                if signature in seen:
                    continue
                seen.add(signature)
                rows.append(row)
        next_cursor = data.get("nextCursor")
        pages.append({"events_returned": len(data["data"]), "has_next": bool(next_cursor)})
        if not next_cursor:
            break
        if not isinstance(next_cursor, str) or next_cursor in previous or next_cursor == cursor:
            raise RuntimeError("Repeated or invalid SportsGameOdds page cursor")
        previous.add(next_cursor)
        cursor = next_cursor
    return rows, pages, skips


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="snapshots")
    parser.add_argument("--leagues", default="NBA,NFL,MLB,NHL,NCAAF,NCAAB,MLS,UEFA_CHAMPIONS_LEAGUE")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args(argv)
    leagues = tuple(part.strip().upper() for part in args.leagues.split(",") if part.strip())
    if not leagues or any(league.lower() not in LEAGUE_SPORTS for league in leagues):
        parser.error("Allowed leagues: " + ",".join(LEAGUE_SPORTS).upper())
    if not 1 <= args.limit <= MAX_EVENTS_PER_PAGE or not 1 <= args.max_pages <= MAX_PAGES:
        parser.error("Limits: 1-25 events per page, 1-3 pages")
    key = (os.environ.get("SPORTSGAMEODDS_API_KEY") or "").strip()
    if not key:
        print("SportsGameOdds GitHub secret not supplied to the job", file=sys.stderr)
        return 2
    started = datetime.now(timezone.utc)
    try:
        # A combined multi-league page can overrepresent one league.
        # Query each league separately while limiting total credit exposure.
        quotes, pages, reasons = [], [], Counter()
        for league in leagues:
            league_quotes, league_pages, league_skips = collect(
                key, (league,), args.max_pages, args.limit)
            quotes.extend(league_quotes)
            pages.extend(dict(page, league=league) for page in league_pages)
            reasons.update(league_skips)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = directory / ("sportsgameodds_dk_" + stamp + ".jsonl")
    with path.open("w", encoding="utf-8") as out:
        for quote in quotes:
            out.write(json.dumps(quote, separators=(",", ":"), sort_keys=True) + "\n")
    summary = {
        "source": "sportsgameodds_v2_draftkings",
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "leagues": leagues, "pages": pages,
        "event_credits_upper_bound": sum(p["events_returned"] for p in pages),
        "leagues_queried_separately": True,
        "quotes_recorded": len(quotes), "skipped": dict(sorted(reasons.items())),
        "research_quote_max_age_seconds": MAX_QUOTE_AGE_SECONDS,
        "strict_betting_validation_quote_max_age_seconds": 120,
        "file": path.name, "source_identity_crosswalk_verified": False,
        "independently_reverified_draftkings_prices": 0,
        "bet_ready_selections": 0, "certified_champion_001_predictions": 0,
        "model_probabilities_generated": 0, "champion_001_modified": False,
        "note": "Research-only provider observations. Not certified picks, EV, or bet-ready."
    }
    (directory / ("sportsgameodds_dk_" + stamp + ".summary.json")).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
