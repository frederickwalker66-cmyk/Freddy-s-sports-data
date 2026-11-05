"""Eight-sport archived native probability vs published-final review, NEVER training data.

Only pregame archived research receipts may join published ESPN results.
Soccer 90-minute settlement is NOT independently established by a generic
published final; all records stay unqualified and have no usable calibration
labels until separately adjudicated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from challenger_multisport_native_capture import (
    CAPTURE_LEAGUES, LEAGUES, SIDES, MARKETS, SCOPE, FORECAST_FILE
)
from challenger_prospective_outcome_validation import instant

FINAL_FILE = "linked_pregame_outcomes.jsonl"


def _published_event(row, now):
    if (not isinstance(row, dict) or row.get("league") not in CAPTURE_LEAGUES
            or row.get("status") != "linked_to_espn_published_final_only"
            or row.get("independent_league_outcome_verified") is not False
            or row.get("qualified_for_challenger_backtest") is not False
            or row.get("model_prediction_at_capture") is not None
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("invalid_published_link_quarantine")
    eid = str(row.get("espn_event_id", ""))
    result = row.get("published_outcome")
    if not eid.isdigit() or not isinstance(result, dict) or result.get("result") not in ("home", "away", "draw"):
        raise ValueError("result_missing")
    u = urlparse(result.get("source_url") or "")
    if u.scheme != "https" or u.hostname != "site.api.espn.com":
        raise ValueError("published_outcome_source_not_espn")
    started = instant(row.get("event_start_utc"))
    observed = instant(result.get("published_retrieved_at_utc"))
    captured = instant(row.get("snapshot_completed_at_utc"))
    if not captured < started < observed <= now:
        raise ValueError("published_result_timing_invalid")
    return (row["league"], eid), (row, started, observed)


def _native_side(row, now):
    if (not isinstance(row, dict)
            or row.get("stage") != "challenger_001_multisport_prospective_research_only"
            or row.get("league") not in CAPTURE_LEAGUES
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False
            or row.get("model_fit_independently_certified") is not False
            or row.get("source_evidence_independently_authenticated") is not False
            or row.get("qualified_for_calibration") is not False
            or row.get("market_implied_probability_used_as_model") is not False
            or row.get("probability_source") != "native_challenger_model_unverified_research"):
        raise ValueError("not_safe_native_research_receipt")
    league = row["league"]
    eid = row.get("event_id")
    if (not isinstance(eid, str) or not eid.isdigit()
            or row.get("market_type") != MARKETS[league]
            or row.get("settlement_scope") != SCOPE[league]
            or row.get("selection_key") not in SIDES[league]
            or not isinstance(row.get("model_version"), str)
            or not row["model_version"].startswith(f"challenger-001-{league}-")
            or not isinstance(row.get("model_sha256"), str)
            or len(row["model_sha256"]) != 64):
        raise ValueError("sport_market_identity_or_model_invalid")
    p = row.get("research_probability")
    if type(p) not in (float, int) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("invalid_native_research_probability")
    snapshot = instant(row.get("snapshot_utc"))
    created = instant(row.get("scored_at_utc"))
    started = instant(row.get("event_start_utc"))
    if not (snapshot <= created < started and created <= now):
        raise ValueError("native_capture_timing_invalid")
    return (league, eid), row


def evaluate_unqualified(native_rows, linked_rows, as_of=None):
    """Preserve research matches only; absolutely no automatic calibration rows."""
    now = as_of or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("as_of_must_be_timezone_aware")
    now = now.astimezone(timezone.utc)
    failures = Counter()
    published = {}
    for row in linked_rows:
        try:
            key, tup = _published_event(row, now)
            if key in published:
                published[key] = None  # fail closed on conflicting source archives
                failures["duplicate_published_event"] += 1
            else:
                published[key] = tup
        except (TypeError, ValueError, KeyError, OverflowError):
            failures["invalid_published_link"] += 1
    groups = defaultdict(list)
    for row in native_rows:
        try:
            key, receipt = _native_side(row, now)
            groups[key].append(receipt)
        except (TypeError, ValueError, KeyError, OverflowError):
            failures["invalid_or_non_native_forecast"] += 1
    output = []
    per_league = Counter()
    for (league, event_id), receipts in sorted(groups.items()):
        sides = {x["selection_key"] for x in receipts}
        if sides != set(SIDES[league]) or len(receipts) != len(SIDES[league]):
            failures["missing_or_duplicate_model_outcome_sides"] += 1
            continue
        if (len({r["model_version"] for r in receipts}) != 1
                or len({r["model_sha256"] for r in receipts}) != 1
                or len({r["event_start_utc"] for r in receipts}) != 1
                or len({r["scored_at_utc"] for r in receipts}) != 1
                or len({r["source_snapshot_sha256"] for r in receipts}) != 1
                or abs(sum(r["research_probability"] for r in receipts) - 1) > 1e-6):
            failures["invalid_multioutcome_probability_vector"] += 1
            continue
        final_data = published.get((league, event_id))
        if final_data is None:
            failures["no_unique_valid_published_final"] += 1
            continue
        final, started, observed = final_data
        forecast = receipts[0]
        try:
            if (instant(forecast["event_start_utc"]) != started
                    or instant(forecast["scored_at_utc"]) >= started
                    or not all(final.get(k) == forecast.get(k) for k in ("home_team", "away_team"))):
                raise ValueError("event_or_team_identity_mismatch")
        except (TypeError, ValueError, KeyError, OverflowError):
            failures["event_or_team_identity_mismatch"] += 1
            continue
        # A soccer published final might include ET/penalties, so no independent
        # regulation-time settlement is inferred from result or final score.
        soccer = league in ("mls", "uefa_champions_league")
        output.append({
            "record_type": "unqualified_multisport_calibration_review_candidate",
            "league": league, "event_id": event_id,
            "market_type": MARKETS[league], "settlement_scope": SCOPE[league],
            "model_version": forecast["model_version"],
            "model_sha256_claimed": forecast["model_sha256"],
            "forecast_captured_at_utc": forecast["scored_at_utc"],
            "event_start_utc": forecast["event_start_utc"],
            "published_final_observed_at_utc": observed.isoformat(),
            "native_research_probabilities_claimed": {
                side: next(r["research_probability"] for r in receipts
                           if r["selection_key"] == side)
                for side in SIDES[league]
            },
            "published_result_for_review_only": final["published_outcome"]["result"],
            "soccer_regulation_90_min_outcome_adjudicated": False if soccer else None,
            "calibration_label": None,
            "independent_model_provenance_verified": False,
            "independent_outcome_verified": False,
            "qualified_for_calibration": False,
            "bet_ready": False, "champion_001_modified": False,
        })
        per_league[league] += 1
    report = {
        "stage": "challenger_eight_sport_native_calibration_review_only",
        "as_of_utc": now.isoformat(),
        "all_leagues": list(LEAGUES),
        "native_forecast_market_selection_rows": len(native_rows),
        "archived_published_outcome_rows": len(linked_rows),
        "unqualified_matched_games": len(output),
        "unqualified_matched_games_by_league": dict(sorted(per_league.items())),
        "failed_joins": dict(sorted(failures.items())),
        "independently_verified_calibration_examples": 0,
        "soccer_90_minute_outcomes_adjudicated": 0,
        "training_dataset_emitted": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Published ESPN results are not independently adjudicated market "
                    "settlements. Soccer requires explicit 90-minute result review; "
                    "no calibration labels, training rows or betting eligibility are produced."),
    }
    return output, report


def _read(root, name):
    files = sorted(Path(root).rglob(name))
    if not files:
        return []
    if len(files) != 1:
        raise ValueError("ambiguous_archive_duplicate:" + name)
    return [json.loads(s) for s in files[0].read_text(encoding="utf-8").splitlines()
            if s.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive-root", default="calibration_sources")
    ap.add_argument("--output-dir", default="challenger_results/calibration_evidence")
    args = ap.parse_args(argv)
    native = _read(args.archive_root, FORECAST_FILE)
    published = _read(args.archive_root, FINAL_FILE)
    queue, report = evaluate_unqualified(native, published)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "multisport_review_queue.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in queue), encoding="utf-8")
    (out / "multisport_review_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"multisport_research_links": len(queue),
                      "qualified_calibration_examples": 0,
                      "report": str(out/"multisport_review_report.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
