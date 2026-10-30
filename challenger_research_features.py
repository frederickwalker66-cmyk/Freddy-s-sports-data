"""Retrospective, non-certified Challenger-001 pregame form research.

Derives lagged rolling team form from historical ESPN final scores ONLY.
The 48-hour availability delay is ASSUMED, not documented publication time.
Do not feed the output into certified training or market recommendations.
No Champion-001 code, sportsbook prices, or player availability is touched.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from historical_outcomes import LEAGUES, parse_time

BINARY_LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab")
LAG_HOURS = 48
WINDOW = 5
MIN_PRIOR_GAMES = 3


def validated(row):
    if not isinstance(row, dict):
        raise ValueError("historical row must be an object")
    if (row.get("record_type") != "historical_completed_game_research"
            or row.get("outcome_source") != "espn_public_scoreboard"
            or row.get("official_league_result_verified") is not False
            or row.get("champion_001_modified") is not False
            or row.get("league") not in LEAGUES):
        raise ValueError("unsupported or misrepresented historical provenance")
    if row.get("league") == "nba" and row.get("season_type") != 2:
        raise ValueError("NBA regular-season evidence required")
    u = urlparse(row.get("source_url", ""))
    if u.scheme != "https" or u.hostname != "site.api.espn.com":
        raise ValueError("missing ESPN source provenance")
    start = parse_time(row.get("event_start_utc"))
    retrieval = parse_time(row.get("retrieved_at_utc"))
    if retrieval <= start:
        raise ValueError("historical source was not retrieved after the event began")
    home, away, eid = (row.get(k) for k in (
        "home_team_espn_id", "away_team_espn_id", "espn_event_id"))
    if (any(not isinstance(x, str) or not x.strip() for x in (home, away, eid))
            or home == away):
        raise ValueError("invalid team or event identity")
    a, b = row.get("home_score"), row.get("away_score")
    if (type(a) is not int or type(b) is not int
            or min(a, b) < 0 or max(a, b) > 999):
        raise ValueError("invalid final scores")
    result = "home" if a > b else "away" if b > a else "draw"
    if row.get("result") != result:
        raise ValueError("result contradicts scores")
    return start


def form(history, cutoff):
    # Results from events inside the embargo may not influence these features.
    prior = [g for g in history if g[0] <= cutoff]
    last = prior[-WINDOW:]
    if len(last) < MIN_PRIOR_GAMES:
        return None
    return {
        "games": len(last),
        "win_rate": sum(g[2] for g in last) / len(last),
        "margin_avg": sum(g[3] for g in last) / len(last),
        "source_event_ids": [g[1] for g in last],
    }


def build_candidates(rows):
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        start = validated(row)
        identity = (row["league"], row["espn_event_id"])
        if identity in seen:
            raise ValueError("duplicate historical event")
        seen.add(identity)
        groups[row["league"]].append((start, row))
    candidates = []
    by_league = {}
    for league in LEAGUES:
        games = sorted(groups[league], key=lambda item: (
            item[0], item[1]["espn_event_id"]))
        counts = {"historical_games": len(games), "research_candidates": 0,
                  "excluded_no_prior_history": 0, "excluded_draws": 0,
                  "excluded_three_way_market": 0}
        team_history = defaultdict(list)
        for start, row in games:
            if league not in BINARY_LEAGUES:
                counts["excluded_three_way_market"] += 1
                continue
            if row["result"] == "draw":
                counts["excluded_draws"] += 1
                continue
            cutoff = start - timedelta(hours=LAG_HOURS)
            home = row["home_team_espn_id"]
            away = row["away_team_espn_id"]
            fh = form(team_history[home], cutoff)
            fa = form(team_history[away], cutoff)
            if fh is None or fa is None:
                counts["excluded_no_prior_history"] += 1
            else:
                candidates.append({
                    "record_type": "retrospective_challenger_candidate_not_training_ready",
                    "league": league,
                    "event_id": row["espn_event_id"],
                    "event_start_utc": start.isoformat(),
                    "features_cutoff_utc": cutoff.isoformat(),
                    "selection_type": "home",
                    "market_type": "moneyline",
                    "outcome": int(row["result"] == "home"),
                    "features": {
                        "pregame_home_prior_games": fh["games"],
                        "pregame_away_prior_games": fa["games"],
                        "pregame_home_win_rate": round(fh["win_rate"], 6),
                        "pregame_away_win_rate": round(fa["win_rate"], 6),
                        "pregame_home_margin_avg": round(fh["margin_avg"], 6),
                        "pregame_away_margin_avg": round(fa["margin_avg"], 6),
                    },
                    "lagged_result_event_ids": {
                        "home": fh["source_event_ids"],
                        "away": fa["source_event_ids"],
                    },
                    "historical_result_url": row["source_url"],
                    "outcome_publication_time_verified": False,
                    "pregame_feature_availability_verified": False,
                    "pregame_player_availability_verified": False,
                    "historical_odds_snapshot_verified": False,
                    "independent_league_outcome_verified": False,
                    "qualified_for_challenger_backtest": False,
                    "bet_ready": False,
                    "champion_001_modified": False,
                })
                counts["research_candidates"] += 1
            margin = row["home_score"] - row["away_score"]
            # Stored now, but not accessible as a feature until start+48h.
            team_history[home].append((start, row["espn_event_id"], int(margin > 0), margin))
            team_history[away].append((start, row["espn_event_id"], int(margin < 0), -margin))
        by_league[league] = counts
    candidates.sort(key=lambda r: (r["event_start_utc"], r["league"], r["event_id"]))
    report = {
        "mode": "challenger_001_retrospective_feature_research_only",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_games_input": len(rows),
        "research_candidates": len(candidates),
        "assumed_outcome_availability_lag_hours": LAG_HOURS,
        "team_form_window_max_games": WINDOW,
        "minimum_prior_team_games": MIN_PRIOR_GAMES,
        "by_league": by_league,
        "qualified_training_examples": 0,
        "independently_audited_historical_pregame_features": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "Retrospective 48h buffer is an assumption, NOT verified historical "
            "publication time. Scores and features lack true pregame as-of "
            "verification, independent adjudication, and sportsbook quotes. "
            "Do not pass these candidates to the qualified backtest."
        ),
    }
    return candidates, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", default="challenger_history/results.jsonl")
    p.add_argument("--output-dir", default="challenger_history")
    args = p.parse_args(argv)
    source = Path(args.results)
    # Missing source is a hard failure: never synthesize training examples.
    if not source.is_file():
        raise FileNotFoundError(source)
    rows = [json.loads(s) for s in source.read_text(encoding="utf8").splitlines() if s.strip()]
    candidates, report = build_candidates(rows)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "retrospective_candidates.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in candidates),
        encoding="utf8")
    (out / "retrospective_coverage.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
