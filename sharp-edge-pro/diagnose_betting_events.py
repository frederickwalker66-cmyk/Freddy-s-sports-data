"""Read-only HTTP status diagnostic for the SportsDataIO NBA betting-events endpoint.

Never prints provider response bodies, headers, URL query strings or credentials.
An HTTP response alone does not validate odds, subscription authenticity or bets.
"""
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

def main():
    key = os.getenv("SPORTSDATAIO_ODDS_API_KEY") or os.getenv("SPORTSDATAIO")
    if not key:
        print("HOLD: odds credential unavailable")
        return 1
    day = datetime.now(timezone.utc).date().isoformat()
    url = "https://api.sportsdata.io/v3/nba/odds/json/BettingEventsByDate/" + day
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": key, "Accept": "application/json",
        "User-Agent": "FreddysPicksResearch/1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            print("betting_events_http_status:", response.status)
            print("betting_events_result: RESPONSE_RECEIVED_CONTENT_UNVERIFIED")
    except urllib.error.HTTPError as exc:
        print("betting_events_http_status:", exc.code)
        print("betting_events_result: HOLD_HTTP_ERROR")
    except (urllib.error.URLError, TimeoutError, OSError):
        print("betting_events_result: HOLD_TRANSPORT_ERROR")
    print("certified_take_count: 0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
