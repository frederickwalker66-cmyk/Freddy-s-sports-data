"""Evidence-constrained metrics health report for Freddy's Picks AI.

This module improves observability, never model probabilities. All data
is from a separately validated, persisted original-forward calibration
report; bookmaker quotes and public scores cannot authenticate betting EV.
"""
from __future__ import annotations

from v8_forward_calibration import (
    MIN_PUBLIC_SCORE_BRIER_GAMES, MIN_RESEARCH_ECE_GAMES,
    MIN_BIN_FOR_ECE, MIN_BIN_FOR_OBSERVED_RATE, _wilson,
)
from v8_forward_calibration_view import read_calibration


def build_metrics_health(*, calibration_file=None, persisted=None,
                         market_evidence=None, leagues=("nba",)):
    """Read-only diagnostics; unavailable values stay None, not zero.

    No estimate from fewer than 50 games is advertised as model skill;
    a Wilson band on the observed HOME-WIN BASE RATE is explicitly not
    win-pick accuracy and not a calibrated forecast.
    """
    if persisted is None:
        persisted = read_calibration(calibration_file)
    if not isinstance(persisted, dict):
        raise ValueError("validated_original_calibration_report_required")
    if (persisted.get("bet_ready") is not False
            or persisted.get("certified_positive_ev_bets") != 0
            or persisted.get("original_Champion_001_certified_shadows") != 0):
        raise ValueError("untrusted_calibration_certification_claim")
    if type(leagues) not in (tuple, list) or not leagues or any(
            not isinstance(lg, str) or not lg for lg in leagues):
        raise ValueError("explicit_sport_scope_required")
    models = persisted.get("models", [])
    if not isinstance(models, list):
        raise ValueError("validated_calibration_models_required")
    archived = persisted.get("archived_original_forward_forecasts")
    graded = persisted.get("graded_research_NBA_games")
    pending = persisted.get("pending_ungraded")
    quarantined = persisted.get("quarantined")
    known = all(type(x) is int and x >= 0 for x in
                (archived, graded, pending, quarantined))
    if known and archived != graded + pending + quarantined:
        raise ValueError("forward_grade_coverage_counts_do_not_reconcile")
    if not known and any(x is not None for x in (archived, graded, pending, quarantined)):
        raise ValueError("partially_known_calibration_counts")
    per_model = []
    for model in models:
        bins = model["fixed_predeclared_probability_bins"]
        n = model["original_forward_pregame_games_graded"]
        distribution = [{
            "p_home_bin": (f"{int(b['probability_min_inclusive']*100)}-"
                           f"{int(b['probability_max_exclusive']*100)}%"),
            "observations": b["observations"],
            "sample_share_percent": round(100*b["observations"]/n, 1),
            "observed_home_wins": b["home_wins"],
            "below_minimum_for_reliability_rate":
                0 < b["observations"] < MIN_BIN_FOR_OBSERVED_RATE,
            "below_minimum_for_ece":
                0 < b["observations"] < MIN_BIN_FOR_ECE,
        } for b in bins]
        wins = sum(b["home_wins"] for b in bins)
        occupied = sum(b["observations"] > 0 for b in bins)
        maxshare = max((b["observations"] for b in bins), default=0)/n
        per_model.append({
            "model_version": model["model_version"],
            "graded_forecasts": n,
            "observed_home_wins_not_model_correct_picks": wins,
            "observed_away_wins_not_model_misses": n-wins,
            "home_win_base_rate_percent_NOT_MODEL_ACCURACY":
                round(100*wins/n, 1),
            "home_win_base_rate_Wilson_95pct_NOT_MODEL_ACCURACY":
                _wilson(wins,n),
            "occupied_predeclared_probability_bins": occupied,
            "predeclared_probability_bins": len(bins),
            "largest_bin_share_percent": round(100*maxshare, 1),
            "below_20_observation_occupied_bins":
                sum(0 < b["observations"] < MIN_BIN_FOR_OBSERVED_RATE for b in bins),
            "below_10_observation_occupied_bins":
                sum(0 < b["observations"] < MIN_BIN_FOR_ECE for b in bins),
            "observed_bin_distribution": distribution,
            "minimum_forward_grades_for_skill_metrics": MIN_PUBLIC_SCORE_BRIER_GAMES,
            "additional_grades_for_skill_metrics": max(
                0, MIN_PUBLIC_SCORE_BRIER_GAMES-n),
            "minimum_forward_grades_for_exploratory_ece": MIN_RESEARCH_ECE_GAMES,
            "additional_grades_for_exploratory_ece": max(
                0, MIN_RESEARCH_ECE_GAMES-n),
            "research_Brier": model.get("research_Brier"),
            "research_log_loss": model.get("research_log_loss"),
            "research_directional_accuracy": model.get("research_directional_accuracy"),
            "research_directional_accuracy_Wilson_95pct":
                model.get("research_directional_accuracy_wilson_95pct"),
            "research_Brier_skill_vs_fixed_50_50_NOT_sportsbook":
                model.get("research_Brier_skill_vs_fixed_50_50_NOT_sportsbook"),
            "research_log_loss_skill_vs_fixed_50_50_NOT_sportsbook":
                model.get("research_log_loss_skill_vs_fixed_50_50_NOT_sportsbook"),
            "exploratory_expected_calibration_error":
                model.get("exploratory_expected_calibration_error"),
            "not_champion_001_and_not_market_ev": True,
            "model_betting_ready": False,
        })
    sources = {}
    for league in leagues:
        if market_evidence is not None and league in market_evidence:
            raw = market_evidence[league]
            if not isinstance(raw, dict):
                raise ValueError("invalid_sport_market_evidence")
            values = (raw.get("archived_provider_quote_rows"),
                      raw.get("fresh_paired_game_boards"),
                      raw.get("fresh_paired_player_prop_markets"))
            if any(type(x) is not int or x < 0 for x in values):
                raise ValueError("invalid_market_evidence_counts")
            sources[league] = {
                "archived_quote_rows": values[0],
                "fresh_paired_game_markets": values[1],
                "fresh_paired_prop_markets": values[2],
                "source_blocker": raw.get("primary_source_blocker"),
                "bookmaker_checkout_verified": False,
                "independently_calibrated_market_model": False,
                "action": ("RETRIEVE_OR_VALIDATE_FRESH_EXACT_PRICES"
                           if values[0] else "COLLECT_PROVIDER_QUOTES_WITH_USER_OPT_IN"),
            }
        else:
            sources[league] = {
                "archived_quote_rows": None,
                "fresh_paired_game_markets": None,
                "fresh_paired_prop_markets": None,
                "source_blocker": "NO_MARKET_EVIDENCE_SUPPLIED",
                "bookmaker_checkout_verified": False,
                "independently_calibrated_market_model": False,
                "action": "INSPECT_SAVED_MARKET_SOURCE_COVERAGE",
            }
    return {
        "report_type": "freddys_v8_evidence_metric_health_v1",
        "status": "OBSERVABILITY_UPGRADED_NO_PROBABILITY_REFIT",
        "calibration_source_status": persisted.get("status"),
        "nba_archived_original_forward_forecasts": archived,
        "nba_graded_research_games": graded,
        "nba_pending_ungraded": pending,
        "nba_quarantined": quarantined,
        "nba_grade_coverage_percent":
            round(100*graded/archived, 1) if known and archived else None,
        "additional_nba_grades_to_50":
            max(0, MIN_PUBLIC_SCORE_BRIER_GAMES-graded) if known else None,
        "additional_nba_grades_to_100":
            max(0, MIN_RESEARCH_ECE_GAMES-graded) if known else None,
        "model_reliability_diagnostics": per_model,
        "source_market_diagnostics_by_league": sources,
        "uncertainty_warning": (
            "Observed home-win rates and Wilson bands describe the sampled "
            "outcomes, NOT model accuracy. Brier, log loss, directional skill "
            "and ECE remain unavailable until their separate gates pass."),
        "next_actions": [
            "MATURE_AND_INDEPENDENTLY_RECONCILE_PREGAME_FORECAST_OUTCOMES",
            "REVIEW_PROBABILITY_BIN_COVERAGE_AND_GRADED_SAMPLE_SIZE",
            "VALIDATE_CURRENT_EXACT_MARKET_PRICES_AND_PLAYER_AVAILABILITY",
            "CROSSCHECK_OUTCOMES_AND_PROVENANCE_BEFORE_ANY_RECALIBRATION",
        ],
        "betting_decision": "HOLD_NO_CERTIFIED_EDGE",
        "native_calibrator_fitted": False,
        "new_or_revised_model_probabilities": 0,
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "money_wagered_usd": 0,
        "bet_ready": False,
    }
