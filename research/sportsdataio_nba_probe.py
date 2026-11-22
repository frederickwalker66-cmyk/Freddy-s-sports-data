"""SportsDataIO NBA documented endpoint probe, credentials from environment only.

Authenticated HTTPS transport proves an API response, NOT DraftKings identity,
quote freshness, lineup accuracy, or certified positive-EV forecasts.
"""
import argparse
import json
import os
from datetime import date
from pathlib import Path

from research.trusted_provider_gateway import SourceUnavailable, fetch_provider_json
import urllib.error

HOST = "api.sportsdata.io"
BASE = "https://" + HOST + "/v3/nba"
ENDPOINTS = {
    "pregame_odds": "/odds/json/GameOddsByDate/{date}",
    "betting_events": "/odds/json/BettingEventsByDate/{date}",
    "players": "/scores/json/Players",
    "injured_players": "/projections/json/InjuredPlayers",
}


def schema_shape(records, *, max_fields=40):
    """Field-name-only structural sample; never emit licensed record values."""
    if not isinstance(records, list) or not records:
        return {"record_type": "empty_or_invalid", "field_names": []}
    first = next((record for record in records if isinstance(record, dict)), None)
    if first is None:
        return {"record_type": type(records[0]).__name__, "field_names": []}
    return {"record_type": "object", "field_names": sorted(
        key for key in first if isinstance(key, str))[:max_fields]}


def probe(*, day=None, env=None, fetch=fetch_provider_json):
    env = os.environ if env is None else env
    day = day or date.today().isoformat()
    try:
        parsed_day = date.fromisoformat(day)
        if parsed_day.isoformat() != day:
            raise ValueError("noncanonical_iso_date")
    except ValueError as exc:
        raise ValueError("invalid_iso_date") from exc
    # Never silently substitute a key from another account/provider.
    odds_key = env.get("SPORTSDATAIO_ODDS_API_KEY") or env.get("FREDDY_ODDS_API_KEY")
    player_key = env.get("SPORTSDATAIO_NBA_API_KEY") or env.get("FREDDY_ROSTER_INJURY_API_KEY")
    results = {}
    for name, path in ENDPOINTS.items():
        key = odds_key if name in ("pregame_odds", "betting_events") else player_key
        if not key:
            results[name] = {"status": "HOLD_API_KEY_NOT_CONFIGURED"}
            continue
        url = BASE + path.replace("{date}", day)
        try:
            response = fetch(url, api_key=key, allowed_host=HOST)
            payload = response["payload"]
            if not isinstance(payload, list):
                results[name] = {"status": "HOLD_UNEXPECTED_PROVIDER_SCHEMA"}
                continue
            results[name] = {
                "status": ("RECEIVED_PROVIDER_RESPONSE_UNVERIFIED_MARKETS"
                           if payload else "HOLD_EMPTY_PROVIDER_RESPONSE"),
                "retrieved_at": response["retrieved_at"],
                "record_count": len(payload),
                "schema_shape": schema_shape(payload),
                "transport_authenticated": True,
                "draftkings_selection_verified": False,
                "player_team_and_injury_crosschecked": False,
            }
        except SourceUnavailable as exc:
            # Do not print exception messages: they can include URLs or response details.
            cause = exc.__cause__
            if isinstance(cause, urllib.error.HTTPError):
                results[name] = {"status": "HOLD_PROVIDER_HTTP_ERROR",
                                 "http_status": int(cause.code)}
            elif isinstance(cause, ValueError):
                results[name] = {"status": "HOLD_PROVIDER_INVALID_JSON"}
            else:
                results[name] = {"status": "HOLD_PROVIDER_TRANSPORT_ERROR",
                                 "reason_type": type(cause).__name__ if cause else "SourceUnavailable"}
        except (KeyError, TypeError, ValueError) as exc:
            results[name] = {"status": "HOLD_PROVIDER_RESPONSE_ERROR",
                             "reason_type": type(exc).__name__}
    coverage = {name: {"response_received": item["status"] in (
                    "RECEIVED_PROVIDER_RESPONSE_UNVERIFIED_MARKETS", "HOLD_EMPTY_PROVIDER_RESPONSE"),
                    "records_present": item.get("record_count", 0) > 0,
                    "record_count": item.get("record_count", 0)}
                for name, item in results.items()}
    return {"provider": "SportsDataIO", "sport": "nba", "date": day,
            "coverage": coverage, "draftkings_markets_verified": 0,
            "roster_identities_independently_verified": 0,
            "endpoints": results, "certified_take_count": 0, "decision": "HOLD",
            "note": "DraftKings book mapping, props, independent roster corroboration, original Champion inference, and calibrated EV remain required."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default="SPORTSDATAIO_NBA_READINESS.json")
    args = parser.parse_args()
    result = probe(day=args.date)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"],
                      "endpoint_statuses": {k:v["status"] for k,v in result["endpoints"].items()},
                      "output": str(out)}))


if __name__ == "__main__":
    main()
