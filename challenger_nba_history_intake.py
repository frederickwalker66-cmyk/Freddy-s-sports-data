"""NBA research history-review packets from archived prospective evidence.

Creates NON-TRAINABLE human-review candidates, NOT historical_results.jsonl.
ESPN-published scores, same-workflow receipts and pregame form do not prove
independent source publication timing or official bookmaker settlement.
No sportsbook APIs, no SportsGameOdds, no certified forecasts, no wagers.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from challenger_backtest import timestamp

REQUIRED_FEATURES = frozenset({
    "pregame_home_prior_win_rate",
    "pregame_away_prior_win_rate",
    "pregame_home_prior_margin_avg",
    "pregame_away_prior_margin_avg",
})
REVIEW_BLOCKERS = [
    "historical_feature_source_publication_time_not_independently_proven",
    "original_pregame_receipts_not_independently_authenticated",
    "independent_outcome_adjudication_missing",
    "bookmaker_moneyline_settlement_rules_unverified",
    "independent_reviewer_signoff_missing",
]


def _source(value):
    if not isinstance(value, str):
        return False
    u = urlparse(value)
    return u.scheme == "https" and u.hostname == "site.api.espn.com"


def _validate(row, now):
    """Fail closed on source, result, timing, label or status ambiguity."""
    if not isinstance(row, dict) or row.get("league") != "nba":
        raise ValueError("not NBA research evidence")
    required_false = (
        "independent_feature_asof_review", "independent_outcome_adjudication",
        "market_settlement_rules_verified", "qualified_for_challenger_backtest",
        "eligible_to_train_probability_model", "certified_prediction",
        "bet_ready", "champion_001_modified",
    )
    if (row.get("record_type") != "challenger_eight_sport_evidence_review_queue_only"
            or row.get("research_target") != "published_score_winner_binary_research"
            or row.get("review_status") != "needs_league_rule_and_independent_outcome_review"
            or any(row.get(field) is not False for field in required_false)
            or row.get("model_probability") is not None):
        raise ValueError("review-only status or provenance flags inconsistent")
    event = row.get("event_id")
    if not isinstance(event, str) or not event.isdigit() or not event.strip():
        raise ValueError("invalid original event identity")
    home, away = row.get("home_team"), row.get("away_team")
    if (not isinstance(home, str) or not home.strip() or not isinstance(away, str)
            or not away.strip() or home.strip().casefold() == away.strip().casefold()):
        raise ValueError("ambiguous teams")
    snap = timestamp(row.get("snapshot_utc"))
    features_at = timestamp(row.get("features_asof_utc"))
    start = timestamp(row.get("start_utc"))
    outcome_seen = timestamp(row.get("published_outcome_seen_utc"))
    if not features_at <= snap < start < outcome_seen <= now:
        raise ValueError("source timestamps violate chronological order")
    if not _source(row.get("schedule_source_url")) or not _source(row.get("published_result_url")):
        raise ValueError("source URL not expected ESPN reference")
    scores = row.get("published_score_only")
    if (not isinstance(scores, dict) or type(scores.get("home")) is not int
            or type(scores.get("away")) is not int
            or not 0 <= scores["home"] <= 999 or not 0 <= scores["away"] <= 999
            or scores["home"] == scores["away"]):
        raise ValueError("missing, implausible or tied binary final")
    result = "home" if scores["home"] > scores["away"] else "away"
    if row.get("published_result_research_label") != result:
        raise ValueError("published result contradicts score")
    features = row.get("features")
    if (not isinstance(features, dict) or set(features) != REQUIRED_FEATURES
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in features.values())
            or any(not 0 <= features[name] <= 1 for name in (
                "pregame_home_prior_win_rate", "pregame_away_prior_win_rate"))
            or any(abs(features[name]) > 500 for name in (
                "pregame_home_prior_margin_avg", "pregame_away_prior_margin_avg"))):
        raise ValueError("missing or invalid prospective feature schema")
    # Original SHA strings are only self-attested; do not synthesize hashes.
    for field in ("source_receipt_sha256_not_independently_verified",
                  "linked_receipt_sha256_not_independently_verified"):
        h = row.get(field)
        if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("missing original research digest")
    return {
        "record_type": "challenger_nba_history_candidate_review_only",
        "event_id": event,
        "league": "nba",
        "market_type": "moneyline",
        "selection_type": "home",
        "home_team": home.strip(),
        "away_team": away.strip(),
        "outcome": int(result == "home"),  # Published score label, not independently adjudicated.
        "snapshot_utc": snap.isoformat(),
        "features_asof_utc": features_at.isoformat(),
        "start_utc": start.isoformat(),
        "outcome_verified_at_utc": outcome_seen.isoformat(),  # Observed publication, NOT independent verification.
        "event_source_url": row["schedule_source_url"],
        "feature_source_url": row["schedule_source_url"],
        "outcome_source_url": row["published_result_url"],
        "features": dict(sorted(features.items())),
        "published_score_only": scores,
        "source_receipt_sha256_not_independently_verified":
            row["source_receipt_sha256_not_independently_verified"],
        "linked_receipt_sha256_not_independently_verified":
            row["linked_receipt_sha256_not_independently_verified"],
        "review_required": REVIEW_BLOCKERS[:],
        "qualified_for_challenger_backtest": False,
        "independent_asof_review": False,
        "independent_outcome_review": False,
        "feature_snapshot_sha256": None,
        "outcome_snapshot_sha256": None,
        "eligible_to_train_probability_model": False,
        "certified_prediction": False,
        "model_probability": None,
        "bet_ready": False,
        "wagers_placed": 0,
        "champion_001_modified": False,
    }


def build_intake(rows, now):
    if not isinstance(rows, list) or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("review rows and aware time required")
    now = now.astimezone(timezone.utc)
    counts = Counter()
    by_id = {}
    seen = Counter()
    for row in rows:
        counts["rows_seen"] += 1
        if not isinstance(row, dict):
            counts["invalid_research_rows"] += 1
            continue
        if row.get("league") != "nba":
            counts["non_nba_rows_excluded"] += 1
            continue
        counts["nba_rows_seen"] += 1
        try:
            candidate = _validate(row, now)
        except (ValueError, TypeError, OverflowError, KeyError):
            counts["invalid_nba_rows"] += 1
            continue
        event = candidate["event_id"]
        seen[event] += 1
        by_id.setdefault(event, candidate)
    candidates = [r for k, r in by_id.items() if seen[k] == 1]
    candidates.sort(key=lambda r: (r["start_utc"], r["event_id"]))
    counts["ambiguous_duplicate_event_ids"] = sum(n > 1 for n in seen.values())
    counts["duplicate_rows_quarantined"] = sum(n for n in seen.values() if n > 1)
    counts["structurally_valid_review_candidates"] = len(candidates)
    report = {
        "stage": "challenger_001_nba_history_review_intake_only",
        "generated_utc": now.isoformat(),
        "counts": dict(sorted(counts.items())),
        "nba_review_candidates": len(candidates),
        "minimum_chronological_train_games": 200,
        "minimum_chronological_holdout_games": 50,
        "minimum_total_games": 250,
        "shortfall_vs_250_structural_candidates": max(0, 250 - len(candidates)),
        "independently_verified_training_records": 0,
        "qualified_for_challenger_backtest": 0,
        "trained_models_created": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "result": "blocked_independent_source_review_and_chronological_validation",
        "blockers": REVIEW_BLOCKERS[:],
        "warning": (
            "Review packets are NOT historical_results.jsonl or certified training examples. "
            "ESPN-published score, self-generated checksums and feature-source URLs "
            "do not prove original as-of publication, independent outcome review, "
            "or point-in-time market settlement. Never train from these files."
        ),
    }
    return candidates, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-queue", required=True)
    parser.add_argument("--output-dir", default="prospective_validation")
    args = parser.parse_args(argv)
    p = Path(args.review_queue)
    if not p.is_file():
        raise FileNotFoundError("missing prospective evidence review queue")
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    candidates, report = build_intake(rows, datetime.now(timezone.utc))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "nba_history_review_candidates.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True, allow_nan=False) + "\n" for x in candidates),
        encoding="utf-8")
    (out / "nba_history_intake_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
