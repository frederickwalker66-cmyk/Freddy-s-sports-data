"""SportsDataIO game-score evidence collector. Research only; no betting or training."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls")
# SportsDataIO subscriptions are product-specific. No guessed UEFA endpoint.
PATHS = {
    "nba": "/v3/nba/scores/json/GamesByDate/{date}",
    "nfl": "/v3/nfl/scores/json/ScoresByDate/{date}",
    "mlb": "/v3/mlb/scores/json/GamesByDate/{date}",
    "nhl": "/v3/nhl/scores/json/GamesByDate/{date}",
    "ncaaf": "/v3/cfb/scores/json/GamesByDate/{date}",
    "ncaab": "/v3/cbb/scores/json/GamesByDate/{date}",
    "mls": "/v4/soccer/scores/json/GamesByDate/MLS/{date}",
}

def collect(key, leagues, date, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    report = {"provider": "sportsdataio", "date_utc": date, "research_only": True,
              "qualified_training_examples": 0, "certified_predictions": 0,
              "bet_ready_selections": 0, "champion_001_modified": False, "leagues": {}}
    failed = False
    for league in leagues:
        path = PATHS[league].format(date=date)
        url = "https://api.sportsdata.io" + path
        request = Request(url, headers={"Ocp-Apim-Subscription-Key": key, "Accept": "application/json"})
        try:
            started = datetime.now(timezone.utc).isoformat()
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            finished = datetime.now(timezone.utc).isoformat()
            if not isinstance(data, list):
                raise ValueError("non-list provider response")
            file = outdir / f"{league}_{date}.jsonl"
            with file.open("w", encoding="utf-8") as handle:
                for item in data:
                    if not isinstance(item, dict):
                        raise ValueError("non-object game row")
                    record = {"source": "sportsdataio", "league": league,
                              "requested_date_utc": date, "request_started_utc": started,
                              "received_at_utc": finished, "provider_payload": item,
                              "qualified_for_challenger_backtest": False,
                              "certified_prediction": False, "champion_001_modified": False}
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
            report["leagues"][league] = {"status": "success", "records": len(data), "file": file.name}
        except HTTPError as exc:
            failed = True
            report["leagues"][league] = {"status": "error", "error": f"HTTP {exc.code} (subscription/endpoint/access)"}
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            failed = True
            report["leagues"][league] = {"status": "error", "error": type(exc).__name__}
    (outdir / "collection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--leagues", default="nba")
    p.add_argument("--date", default=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat())
    p.add_argument("--output-dir", default="sportsdataio_evidence")
    args = p.parse_args()
    leagues = [s.strip().lower() for s in args.leagues.split(",")]
    if not leagues or any(s not in LEAGUES for s in leagues):
        p.error("Unsupported league; supported: " + ",".join(LEAGUES))
    key = os.environ.get("SPORTSDATAIO_API_KEY")
    if not key:
        p.error("Missing Sportsdataio GitHub Actions secret")
    return collect(key, leagues, args.date, Path(args.output_dir))

if __name__ == "__main__":
    raise SystemExit(main())
