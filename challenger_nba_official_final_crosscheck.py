"""Cross-check already published NBA outcomes against an NBA-owned schedule.

Research-only, fail-closed evidence comparison. A current NBA schedule response
does not prove historical source publication times, feature as-of provenance,
authenticated source receipts, official bookmaker settlement, or model accuracy.
No SportsGameOdds or paid sportsbook requests, no trained model or wagers.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from challenger_backtest import timestamp
from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, fetch_official_schedule, nba_team_name,
)

MAX_TIME_DIFFERENCE_SECONDS = 30 * 60
RESEARCH_STATUS = "nba_second_source_final_score_agrees_research_only"


def official_final_games(payload):
    """Strict parse of NBA-owned season schedule, including NOT-final games."""
    if not isinstance(payload, dict):
        raise ValueError("untrusted NBA JSON")
    league = payload.get("leagueSchedule")
    if not isinstance(league, dict) or not isinstance(league.get("gameDates"), list):
        raise ValueError("missing NBA leagueSchedule.gameDates")
    if league.get("leagueId") not in (None, "00", "0"):
        raise ValueError("unrecognized NBA league")
    seen = {}
    games = []
    for day in league["gameDates"]:
        if not isinstance(day, dict) or not isinstance(day.get("games"), list):
            raise ValueError("malformed official gameDates")
        for item in day["games"]:
            if not isinstance(item, dict):
                continue
            home = item.get("homeTeam")
            away = item.get("awayTeam")
            if not isinstance(home, dict) or not isinstance(away, dict):
                continue
            game_id = item.get("gameId")
            if not isinstance(game_id, str) or not game_id.isdigit():
                continue
            try:
                home_name = nba_team_name(home["teamCity"] + " " + home["teamName"])
                away_name = nba_team_name(away["teamCity"] + " " + away["teamName"])
                start = timestamp(item["gameDateTimeUTC"])
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            if not home_name or not away_name or home_name == away_name:
                continue
            final = item.get("gameStatus") in (3, "3")
            home_score, away_score = home.get("score"), away.get("score")
            score_ok = (type(home_score) is int and type(away_score) is int
                        and 0 <= home_score <= 999 and 0 <= away_score <= 999
                        and home_score != away_score)
            status = ("official_final" if final and score_ok else
                      "official_final_invalid_score" if final else "not_final")
            entry = {
                "nba_game_id": game_id,
                "home": home_name,
                "away": away_name,
                "start_utc": start,
                "status": status,
                "home_score": home_score if score_ok else None,
                "away_score": away_score if score_ok else None,
            }
            # Conflicting duplicate IDs invalidate the payload, not a random winner.
            if game_id in seen and seen[game_id] != entry:
                raise ValueError("conflicting NBA official game ID")
            if game_id not in seen:
                seen[game_id] = entry
                games.append(entry)
    return games


def review_candidates(candidates, official_payload, observed):
    """Report second-source score agreement without qualifying any training row."""
    if not isinstance(candidates, list) or not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ValueError("candidates and aware retrieval time required")
    observed = observed.astimezone(timezone.utc)
    official = official_final_games(official_payload) if official_payload is not None else None
    counts = Counter()
    records = []
    ids = set()
    for item in candidates:
        if (not isinstance(item, dict) or
            item.get("record_type") != "challenger_nba_history_candidate_review_only" or
            item.get("league") != "nba" or
            item.get("market_type") != "moneyline" or
            item.get("selection_type") != "home" or
            item.get("qualified_for_challenger_backtest") is not False or
            item.get("eligible_to_train_probability_model") is not False or
            item.get("independent_asof_review") is not False or
            item.get("independent_outcome_review") is not False or
            item.get("certified_prediction") is not False or
            item.get("bet_ready") is not False or
            item.get("champion_001_modified") is not False or
            item.get("model_probability") is not None):
            raise ValueError("intake must contain strictly unqualified NBA review candidates")
        event_id = item.get("event_id")
        if not isinstance(event_id, str) or not event_id.isdigit() or event_id in ids:
            raise ValueError("invalid or duplicate ESPN research event ID")
        ids.add(event_id)
        try:
            start = timestamp(item["start_utc"])
            snap = timestamp(item["snapshot_utc"])
            published = timestamp(item["outcome_verified_at_utc"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("candidate timestamps invalid") from None
        if not snap < start < published <= observed:
            raise ValueError("future or temporally inconsistent historical candidate")
        h, a = item.get("home_team"), item.get("away_team")
        scores = item.get("published_score_only")
        if (not isinstance(h, str) or not isinstance(a, str) or not isinstance(scores, dict)
                or type(scores.get("home")) is not int or type(scores.get("away")) is not int
                or scores["home"] == scores["away"] or
                (scores["home"] > scores["away"]) != (item.get("outcome") == 1)):
            raise ValueError("candidate identity or score label mismatch")
        record = {
            "espn_research_event_id": event_id,
            "home_team": h, "away_team": a,
            "espn_published_score": dict(scores),
            "source_checked_at_utc": observed.isoformat(),
            "official_nba_source_url": NBA_SCHEDULE_URL,
            "training_row_qualified": False,
            "independent_feature_asof_verified": False,
            "independent_source_receipt_authenticated": False,
            "independent_bookmaker_settlement_verified": False,
            "certified_prediction": False,
            "bet_ready": False,
            "champion_001_modified": False,
        }
        if official is None:
            state = "nba_official_source_unavailable"
        else:
            match = [g for g in official
                     if g["home"] == nba_team_name(h)
                     and g["away"] == nba_team_name(a)
                     and abs((g["start_utc"] - start).total_seconds()) <=
                        MAX_TIME_DIFFERENCE_SECONDS]
            if len(match) > 1:
                state = "ambiguous_official_game_identity"
            elif not match:
                # Never match purely on names across unbounded historical dates.
                state = "official_nba_game_not_found_or_clock_mismatch"
            else:
                game = match[0]
                record["official_nba_game_id"] = game["nba_game_id"]
                record["official_nba_start_utc"] = game["start_utc"].isoformat()
                if game["status"] != "official_final":
                    state = "official_nba_game_not_final_or_score_unavailable"
                elif (game["home_score"] != scores["home"] or
                      game["away_score"] != scores["away"]):
                    state = "nba_official_final_disagrees_with_espn"
                    record["official_nba_score"] = {
                        "home": game["home_score"], "away": game["away_score"]
                    }
                else:
                    state = RESEARCH_STATUS
                    record["official_nba_score"] = {
                        "home": game["home_score"], "away": game["away_score"]
                    }
        record["crosscheck_status"] = state
        counts[state] += 1
        records.append(record)
    report = {
        "stage": "challenger_nba_official_final_score_crosscheck_research_only",
        "observed_at_utc": observed.isoformat(),
        "official_nba_source_url": NBA_SCHEDULE_URL,
        "official_source_available": official is not None,
        "official_games_parsed": len(official) if official is not None else 0,
        "nba_review_candidates_checked": len(records),
        "second_source_published_final_score_agreements": counts[RESEARCH_STATUS],
        "by_status": dict(sorted(counts.items())),
        "independently_authenticated_feature_snapshots": 0,
        "independently_qualified_training_records": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "trained_models_created": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "Published NBA-owned score agreement is a second-source outcome "
            "comparison only. No proof of original as-of feature publication, "
            "receipt authenticity, bookmaker settlement or qualified training. "
            "Never turn this output into historical_results.jsonl."
        ),
    }
    return records, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", default="prospective_validation")
    args = parser.parse_args(argv)
    src = Path(args.candidates)
    if not src.is_file():
        raise FileNotFoundError("missing NBA history review candidates")
    candidates = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x.strip()]
    observed = datetime.now(timezone.utc)
    source_error = None
    payload = None
    if candidates:
        try:
            payload = fetch_official_schedule(NBA_SCHEDULE_URL)
            official_final_games(payload)
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            payload = None
            source_error = type(exc).__name__
    rows, report = review_candidates(candidates, payload, observed)
    report["official_source_failure_type"] = source_error
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "nba_official_final_crosscheck.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows), encoding="utf-8")
    (root / "nba_official_final_crosscheck_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
