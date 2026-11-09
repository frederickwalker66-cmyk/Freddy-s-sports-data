"""Freddy's Picks AI V8 certification *evidence* auditor (not self-certification).

Read previously archived, completed GitHub source, training and price reports.
Reconcile same-run source counts and expose per-league reasons why candidate
probabilities remain unqualified. A successful job, review flag, self-created
hash or aggregator quote is not publisher custody, independent out-of-sample
skill, a direct sportsbook checkout quote, or proof of betting profitability.

Never generates fake historical evidence, signs its own attestation, certifies
forecasts, changes frozen Champion-001 or places wagers. An independent external
release review is required before actual certification can occur.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v8_milestone_tracker import LEAGUES

SOURCE_FILES = {
    "coverage": "preflight_summary.json",
    "release": "model_completion/release_readiness.json",
    "training": "model_completion/native_training/research_training_report.json",
    "champion": "model_completion/champion_authentication.json",
    "identity": "independent_identity/independent_game_identity_report.json",
}
SHARP_FILE = "validation_output/moneyline_market_baseline_report.json"
MAX_REPORT_BYTES = 2_000_000


def read_optional(base, relative):
    if base is None:
        return None
    target = Path(base) / relative
    if not target.is_file():
        return None
    if target.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("oversized_untrusted_upstream_report")
    obj = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("upstream_report_must_be_a_JSON_object")
    return obj


def count(row, name):
    value = row.get(name)
    if type(value) is not int or value < 0:
        raise ValueError("invalid_provenance_count_" + name)
    return value


def inspect_archives(source_dir=None, sharp_dir=None, source_run_id=None,
                     sharp_run_id=None):
    """Return an audit of saved *reports*, never an automatically certified pick."""
    reports = {key: read_optional(source_dir, name)
               for key, name in SOURCE_FILES.items()}
    coverage = reports["coverage"]
    release = reports["release"]
    training = reports["training"]
    champion = reports["champion"]
    identity = reports["identity"]
    sharp = read_optional(sharp_dir, SHARP_FILE)
    if coverage is not None:
        if (coverage.get("stage") !=
                "challenger_eight_sport_original_schedule_live_preflight_research_only"
                or set(coverage.get("by_league", {})) != set(LEAGUES)):
            raise ValueError("wrong_source_archive_or_missing_leagues")
        source_events = count(coverage["totals"], "pregame_events_archived")
        if source_events != sum(count(r, "future_games_archived")
                                for r in coverage["by_league"].values()):
            raise ValueError("source_games_do_not_reconcile")
        if coverage.get("champion_001_modified") is not False:
            raise ValueError("frozen_champion_integrity_unknown")
    else:
        source_events = None
    if release is not None:
        if (release.get("stage") != "challenger_82_full_sequence_release_readiness"
                or release.get("champion_001_modified") is not False):
            raise ValueError("wrong_release_gate_or_champion_integrity_unknown")
        if coverage is None:
            raise ValueError("orphan_release_without_same_run_source")
        if count(release, "archived_pregame_games") != source_events:
            raise ValueError("release_and_source_event_counts_disagree")
    if training is not None:
        if (training.get("stage") != "challenger_multisport_native_research_training"
                or training.get("champion_001_modified") is not False):
            raise ValueError("unsafe_training_report")
        models = training.get("trained_research_models")
        if (not isinstance(models, list) or len(models) != len(set(models))
                or any(x not in LEAGUES for x in models)):
            raise ValueError("invalid_native_training_models")
        count(training, "review_attested_records_received")
    else:
        models = []
    if champion is not None:
        if (champion.get("stage") != "champion_001_artifact_authentication"
                or champion.get("champion_001_modified") is not False):
            raise ValueError("unsafe_champion_report")
    if identity is not None:
        if (identity.get("stage") != "challenger_78_independent_league_identity_research_only"
                or identity.get("champion_001_modified") is not False):
            raise ValueError("unsafe_identity_report")
        if coverage is None:
            raise ValueError("orphan_identity_without_source")
        if count(identity, "archived_espn_events_reviewed") != source_events:
            raise ValueError("identity_and_source_event_counts_disagree")
    if sharp is not None:
        if (sharp.get("report_type") !=
                "challenger_full_game_two_way_market_baseline_research_only"
                or sharp.get("champion_001_modified") is not False):
            raise ValueError("unsafe_sharp_price_report")
    present = {name: item is not None for name, item in reports.items()}
    present["sharp_moneyline_baseline"] = sharp is not None
    leagues = {}
    league_matches = (release.get("league_operated_identity_matches_research_only", {})
                      if release is not None else {})
    if not isinstance(league_matches, dict):
        raise ValueError("invalid_independent_game_identity_counts")
    for league in LEAGUES:
        item = coverage["by_league"][league] if coverage else None
        archived = count(item, "future_games_archived") if item else None
        source_failures = count(item, "source_days_failed") if item else None
        matched = league_matches.get(league) if release else None
        if release:
            if type(matched) is not int or matched < 0 or (archived is not None and matched > archived):
                raise ValueError("invalid_league_identity_matches")
        blockers = []
        if item is None:
            blockers.append("source_archive_missing")
        elif archived == 0:
            blockers.append("no_pregame_event_archived_in_latest_window")
        if source_failures:
            blockers.append("some_source_dates_failed")
        if matched is None:
            blockers.append("separate_league_operated_identity_not_reviewed")
        elif matched == 0:
            blockers.append("no_cross_source_league_operated_game_identity")
        if league not in models:
            blockers.append("no_native_research_model_fitted_from_qualified_history")
        else:
            blockers.append("research_model_not_independently_certified")
        blockers.extend((
            "training_source_asof_and_settlement_not_independently_audited",
            "untouched_holdout_performance_and_probability_calibration_not_certified",
            "live_independent_bookmaker_checkout_quote_not_verified",
            "independent_model_release_approval_not_on_file",
        ))
        if league in ("mls", "uefa_champions_league"):
            blockers.append("regulation_90_min_three_way_settlement_not_certified")
        leagues[league] = {
            "archived_source_games_latest_run": archived,
            "failed_source_days_latest_run": source_failures,
            "league_operated_identity_matches_research_only": matched,
            "native_research_model_fitted": league in models,
            "certified_predictions": 0,
            "positive_ev_selections_certified": 0,
            "status": "BLOCKED_INDEPENDENT_VALIDATION",
            "blockers": blockers,
        }

    release_blockers = release.get("blockers", []) if release else []
    if not isinstance(release_blockers, list) or any(
        not isinstance(item, str) for item in release_blockers
    ):
        raise ValueError("invalid_model_release_blocker_list")
    nba_source_errors = identity.get("network_nba_source_failures_by_url", {}) if identity else {}
    if (not isinstance(nba_source_errors, dict)
            or any(not isinstance(key, str) or not isinstance(value, str)
                   for key, value in nba_source_errors.items())):
        raise ValueError("invalid_nba_source_failure_diagnostics")
    champion_verified = bool(
        champion and champion.get("original_executable_verified") is True
        and champion.get("immutable_model_version_authenticated") is True
        and champion.get("reproducible_reference_outputs_verified") is True)
    sharp_pairs = count(sharp, "two_way_research_market_pairs") if sharp else None
    report = {
        "version": "v8-certification-archive-audit-v1",
        "status": "HOLD_MISSING_INDEPENDENT_MODEL_AND_PRICE_PROOF",
        "source_run_id": source_run_id,
        "sharp_run_id": sharp_run_id,
        "reports_found": present,
        "source_games_archived": source_events,
        "research_moneyline_price_pairs_from_aggregator": sharp_pairs,
        "native_research_models_seen": sorted(models),
        "model_release_decision_from_source_pipeline": (
            release.get("release_decision") if release is not None else None),
        "model_release_blockers_from_source_pipeline": release_blockers,
        "nba_official_source_request_failures": nba_source_errors,
        "review_attested_historical_training_rows_not_independently_certified": (
            count(training, "review_attested_records_received") if training else None),
        "prior_artifact_report_claims_champion_verified_untrusted": champion_verified,
        "original_champion_001_authenticated_by_external_review": False,
        "independent_bookmaker_checkout_quotes_verified": 0,
        "independently_validated_pregame_forecast_probabilities": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_v8_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "by_league": leagues,
        "next_required_external_evidence": [
            "Recover externally authenticated original frozen Champion-001 source/weights and reference predictions if Champion certification is intended.",
            "Produce independently authenticated, untampered original as-of pregame training features and adjudicated outcomes.",
            "Train reproducible native models; evaluate 200+ chronological training and 50+ untouched holdout games per league and probability calibration.",
            "Archive genuine pre-event forecast records from models trained before the game.",
            "Capture independently verified event/market/selection-specific executable sportsbook checkout prices.",
            "Have an independent reviewer inspect evidence and explicitly approve any model release; preserve loss outcomes and model version.",
        ],
        "warning": ("Existing GitHub job success and local report receipts cannot certify "
                    "probability calibration, independent source custody, sharp money, "
                    "positive expected value or a wager. This is an evidence inventory only."),
    }
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", help="Saved complete independent-source GH artifact directory")
    p.add_argument("--sharp-dir", help="Saved completed SharpAPI GH artifact directory")
    p.add_argument("--source-run-id", type=int)
    p.add_argument("--sharp-run-id", type=int)
    p.add_argument("--output", default="v8_results/certification_audit.json")
    args = p.parse_args(argv)
    result = inspect_archives(
        args.source_dir, args.sharp_dir, args.source_run_id, args.sharp_run_id)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "source_games_archived": result["source_games_archived"],
        "research_price_pairs": result["research_moneyline_price_pairs_from_aggregator"],
        "certified_predictions": 0, "bet_ready": False,
        "output": str(dest),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
