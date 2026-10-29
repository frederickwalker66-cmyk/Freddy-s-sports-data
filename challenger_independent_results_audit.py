"""Secondary published-outcome cross-check for NBA and MLB (research only).

These observations were retrieved after games. They do not establish when any
pregame feature was available or promote rows to Challenger training.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from challenger_research_features import validated
from historical_outcomes import parse_time

SOURCES = {
    "mlb": "https://statsapi.mlb.com/api/v1/schedule",
    "nba": "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
}
MAX_BYTES = 12_000_000


def clean_name(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def evidence_request(league, rows, fetcher=None):
    if league not in SOURCES:
        raise ValueError("only NBA and MLB supported")
    if not rows:
        raise ValueError("no records to audit")
    starts = [parse_time(row["event_start_utc"]) for row in rows]
    if league == "mlb":
        # Dates may shift at UTC boundary; buffer by one day.
        from datetime import timedelta
        start = (min(starts) - timedelta(days=1)).date().isoformat()
        end = (max(starts) + timedelta(days=1)).date().isoformat()
        url = SOURCES[league] + "?" + urlencode({"sportId": 1, "startDate": start, "endDate": end})
    else:
        url = SOURCES[league]
    fetcher = fetcher or fetch_json
    return fetcher(url), url


def fetch_json(url):
    req = Request(url, headers={"User-Agent": "FreddysPicks-IndependentOutcomeResearch/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("independent evidence too large")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("unexpected independent evidence")
    return obj


def score(val):
    if type(val) is int and 0 <= val <= 999:
        return val
    if isinstance(val, str) and val.isdecimal() and int(val) <= 999:
        return int(val)
    raise ValueError("missing/invalid final score")


def independent_games(league, data):
    if not isinstance(data, dict):
        raise ValueError("invalid second source")
    result = []
    if league == "mlb":
        if not isinstance(data.get("dates"), list):
            raise ValueError("invalid MLB dates")
        for day in data["dates"]:
            for game in day.get("games", []):
                if game.get("status", {}).get("abstractGameState") != "Final":
                    continue
                try:
                    sides = game["teams"]
                    home, away = sides["home"], sides["away"]
                    result.append({"id": str(game["gamePk"]), "start": parse_time(game["gameDate"]),
                                   "home_name": clean_name(home["team"]["name"]),
                                   "away_name": clean_name(away["team"]["name"]),
                                   "home_score": score(home["score"]), "away_score": score(away["score"])})
                except (KeyError, ValueError, TypeError):
                    continue
    elif league == "nba":
        dates = data.get("leagueSchedule", {}).get("gameDates")
        if not isinstance(dates, list):
            raise ValueError("invalid NBA schedule")
        for day in dates:
            for game in day.get("games", []):
                if game.get("gameStatus") != 3:
                    continue
                try:
                    home, away = game["homeTeam"], game["awayTeam"]
                    result.append({"id": str(game["gameId"]), "start": parse_time(game["gameDateTimeUTC"]),
                                   "home_name": clean_name(home["teamCity"] + " " + home["teamName"]),
                                   "away_name": clean_name(away["teamCity"] + " " + away["teamName"]),
                                   "home_score": score(home["score"]), "away_score": score(away["score"])})
                except (KeyError, ValueError, TypeError):
                    continue
    else:
        raise ValueError("unsupported league")
    return result


def audit(rows, candidates, league, data, source_url, observed_utc=None):
    if league not in SOURCES:
        raise ValueError("unsupported league")
    if not isinstance(candidates, list):
        raise ValueError("invalid candidate file")
    keys = set()
    for row in rows:
        validated(row)
        if row["league"] != league:
            raise ValueError("mixed-league results")
        key = row["espn_event_id"]
        if key in keys:
            raise ValueError("duplicate result")
        keys.add(key)
    for candidate in candidates:
        if (candidate.get("league") != league or candidate.get("event_id") not in keys
                or candidate.get("qualified_for_challenger_backtest") is not False
                or candidate.get("bet_ready") is not False):
            raise ValueError("invalid/unquarantined candidate")
    games = independent_games(league, data)
    observed = observed_utc or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ValueError("evidence time must be timezone-aware")
    checked = []
    for row in rows:
        start = parse_time(row["event_start_utc"])
        # Match team, start time and uniqueness BEFORE comparing final scores.
        matches = [g for g in games if
                   g["home_name"] == clean_name(row["home_team"]) and
                   g["away_name"] == clean_name(row["away_team"]) and
                   abs((g["start"] - start).total_seconds()) <= 6 * 3600]
        if len(matches) == 0:
            status, independent_id = "no_unambiguous_secondary_match", None
        elif len(matches) > 1:
            status, independent_id = "ambiguous_secondary_match", None
        else:
            g = matches[0]
            independent_id = g["id"]
            status = ("published_result_cross_checked" if
                      (g["home_score"], g["away_score"]) == (row["home_score"], row["away_score"])
                      else "secondary_score_disagreement")
        checked.append({"league": league, "espn_event_id": row["espn_event_id"],
                        "secondary_event_id": independent_id, "secondary_source_url": source_url,
                        "secondary_source_retrieved_at_utc": observed.isoformat(),
                        "result_check_status": status, "official_league_adjudication_certified": False,
                        "historical_pregame_availability_verified": False,
                        "qualified_for_challenger_backtest": False, "bet_ready": False,
                        "champion_001_modified": False})
    counts = Counter(x["result_check_status"] for x in checked)
    report = {"stage": "challenger_secondary_published_results_research_only", "league": league,
              "primary_published_results": len(rows), "secondary_published_results": len(games),
              "candidate_rows_still_quarantined": len(candidates), "outcome_cross_checks": dict(counts),
              "secondary_source_url": source_url, "secondary_source_retrieved_at_utc": observed.isoformat(),
              "verified_pregame_training_examples": 0, "certified_champion_001_predictions": 0,
              "certified_challenger_001_predictions": 0, "bet_ready_selections": 0,
              "automated_bets_placed": 0, "champion_001_modified": False,
              "warning": "Secondary score agreement is NOT verified pregame feature availability or model training evidence. Current source retrieval cannot establish historical as-of timestamps."}
    return checked, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--league", required=True, choices=sorted(SOURCES))
    p.add_argument("--results", required=True)
    p.add_argument("--candidates", required=True)
    p.add_argument("--output-dir", default="challenger_secondary_audit")
    args = p.parse_args(argv)
    rows = [json.loads(x) for x in Path(args.results).read_text().splitlines() if x.strip()]
    candidates = [json.loads(x) for x in Path(args.candidates).read_text().splitlines() if x.strip()]
    # Source failure does not authorize promotions; record the blocker.
    try:
        payload, url = evidence_request(args.league, rows)
        checked, report = audit(rows, candidates, args.league, payload, url)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        checked = []
        report = {"stage": "challenger_secondary_published_results_research_only",
                  "league": args.league, "status": "blocked_secondary_source_unavailable_or_invalid",
                  "error_type": type(exc).__name__, "verified_pregame_training_examples": 0,
                  "certified_champion_001_predictions": 0, "certified_challenger_001_predictions": 0,
                  "bet_ready_selections": 0, "automated_bets_placed": 0,
                  "champion_001_modified": False}
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "secondary_result_checks.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in checked))
    (folder / "secondary_result_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
