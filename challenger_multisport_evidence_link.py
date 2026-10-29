"""Link quarantined historical result/feature evidence across eight sports.

This is NOT a backtest, training-file generator, or probability model.  Score
corroboration from another published feed cannot establish what was known
before a game. All linked records remain research-only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from challenger_research_features import validated

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls",
           "uefa_champions_league")
BINARY = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab"))
CHECK_STATUSES = frozenset((
    "published_result_cross_checked", "secondary_score_disagreement",
    "ambiguous_secondary_match", "no_unambiguous_secondary_match",
))
NOT_CERTIFIED = {
    "qualified_training_examples": 0,
    "certified_champion_001_predictions": 0,
    "certified_challenger_001_predictions": 0,
    "bet_ready_selections": 0,
    "automated_bets_placed": 0,
    "champion_001_modified": False,
}
CANDIDATE_UNPROVEN = (
    "outcome_publication_time_verified",
    "pregame_feature_availability_verified",
    "pregame_player_availability_verified",
    "historical_odds_snapshot_verified",
    "independent_league_outcome_verified",
)


def read_jsonl(path):
    if path is None:
        return []
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("required evidence file missing: " + str(source))
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def read_coverage(path):
    if path is None:
        return None
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("required coverage file missing: " + str(source))
    result = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("invalid coverage report")
    return result


def assess(league, results, candidates, checks=None, coverage=None):
    """Cross-reference by provider event ID; never promote research candidates."""
    if league not in LEAGUES:
        raise ValueError("unsupported league")
    if not all(isinstance(items, list) for items in (results, candidates)):
        raise ValueError("results/candidates must be lists")
    checks = [] if checks is None else checks
    if not isinstance(checks, list):
        raise ValueError("secondary checks must be a list")

    primary = {}
    for row in results:
        if not isinstance(row, dict):
            raise ValueError("invalid historical result")
        if row.get("league") != league:
            continue  # shared eight-league historical archive
        validated(row)
        key = row["espn_event_id"]
        if key in primary:
            raise ValueError("duplicate primary event identity")
        primary[key] = row

    second = {}
    for item in checks:
        if not isinstance(item, dict) or item.get("league") != league:
            raise ValueError("mixed or invalid independent checks")
        key = item.get("espn_event_id")
        if key not in primary or key in second:
            raise ValueError("unlinked or duplicate secondary check")
        if (item.get("result_check_status") not in CHECK_STATUSES
                or item.get("qualified_for_challenger_backtest") is not False
                or item.get("bet_ready") is not False
                or item.get("historical_pregame_availability_verified") is not False):
            raise ValueError("invalid or improperly promoted secondary check")
        second[key] = item

    linked = []
    ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid candidate")
        if candidate.get("league") != league:
            continue  # shared eight-league historical archive
        event_id = candidate.get("event_id")
        if event_id not in primary or event_id in ids:
            raise ValueError("unlinked or duplicate research candidate")
        ids.add(event_id)
        if (candidate.get("record_type") !=
                "retrospective_challenger_candidate_not_training_ready"
                or candidate.get("qualified_for_challenger_backtest") is not False
                or candidate.get("bet_ready") is not False
                or candidate.get("champion_001_modified") is not False
                or any(candidate.get(field) is not False
                       for field in CANDIDATE_UNPROVEN)):
            raise ValueError("candidate is not safely quarantined")
        checked = second.get(event_id)
        status = (checked["result_check_status"] if checked
                  else "no_independent_check_archive")
        missing = [
            "independently_proven_historical_pregame_feature_timestamps",
            "verified_original_result_publication_times",
            "historical_pregame_player_availability",
            "timestamped_historical_odds",
            "official_league_result_adjudication",
        ]
        if status != "published_result_cross_checked":
            missing.insert(0, "independent_score_corroboration")
        if league not in BINARY:
            missing.append("three_way_market_specific_model_and_settlement")
        linked.append({
            "league": league,
            "espn_event_id": event_id,
            "event_start_utc": candidate["event_start_utc"],
            "secondary_score_status": status,
            "secondary_source_url": checked.get("secondary_source_url") if checked else None,
            "secondary_source_class": checked.get("secondary_source_class") if checked else None,
            "missing_training_evidence": missing,
            "qualified_for_challenger_backtest": False,
            "bet_ready": False,
            "champion_001_modified": False,
        })

    status_counts = Counter(x["result_check_status"] for x in second.values())
    candidate_counts = Counter(x["secondary_score_status"] for x in linked)
    coverage_complete = None
    coverage_days_failed = None
    if coverage is not None:
        if not isinstance(coverage, dict):
            raise ValueError("invalid coverage")
        if "coverage_complete" in coverage:
            if coverage.get("league") != league:
                raise ValueError("coverage league mismatch")
            coverage_complete = coverage["coverage_complete"] is True
            coverage_days_failed = coverage.get("scoreboard_days_failed")
        else:
            item = coverage.get("by_league", {}).get(league)
            if not isinstance(item, dict):
                raise ValueError("missing league coverage")
            coverage_days_failed = item.get("days_failed")
            coverage_complete = coverage_days_failed == 0

    report = {
        "stage": "eight_league_challenger_evidence_readiness_research_only",
        "league": league,
        "source_outcome_rows": len(primary),
        "research_candidates": len(linked),
        "independent_checks_received": len(second),
        "primary_rows_with_secondary_published_score_agreement":
            status_counts["published_result_cross_checked"],
        "secondary_result_status_counts": dict(sorted(status_counts.items())),
        "candidate_secondary_result_status_counts": dict(sorted(candidate_counts.items())),
        "scoreboard_coverage_complete": coverage_complete,
        "scoreboard_days_failed": coverage_days_failed,
        "historical_pregame_source_publication_verified": 0,
        "historical_injury_asof_verified": 0,
        "historical_odds_asof_verified": 0,
        "independent_official_outcome_adjudication_verified": 0,
        "binary_moneyline_backtest_supported": league in BINARY,
        "missing_evidence_categories": [
            "point_in_time_pregame_features",
            "result_publication_provenance",
            "historical_player_information",
            "time_stamped_historical_odds",
            "official_outcome_adjudication",
        ] + ([] if league in BINARY else ["three_way_market_logic"]),
        **NOT_CERTIFIED,
        "warning": ("Score agreement is retrospective and does not verify historical "
                    "pregame availability. This is not a training file; no observations "
                    "are promoted, no model probabilities or wagers are produced."),
    }
    return linked, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", choices=LEAGUES, required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--checks")
    parser.add_argument("--coverage")
    parser.add_argument("--output-dir", default="challenger_readiness")
    args = parser.parse_args(argv)
    rows, report = assess(args.league, read_jsonl(args.results),
                          read_jsonl(args.candidates), read_jsonl(args.checks),
                          read_coverage(args.coverage))
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "linked_evidence.jsonl").write_text("".join(
        json.dumps(item, sort_keys=True) + "\n" for item in rows), encoding="utf-8")
    (root / "readiness_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
