"""Prospective, research-only NBA Elo forecasts from actual prior published results.

Historical outcomes are delayed by a conservative 48h assumption; this does
not authenticate their original publication. Never certify or label as EV.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from challenger_elo_walkforward import K, HOME_ADV, SETTLEMENT_LAG_HOURS, pregame_probability, validate_game

def forecast(history, upcoming, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC-aware clock required")
    now = now.astimezone(timezone.utc)
    ratings = {}
    seen = set()
    settled = []
    for row in history:
        league, start, eid, home, away, outcome = validate_game(row)
        if league != "nba" or outcome is None:
            continue
        if eid in seen:
            raise ValueError("duplicate historical event")
        seen.add(eid)
        if start + timedelta(hours=SETTLEMENT_LAG_HOURS) <= now:
            settled.append((start, eid, home, away, outcome))
    settled.sort()
    for start, eid, home, away, outcome in settled:
        a, b = ratings.get(home, 1500.), ratings.get(away, 1500.)
        p = pregame_probability(a, b)
        ratings[home] = a + K * (outcome - p)
        ratings[away] = b - K * (outcome - p)
    output = []
    for event in upcoming:
        if not isinstance(event, dict):
            raise ValueError("upcoming event must be object")
        eid, home, away = (event.get(k) for k in ("event_id", "home_team_espn_id", "away_team_espn_id"))
        if any(not isinstance(v, str) or not v.strip() for v in (eid, home, away)) or home == away or eid in seen:
            raise ValueError("invalid or historical event identity")
        start = datetime.fromisoformat(event["start_utc"].replace("Z", "+00:00"))
        if start.tzinfo is None or start.astimezone(timezone.utc) <= now:
            raise ValueError("event must be genuinely future")
        if not event.get("source_url", "").startswith("https://"):
            raise ValueError("upcoming event source URL required")
        p = pregame_probability(ratings.get(home, 1500.), ratings.get(away, 1500.))
        output.append({"event_id": eid, "start_utc": start.astimezone(timezone.utc).isoformat(),
                       "research_probability_home_win": round(p, 6),
                       "research_probability_away_win": round(1-p, 6),
                       "model": "Challenger independent uncalibrated Elo baseline",
                       "historical_games_used": len(settled), "source_url": event["source_url"],
                       "prediction_created_at_utc": now.isoformat(),
                       "decision": "HOLD", "certified": False, "bet_ready": False})
    return {"forecasts": output, "historical_games_used": len(settled),
            "result_publication_time_independently_verified": False,
            "elo_calibrated": False, "certified_take_count": 0,
            "champion_001_modified": False,
            "warning": "Research-only Elo baseline; historical result availability assumes a 48h delay. No validated odds edge or independent certification."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--upcoming", required=True)
    parser.add_argument("--output", default="nba_elo_research_forecasts.json")
    args = parser.parse_args()
    rows = [json.loads(s) for s in Path(args.history).read_text().splitlines() if s.strip()]
    upcoming = json.loads(Path(args.upcoming).read_text())
    result = forecast(rows, upcoming)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"forecast_count": len(result["forecasts"]), "certified_take_count": 0}))

if __name__ == "__main__":
    main()
