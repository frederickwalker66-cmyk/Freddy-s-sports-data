"""Link genuine pre-tipoff prospective snapshots to later ESPN final scores.

RESEARCH ONLY: this is a published-outcome linkage, not independent adjudication,
certified training data, calibrated model probabilities or wagering advice.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

ALLOWED = {"nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league"}


def instant(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return result.astimezone(timezone.utc)


def norm(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().split())


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def validate_snapshot(row, now):
    """Never accept an observation captured at or after tipoff."""
    if not isinstance(row, dict):
        raise ValueError("invalid snapshot")
    if (row.get("record_type") != "prospective_evidence_snapshot_research_only"
            or row.get("league") not in ALLOWED or not str(row.get("espn_schedule_event_id", "")).isdigit()
            or row.get("champion_001_modified") is not False
            or row.get("qualified_for_challenger_backtest") is not False
            or row.get("bet_ready") is not False
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None):
        raise ValueError("snapshot not quarantined or invalid")
    source = urlparse(row.get("schedule_source_url") or "")
    if source.scheme != "https" or source.hostname != "site.api.espn.com":
        raise ValueError("unexpected schedule source")
    start = instant(row["event_start_utc"])
    captured = instant(row["snapshot_completed_at_utc"])
    observed = instant(row["schedule_observed_at_utc"])
    if not (observed <= captured < start and captured <= now):
        raise ValueError("not actually pregame")
    if not norm(row.get("home_team")) or not norm(row.get("away_team")):
        raise ValueError("missing teams")
    for q in row.get("odds_observations", []):
        if (q.get("direct_draftkings_checkout_verified") is not False
                or instant(q["received_at_utc"]) >= start
                or instant(q["received_at_utc"]) > captured):
            raise ValueError("unverified or after-start price")
    return (row["league"], str(row["espn_schedule_event_id"])), captured


def validated_outcome(row, now):
    if (not isinstance(row, dict) or row.get("record_type") != "historical_completed_game_research"
            or row.get("outcome_source") != "espn_public_scoreboard"
            or row.get("league") not in ALLOWED or not str(row.get("espn_event_id", "")).isdigit()
            or row.get("champion_001_modified") is not False):
        raise ValueError("invalid published outcome")
    source = urlparse(row.get("source_url") or "")
    if source.scheme != "https" or source.hostname != "site.api.espn.com":
        raise ValueError("unknown published outcome source")
    start, observed = instant(row["event_start_utc"]), instant(row["retrieved_at_utc"])
    if not (start < observed <= now):
        raise ValueError("result not demonstrably observed after game start")
    h, a = row.get("home_score"), row.get("away_score")
    if type(h) is not int or type(a) is not int or not 0 <= h <= 999 or not 0 <= a <= 999:
        raise ValueError("invalid final score")
    result = "home" if h > a else "away" if a > h else "draw"
    if result != row.get("result"):
        raise ValueError("outcome/result disagree")
    return (row["league"], str(row["espn_event_id"]))


def reconcile(snapshots, outcomes, now):
    """Earliest valid prospective capture per event; reject ambiguous final records."""
    if now.tzinfo is None:
        raise ValueError("now requires timezone")
    selected = {}
    rejected = Counter()
    for row in snapshots:
        try:
            key, captured = validate_snapshot(row, now)
        except (KeyError, ValueError, TypeError, OverflowError):
            rejected["invalid_pregame_snapshot"] += 1
            continue
        if key not in selected or captured < selected[key][0]:
            selected[key] = captured, row
    result_by_key = defaultdict(list)
    for row in outcomes:
        try:
            key = validated_outcome(row, now)
            result_by_key[key].append(row)
        except (KeyError, ValueError, TypeError, OverflowError):
            rejected["invalid_published_outcome"] += 1
    linked = []
    for (league, event_id), (captured, snap) in sorted(selected.items()):
        final_rows = result_by_key.get((league, event_id), [])
        status = "awaiting_published_final" if not final_rows else "ambiguous_or_mismatched_published_final"
        final_score = None
        if final_rows:
            # Repeated ESPN archives are normal. Accept repeated *identical*
            # published finals, but never silently pick among conflicting scores
            # or team identities. No sportsbook or model data is involved.
            signature = {(norm(g["home_team"]), norm(g["away_team"]),
                          g["home_score"], g["away_score"], g["result"]) for g in final_rows}
            same_teams = all(
                norm(g["home_team"]) == norm(snap["home_team"]) and
                norm(g["away_team"]) == norm(snap["away_team"]) for g in final_rows)
            starts_agree = all(
                abs((instant(g["event_start_utc"]) -
                     instant(snap["event_start_utc"])).total_seconds()) <= 1800
                for g in final_rows)
            later_final = all(instant(g["retrieved_at_utc"]) > captured for g in final_rows)
            if len(signature) == 1 and same_teams and starts_agree and later_final:
                final = min(final_rows, key=lambda g: instant(g["retrieved_at_utc"]))
                status = "linked_to_espn_published_final_only"
                final_score = {"home": final["home_score"], "away": final["away_score"],
                               "result": final["result"],
                               "published_retrieved_at_utc": final["retrieved_at_utc"],
                               "source_url": final["source_url"],
                               "consistent_archive_observations": len(final_rows)}
        linked.append({
            "league": league, "espn_event_id": event_id, "status": status,
            "snapshot_completed_at_utc": captured.isoformat(),
            "event_start_utc": snap["event_start_utc"],
            "home_team": snap["home_team"], "away_team": snap["away_team"],
            "both_teams_form_available_at_capture": snap.get("team_form_available_for_both_teams") is True,
            "archived_research_odds_count": len(snap.get("odds_observations", [])),
            "published_outcome": final_score,
            "independent_league_outcome_verified": False,
            "model_prediction_at_capture": None,
            "qualified_for_challenger_backtest": False,
            "bet_ready": False, "champion_001_modified": False})
    counts = Counter(x["status"] for x in linked)
    report = {
        "stage": "challenger_prospective_outcome_linkage_research_only",
        "snapshot_rows_seen": len(snapshots), "unique_valid_pregame_events": len(selected),
        "outcome_rows_seen": len(outcomes), "by_status": dict(sorted(counts.items())),
        "events_with_both_team_features": sum(x["both_teams_form_available_at_capture"] for x in linked),
        "events_with_archived_research_odds": sum(x["archived_research_odds_count"] > 0 for x in linked),
        "rejected_rows": dict(sorted(rejected.items())),
        "independently_adjudicated_outcomes": 0, "verified_historical_training_examples": 0,
        "certified_challenger_001_predictions": 0, "certified_champion_001_predictions": 0,
        "model_accuracy_established": False, "bet_ready_selections": 0,
        "automated_bets_placed": 0, "champion_001_modified": False,
        "warning": "ESPN result linkage is not independent league adjudication. No verified model forecasts are present. Never convert this artifact to historical_results.jsonl."}
    return linked, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-root", required=True)
    p.add_argument("--outcomes", help="Optional freshly collected published outcomes JSONL")
    p.add_argument("--outcomes-root", help="Optional archived historical results folder")
    p.add_argument("--output-dir", default="prospective_validation")
    args = p.parse_args()
    root = Path(args.snapshot_root)
    paths = sorted(root.rglob("prospective_event_evidence.jsonl"))
    if not paths:
        raise SystemExit("No archived point-in-time snapshots found")
    rows = []
    for path in paths:
        rows.extend(load_jsonl(path))
    outcome_paths = []
    if args.outcomes_root:
        outcome_paths.extend(sorted(
            Path(args.outcomes_root).rglob("historical_published_results.jsonl")))
    if args.outcomes:
        outcome_paths.append(Path(args.outcomes))
    if not outcome_paths:
        raise SystemExit("No published result inputs supplied")
    outcomes = []
    for path in outcome_paths:
        outcomes.extend(load_jsonl(path))
    linked, report = reconcile(rows, outcomes, datetime.now(timezone.utc))
    report["published_outcome_archives_scanned"] = len(outcome_paths)
    report["published_source_scope"] = "ESPN archive observations only; no independent final certification"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "linked_pregame_outcomes.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in linked), encoding="utf-8")
    (out / "validation_readiness.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
