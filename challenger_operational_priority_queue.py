"""#85 concise validated action queue from actual completed source research gates.

This is not a promise of background development, automatic data repair,
certified predictions, or model release. Priorities are grounded in receipts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def synthesize(release, independent, nfl, rolling):
    if not all(isinstance(x, dict) for x in (release, independent, nfl, rolling)):
        raise ValueError("missing_same_run_operational_reports")
    if (release.get("stage") != "challenger_82_full_sequence_release_readiness"
            or independent.get("stage") !=
            "challenger_78_independent_league_identity_research_only"
            or nfl.get("stage") !=
            "challenger_83_nflverse_third_party_pregame_identity_research_only"
            or rolling.get("stage") !=
            "challenger_84_rolling_original_pregame_research_ledger"):
        raise ValueError("wrong_operational_evidence_stages")
    for x in (release, independent, nfl, rolling):
        if x.get("champion_001_modified") is not False or x.get("certified_positive_ev_bets") != 0:
            raise ValueError("promoted_unverified_operational_evidence")
    if (release.get("archived_pregame_games") != independent.get("archived_espn_events_reviewed")
            or rolling.get("distinct_future_espn_game_ids", -1) <
            release.get("archived_pregame_games", 0)
            or nfl.get("nfl_games_reviewed") !=
            release.get("league_operated_identity_matches_research_only", {}).get("nfl", 0)
            + (nfl.get("nfl_games_reviewed",0) if release.get("league_operated_identity_matches_research_only", {}).get("nfl", 0) == 0 else 0)):
        raise ValueError("unreconciled_operational_counts")
    # No NFL league-operated adapter has been implemented. nflverse is counted
    # only as a third-party signal and NEVER added to official matches.
    if release.get("league_operated_identity_matches_research_only", {}).get("nfl", 0) != 0:
        raise ValueError("third_party_nfl_misrepresented_as_league_operated")
    if (rolling.get("observations_checked",0) < release["archived_pregame_games"]
            or rolling.get("qualified_training_games") != 0
            or nfl.get("qualified_training_games") != 0
            or release.get("independently_verified_bookmaker_prices") != 0):
        raise ValueError("invalid_source_or_training_evidence")
    official = sum(release["league_operated_identity_matches_research_only"].values())
    third_party = nfl["independent_third_party_pregame_identity_matches_research_only"]
    if type(third_party) is not int or not 0 <= third_party <= nfl["nfl_games_reviewed"]:
        raise ValueError("invalid_third_party_nfl_count")
    nba_sources = independent.get("network_nba_source_failures_by_url", {})
    if not isinstance(nba_sources, dict):
        raise ValueError("invalid_nba_source_failure_summary")
    revisions = sum(rolling.get("source_revision_status", {}).get(label, 0) for label in (
        "team_or_orientation_conflict_research_quarantined",
        "kickoff_revision_observed_research_quarantined",
    ))
    return {
        "stage": "challenger_85_unattended_operational_evidence_priorities",
        "software_sequence": "completed_actual_source_captures",
        "model_release": "BLOCKED_NOT_CERTIFIED",
        "current_run_future_games": release["archived_pregame_games"],
        "deduplicated_games_across_available_research_runs":
            rolling["distinct_future_espn_game_ids"],
        "official_league_identity_matches_this_run_research_only": official,
        "independent_third_party_nfl_matches_this_run_research_only": third_party,
        "source_revisions_quarantined": revisions,
        "nba_source_errors": dict(sorted(nba_sources.items())),
        "priorities": [
            {"priority": 1, "work": "continue genuine independent league-operated schedules and source-access diagnostics",
             "status": "engineering_can_continue", "source_failures_reported": len(nba_sources)},
            {"priority": 2, "work": "accumulate pre-event original bytes from successive actual observation runs",
             "status": "rolling_ledger_implemented_research_only",
             "source_runs": rolling["capture_runs_checked"]},
            {"priority": 3, "work": "recover original independent Champion-001 executable/signature and reference predictions",
             "status": "requires_external_owner_attestation"},
            {"priority": 4, "work": "assemble independently reviewed event-specific as-of features, native training and disjoint holdouts",
             "status": "requires_independent_real_evidence"},
            {"priority": 5, "work": "capture directly observed DraftKings market IDs, lines, sides, prices and executable quote times",
             "status": "requires_independently_authorized_bookmaker_evidence"},
            {"priority": 6, "work": "compute genuine OOS calibration and independently settled CLV/ROI only once eligible",
             "status": "blocked_until_prerequisites_verified"},
        ],
        "qualified_chronological_training_games": 0,
        "verified_direct_draftkings_quotes": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "note": "Engineering can advance without waiting for 'Next', but external data, rights and independent proof are not generated by rerunning the code.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release-report", required=True)
    p.add_argument("--identity-report", required=True)
    p.add_argument("--nfl-report", required=True)
    p.add_argument("--rolling-report", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    paths = (a.release_report, a.identity_report, a.nfl_report, a.rolling_report)
    report = synthesize(*(json.loads(Path(x).read_text()) for x in paths))
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"stage": report["stage"], "model_release": report["model_release"],
                      "nfl_third_party_matches": report["independent_third_party_nfl_matches_this_run_research_only"],
                      "certified_positive_ev_bets": 0},sort_keys=True))


if __name__ == "__main__":
    main()
