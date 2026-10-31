"""SharpAPI DraftKings pregame odds collector (research only; no model forecasts).

Reference: https://docs.sharpapi.io/en/api-reference/odds/
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://api.sharpapi.io/api/v1/odds"
LEAGUES = ("nba", "nfl", "mlb")
MARKETS = ("main", "props")


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("no timestamp")
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timezone not supplied")
    return value.astimezone(timezone.utc)


def normalize_quote(row, received_at, max_age_seconds=900):
    """Reject in-play, stale, improperly timestamped, non-DraftKings observations."""
    if not isinstance(row, dict):
        return None
    if str(row.get("sportsbook", "")).lower() != "draftkings" or row.get("is_live") is not False:
        return None
    try:
        start = parse_time(row.get("event_start_time"))
        source = parse_time(row.get("timestamp"))
        american = row.get("odds_american")
        if isinstance(american, bool) or not isinstance(american, (int, float)) or abs(american) < 100:
            return None
        # Prematch at the actual time we fetched it, not just at provider timestamp.
        if start <= received_at or source >= start or source > received_at:
            return None
        age_seconds = (received_at - source).total_seconds()
        if age_seconds > max_age_seconds:
            return None
        if not all(row.get(field) is not None for field in ("event_id", "market_type", "selection")):
            return None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None
    fields = ("id", "sportsbook", "sport", "league", "event_id", "home_team",
              "away_team", "market_type", "selection", "selection_type", "player_name",
              "player_id", "line", "odds_american", "odds_decimal", "is_main_line",
              "is_alternate_line", "is_player_prop", "event_start_time", "timestamp")
    quote = {field: row.get(field) for field in fields}
    quote.update(record_type="pregame_odds_observation", recorded_at=received_at.isoformat(),
                 source_age_seconds=round(age_seconds, 1),
                 certified_prediction=False, model_probability=None, model_name=None,
                 source="sharpapi_rest")
    return quote


def get_page(key, league, market, cursor=None, max_429_retries=1):
    """Fetch provider data with a bounded 429 backoff; never reuse failed quotes.

    Push commits do not trigger paid calls; scheduled/manual jobs are serialized
    separately at the workflow level. An exhausted provider quota is NOT a
    successful or empty snapshot. Fail closed without printing credentials.
    """
    params = {"sportsbook": "draftkings", "league": league, "market": market,
              "is_live": "false", "limit": "200"}
    if cursor:
        params["cursor"] = cursor
    req = Request(ENDPOINT + "?" + urlencode(params),
                  headers={"X-API-Key": key, "Accept": "application/json"})
    for attempt in range(max_429_retries + 1):
        try:
            with urlopen(req, timeout=30) as reply:
                content = json.load(reply)
            break
        except HTTPError as exc:
            # Do not print API keys, request headers, URLs, or response bodies.
            if exc.code != 429:
                raise RuntimeError(f"SharpAPI HTTP {exc.code} for {league}/{market}") from None
            if attempt == max_429_retries:
                raise RuntimeError(f"SharpAPI HTTP 429 for {league}/{market}; rate limit persists") from None
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                requested_wait = int(retry_after) if retry_after is not None else 60
            except (TypeError, ValueError):
                requested_wait = 60
            if requested_wait > 120:
                raise RuntimeError(f"SharpAPI HTTP 429 for {league}/{market}; deferred by provider") from None
            time.sleep(max(60, requested_wait))
        except (URLError, TimeoutError):
            raise RuntimeError(f"SharpAPI network failure for {league}/{market}") from None
    if not isinstance(content, dict) or not isinstance(content.get("data"), list):
        raise RuntimeError("Unexpected SharpAPI payload schema")
    return content


def collect(key, leagues=LEAGUES, max_pages=4, pause_seconds=5.5):
    quotes = []
    seen = set()
    summary = []
    requests = 0
    for league in leagues:
        for market in MARKETS:
            cursor = None
            previous_cursors = set()
            count = 0
            pages = 0
            truncated = False
            while pages < max_pages:
                if requests:
                    time.sleep(pause_seconds)  # 12 req/min free-tier ceiling.
                content = get_page(key, league, market, cursor)
                received_at = now_utc()
                requests += 1
                pages += 1
                if not content["data"]:
                    store = content.get("meta", {}).get("store", {})
                    if store.get("reason") in ("warming", "store_empty"):
                        raise RuntimeError(f"SharpAPI store unavailable for {league}/{market}")
                for row in content["data"]:
                    quote = normalize_quote(row, received_at)
                    if quote is None:
                        continue
                    signature = (quote["id"], quote["timestamp"], quote["odds_american"], quote["line"])
                    if signature in seen:
                        continue
                    seen.add(signature)
                    quotes.append(quote)
                    count += 1
                pagination = content.get("pagination", {})
                truncated = bool(pagination.get("has_more"))
                if not truncated:
                    break
                new_cursor = pagination.get("next_cursor")
                if not new_cursor or new_cursor in previous_cursors:
                    raise RuntimeError(f"Invalid pagination cursor for {league}/{market}")
                previous_cursors.add(new_cursor)
                cursor = new_cursor
            summary.append({"league": league, "market": market, "pages": pages,
                            "quotes_recorded": count, "truncated": truncated})
    return quotes, summary, requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="snapshots")
    parser.add_argument("--leagues", default="nba,nfl,mlb")
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=5.5)
    args = parser.parse_args()
    key = os.environ.get("SHARPAPI_KEY")
    if not key:
        print("Missing SHARPAPI_KEY. Store it in GitHub Actions repository secrets.", file=sys.stderr)
        return 2
    leagues = tuple(s.strip().lower() for s in args.leagues.split(",") if s.strip())
    if not leagues or any(league not in LEAGUES for league in leagues):
        parser.error("Choose one or more of nba,nfl,mlb")
    if not (1 <= args.max_pages <= 40):
        parser.error("--max-pages must be from 1 to 40")
    if args.pause_seconds < 5.5:
        parser.error("--pause-seconds must be >= 5.5 to respect the free-tier rate limit")
    start = now_utc()
    try:
        odds, pages, api_calls = collect(key, leagues, args.max_pages, args.pause_seconds)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output = Path(args.output_dir)
    output.mkdir(exist_ok=True, parents=True)
    stamp = start.strftime("%Y%m%dT%H%M%SZ")
    filename = f"sharpapi_dk_{stamp}.jsonl"
    with (output / filename).open("w", encoding="utf8") as handle:
        for quote in odds:
            handle.write(json.dumps(quote, sort_keys=True, separators=(",", ":")) + "\n")
    status = {"collector": "sharpapi_draftkings_pregame", "started_at": start.isoformat(),
              "finished_at": now_utc().isoformat(), "api_calls": api_calls,
              "pregame_odds_quotes": len(odds), "certified_champion_001_picks": 0,
              "champion_001_modified": False, "pages": pages, "file": filename,
              "note": "These are sportsbook quotes, not model probabilities, picks, or validated EV."}
    (output / f"sharpapi_dk_{stamp}.summary.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
