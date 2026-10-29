"""Quarantined pregame feature candidates from historical published scores.

No pregame publication time is independently proven. The fixed 48-hour delay
after a game's start is an ASSUMPTION, not a verified settlement time. These
rows are intentionally incompatible with the certified training input and may
not create real-money recommendations or alter frozen Champion-001.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from historical_outcomes import LEAGUES, parse_time
from challenger_elo_walkforward import (
    BINARY_LEAGUES, K, SETTLEMENT_LAG_HOURS,
    pregame_probability, validate_game,
)


def validate_published_source(row):
    league, start, event, home, away, outcome = validate_game(row)
    url = row.get("source_url")
    if not isinstance(url, str):
        raise ValueError("missing outcome source")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("outcome source must be HTTPS")
    retrieval = parse_time(row.get("retrieved_at_utc"))
    if retrieval <= start:
        raise ValueError("published score retrieval must follow start")
    if row.get("provider_event_id_crosswalk_verified") is not False:
        raise ValueError("crosswalk was represented as verified")
    return league, start, event, home, away, outcome


def build_candidates(rows, lag_hours=SETTLEMENT_LAG_HOURS):
    if type(lag_hours) is not int or lag_hours < 48:
        raise ValueError("assumed results embargo must be at least 48 hours")
    games = defaultdict(list)
    seen = set()
    for row in rows:
        lg, start, eid, home, away, outcome = validate_published_source(row)
        identity = (lg, eid)
        if identity in seen:
            raise ValueError("duplicate historical event")
        seen.add(identity)
        games[lg].append((start, eid, home, away, outcome, row))

    candidates, by_league = [], {}
    lag = timedelta(hours=lag_hours)
    for league in sorted(LEAGUES):
        events = sorted(games[league], key=lambda x: (x[0], x[1]))
        if league not in BINARY_LEAGUES:
            by_league[league] = {"published_games": len(events), "candidate_rows": 0,
                                 "status": "three_way_market_not_supported"}
            continue
        ratings = defaultdict(lambda: 1500.0)
        prior = defaultdict(lambda: [0, 0])  # number of games, number of wins
        pending = []
        excluded_ties = 0
        for start, eid, home, away, outcome, source in events:
            # A published final from another game cannot change these pregame
            # features until at least 48 hours after that earlier game's start.
            ready = sorted((x for x in pending if x[0] <= start),
                           key=lambda x: (x[0], x[1]))
            pending = [x for x in pending if x[0] > start]
            for _, _, old_home, old_away, y, old_p in ready:
                change = K * (y - old_p)
                ratings[old_home] += change
                ratings[old_away] -= change
                prior[old_home][0] += 1
                prior[old_away][0] += 1
                prior[old_home][1] += y
                prior[old_away][1] += 1 - y

            if outcome is None:
                excluded_ties += 1
                continue
            home_n, home_w = prior[home]
            away_n, away_w = prior[away]
            p = pregame_probability(ratings[home], ratings[away])
            candidates.append({
                "record_type": "challenger_pregame_candidate_not_training_ready",
                "league": league, "event_id": eid,
                "start_utc": start.isoformat(),
                "home_espn_team_id": home, "away_espn_team_id": away,
                "selection_type": "home", "market_type": "moneyline",
                "published_home_win_result": outcome,
                "published_result_source_url": source["source_url"],
                "published_result_retrieved_at_utc": source["retrieved_at_utc"],
                "features": {
                    "pregame_elo_home_minus_away": round(ratings[home] - ratings[away], 6),
                    "pregame_home_prior_games": home_n,
                    "pregame_away_prior_games": away_n,
                    "pregame_home_prior_win_rate": round((home_w + 1) / (home_n + 2), 6),
                    "pregame_away_prior_win_rate": round((away_w + 1) / (away_n + 2), 6),
                },
                "assumed_result_settlement_delay_hours": lag_hours,
                "historical_final_publication_time_verified": False,
                "historical_feature_availability_verified": False,
                "official_outcome_verified": False,
                "draftkings_checkout_price_verified": False,
                "player_availability_verified": False,
                "training_eligible": False, "bet_ready": False,
                "champion_001_modified": False,
            })
            pending.append((start + lag, eid, home, away, outcome, p))

        by_league[league] = {
            "published_games": len(events),
            "candidate_rows": len(events) - excluded_ties,
            "excluded_ties": excluded_ties,
            "status": "quarantined_awaiting_provenance_audit",
        }
    candidates.sort(key=lambda r: (r["start_utc"], r["league"], r["event_id"]))
    report = {
        "stage": "challenger_001_pregame_candidates_research_only",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "published_games_seen": sum(map(len, games.values())),
        "candidate_rows": len(candidates),
        "verified_training_examples": 0,
        "assumed_result_settlement_delay_hours": lag_hours,
        "by_league": by_league,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "next_required": [
            "independently audit event identity and historical outcomes",
            "verify historical pregame feature as-of timestamps and source provenance",
            "add reliable pregame injuries and lineup information",
            "assemble multi-season training and multiple forward holdout windows",
            "confirm current DraftKings checkout odds before any betting evaluation",
        ],
        "warning": "Candidates are NOT the historical_results.jsonl accepted by the backtest. Published scores and an assumed 48-hour delay do not prove pregame availability. No calibration, positive expected value, or betting readiness established.",
    }
    return candidates, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    p.add_argument("--output-dir", default="challenger_history")
    args = p.parse_args(argv)
    rows = [json.loads(s) for s in Path(args.results).read_text(encoding="utf8").splitlines()
            if s.strip()]
    candidates, report = build_candidates(rows)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "feature_candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates), encoding="utf8")
    (folder / "feature_coverage.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
