"""Hourly best-effort public ESPN scores and market-reference collection.

Eight leagues. No paid API, sportsbook account, private keys, model execution,
or wagers. ESPN provider-labelled fields are RESEARCH REFERENCES ONLY:
an HTTP observation time is NOT a bookmaker's line-posting timestamp.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from independent_schedule_review import SOURCES, BASE

NY = ZoneInfo("America/New_York")
MAX_BYTES = 5_000_000
MAX_EVENTS = 500
MAX_OUTPUT_EVENTS = 120
LEAGUES = tuple(SOURCES)


def utc_iso(text):
    if not isinstance(text, str):
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def scrub(text, limit=100):
    if not isinstance(text, str):
        return ""
    return "".join(c for c in text if c.isprintable())[:limit].strip()


def amount(v, low, high):
    if type(v) in (int, float) and math.isfinite(v) and low <= v <= high:
        return float(v)
    return None


def american(v):
    # ESPN book-labelled American prices; only explicit numeric examples.
    if isinstance(v, str) and re.fullmatch(r"[+-]?\d{3,5}", v):
        v = int(v)
    if type(v) is int and 100 <= abs(v) <= 99999:
        return v
    return None


def source_fetch(url):
    request = Request(url, headers={
        "User-Agent": "FreddysPicks-ESPN-PublicResearch/1.0",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=12) as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("missing_or_oversized_ESPN_response")
    result = json.loads(raw)
    if not isinstance(result, dict) or not isinstance(result.get("events"), list):
        raise ValueError("ESPN_response_missing_events")
    return result


def parse_market(competition, league):
    prices = competition.get("odds") or []
    if not isinstance(prices, list):
        return None
    for item in prices[:5]:
        if not isinstance(item, dict):
            continue
        provider = item.get("provider") or {}
        provider_name = scrub(provider.get("name"), 64) if isinstance(provider, dict) else ""
        # A price without a named source is not displayed.
        if not provider_name:
            continue
        home = item.get("homeTeamOdds") or {}
        away = item.get("awayTeamOdds") or {}
        if not isinstance(home, dict) or not isinstance(away, dict):
            continue
        ml_home = american(home.get("moneyLine"))
        ml_away = american(away.get("moneyLine"))
        # Soccer moneyline requires 3-way HOME/DRAW/AWAY confirmation;
        # never mislabel two-way odds as a standard 90-minute ML.
        if league in ("mls", "uefa_champions_league"):
            ml_home = ml_away = None
        spread_details = scrub(item.get("details"), 55)
        total = amount(item.get("overUnder"), 0.5, 999.5)
        spread_price_home = american(home.get("spreadOdds"))
        spread_price_away = american(away.get("spreadOdds"))
        over_price = american(item.get("overOdds"))
        under_price = american(item.get("underOdds"))
        if all(x is None for x in (ml_home, ml_away, total)) and not spread_details:
            continue
        return {
            "provider_name": provider_name,
            "away_moneyline": ml_away, "home_moneyline": ml_home,
            "spread_details": spread_details or None,
            "away_spread_price": spread_price_away,
            "home_spread_price": spread_price_home,
            "total": total, "over_price": over_price, "under_price": under_price,
            "bookmaker_quote_timestamp_utc": None,
            "direct_checkout_verified": False,
            "market_reference_only": True,
            "no_sharp_money_or_ev_claim": True,
        }
    return None


def parse_scoreboard(league, payload, *, date_et, observed_at):
    if (not isinstance(payload, dict) or not isinstance(payload.get("events"), list)
            or len(payload["events"]) > MAX_EVENTS):
        raise ValueError("unexpected_scoreboard_structure")
    out, seen = [], set()
    for item in payload["events"]:
        if not isinstance(item, dict):
            continue
        game_id = str(item.get("id") or "")
        if not re.fullmatch(r"\d{4,20}", game_id) or game_id in seen:
            continue
        cs = item.get("competitions")
        if not isinstance(cs, list) or not cs or not isinstance(cs[0], dict):
            continue
        comp = cs[0]
        sides = {}
        scores = {}
        for entry in comp.get("competitors") or []:
            if not isinstance(entry, dict):
                continue
            side = entry.get("homeAway")
            team = entry.get("team") or {}
            if side not in ("home", "away") or not isinstance(team, dict):
                continue
            sides[side] = scrub(team.get("displayName"), 90)
            val = entry.get("score")
            try:
                scores[side] = int(val) if re.fullmatch(r"\d{1,3}", str(val)) else None
            except (TypeError, ValueError):
                scores[side] = None
        if not sides.get("home") or not sides.get("away") or sides["home"] == sides["away"]:
            continue
        start = utc_iso(item.get("date") or comp.get("date"))
        if not start or start.astimezone(NY).date().isoformat() != date_et:
            continue
        status_obj = item.get("status") or {}
        state = (status_obj.get("type") or {}).get("state") if isinstance(status_obj, dict) else None
        if state not in ("pre", "in", "post"):
            continue
        seen.add(game_id)
        market = parse_market(comp, league)
        row = {
            "id": game_id,
            "home": sides["home"], "away": sides["away"],
            "start_et": start.astimezone(NY).isoformat(),
            "status": state,
            "home_score": scores.get("home") if state in ("in", "post") else None,
            "away_score": scores.get("away") if state in ("in", "post") else None,
            "period": amount(status_obj.get("period"), 0, 25),
            "clock": scrub(status_obj.get("displayClock"), 18),
            "market_reference": market,
            "observed_at_utc": observed_at,
        }
        out.append(row)
    out.sort(key=lambda e: (e["start_et"], e["id"]))
    if len(out) > MAX_OUTPUT_EVENTS:
        raise ValueError("too_many_events_for_public_output")
    return out


def collect(*, fetch=source_fetch, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    if not isinstance(started, datetime) or started.tzinfo is None:
        raise ValueError("aware_capture_clock_required")
    started = started.astimezone(timezone.utc)
    et = started.astimezone(NY).date().isoformat()
    result = {
        "schema": "freddys-espn-public-hourly-v1",
        "date_et": et, "collected_at_utc": started.isoformat(),
        "leagues": {}, "provider_checkout_ever_verified": False,
        "certified_positive_ev": 0, "champion_001_modified": False,
        "notes": "Best-effort ESPN scores and provider-labelled comparison references. No authentic sportsbook checkout, quote-posted timestamp, or certified EV.",
    }
    for league,(sport,division) in SOURCES.items():
        url = BASE+"/"+sport+"/"+division+"/scoreboard?"+urlencode({
            "dates": et.replace("-", ""), "limit": 500,
        })
        try:
            response = fetch(url)
            observed = clock()
            if not isinstance(observed, datetime) or observed.tzinfo is None:
                raise ValueError("invalid_response_observation_clock")
            observed = observed.astimezone(timezone.utc)
            if observed < started or observed.astimezone(NY).date().isoformat() != et:
                raise ValueError("observation_clock_regressed_or_crossed_day")
            rows = parse_scoreboard(league, response, date_et=et, observed_at=observed.isoformat())
            result["leagues"][league] = {
                "status": "ESPN_SCOREBOARD_OBSERVED", "source_url": url,
                "observed_at_utc": observed.isoformat(), "games": rows,
                "game_count": len(rows),
                "line_reference_count": sum(g["market_reference"] is not None for g in rows),
            }
        except (OSError, ValueError, TimeoutError, TypeError, KeyError, json.JSONDecodeError):
            result["leagues"][league] = {
                "status": "SOURCE_UNAVAILABLE",
                "observed_at_utc": None, "source_url": url,
                "games": [], "game_count": None, "line_reference_count": None,
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dashboard_inputs/public_scoreboard.json")
    args = parser.parse_args()
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = collect()
    path.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"source":"ESPN_PUBLIC_REFERENCE_ONLY",
                      "leagues":list(report["leagues"]),
                      "available":sum(x["status"] == "ESPN_SCOREBOARD_OBSERVED"
                                      for x in report["leagues"].values()),
                      "market_reference_records":sum(x["line_reference_count"] or 0
                                                    for x in report["leagues"].values()),
                      "certified_ev":0}, sort_keys=True))


if __name__ == "__main__":
    main()
