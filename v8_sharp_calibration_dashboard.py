"""Read-only, strictly scoped V8 Sharp Edge calibration diagnostic.

The only currently supported durable genuine pregame outcome-paired
calibration source is original NBA research home-win forecasts. It must
never be applied to NBA spreads/totals, NFL games, or player props. Without
graded, independently usable samples, no probabilities may be recalibrated.
"""
from __future__ import annotations

from pathlib import Path
import math

from v8_forward_calibration_view import read_calibration
from v8_forward_calibration import (
    MIN_PUBLIC_SCORE_BRIER_GAMES, MIN_RESEARCH_ECE_GAMES,
    MIN_BIN_FOR_OBSERVED_RATE,
)

MARKET_KEYS = (
    "nba_moneyline", "nba_point_spread", "nba_total_points",
    "nfl_moneyline", "nfl_point_spread", "nfl_total_points",
    "nba_player_props", "nfl_player_props",
)
UNKNOWN = "NOT_AVAILABLE_NO_VERIFIED_PREGAME_FORECAST_OUTCOME_PAIRS"


def _unavailable_market(market):
    return {
        "market": market,
        "status": UNKNOWN,
        "eligible_original_model_forecasts_graded": None,
        "research_brier_score": None,
        "research_log_loss": None,
        "research_expected_calibration_error": None,
        "calibration_probability_bin_diagnostics": [],
        "estimated_hit_rate": None,
        "calibration_adjusted_probability": None,
        "model_version": None,
        "source_scope": "no_durable_exact_market_original_forecast_and_verified_outcome_evidence",
        "independently_certified": False,
        "bet_ready": False,
    }


def dashboard(calibration_file=None):
    """Do not report '0 games' when the provenance artifact is unavailable."""
    markets = {m: _unavailable_market(m) for m in MARKET_KEYS}
    source = {
        "status": "NOT_YET_PERSISTED",
        "archived_original_forward_forecasts": None,
        "graded_research_NBA_games": None,
        "pending_ungraded": None,
        "quarantined": None,
        "models": [],
    }
    if calibration_file is not None and Path(calibration_file).is_file():
        try:
            source = read_calibration(calibration_file)
        except (ValueError, KeyError, TypeError, OSError):
            source = {
                "status": "REJECTED_INCONSISTENT_OR_UNTRUSTED_CALIBRATION_EVIDENCE",
                "archived_original_forward_forecasts": None,
                "graded_research_NBA_games": None,
                "pending_ungraded": None,
                "quarantined": None,
                "models": [],
            }
    nba = markets["nba_moneyline"]
    nba["source_scope"] = "nba_original_forward_home_win_elo_research_only"
    nba["status"] = source["status"]
    nba["archived_original_forward_forecasts"] = source["archived_original_forward_forecasts"]
    nba["pending_ungraded_original_forecasts"] = source["pending_ungraded"]
    nba["quarantined_original_forecasts"] = source["quarantined"]
    nba["eligible_original_model_forecasts_graded"] = source["graded_research_NBA_games"]
    nba["minimum_forward_games_to_display_exploratory_brier"] = MIN_PUBLIC_SCORE_BRIER_GAMES
    nba["minimum_forward_games_to_display_exploratory_ece"] = MIN_RESEARCH_ECE_GAMES
    nba["minimum_single_probability_bin_for_observed_frequency"] = MIN_BIN_FOR_OBSERVED_RATE
    models = source["models"]
    nba["research_models"] = []
    if type(models) is not list:
        raise ValueError("impossible_calibration_models_schema")
    for m in models:
        n = m["original_forward_pregame_games_graded"]
        brier = m["research_Brier"]
        ece = m["exploratory_expected_calibration_error"]
        loss = m["research_log_loss"]
        if (type(n) is not int or n < 1 or n < MIN_PUBLIC_SCORE_BRIER_GAMES
                and (brier is not None or loss is not None)
                or n < MIN_RESEARCH_ECE_GAMES and ece is not None):
            raise ValueError("calibration_insufficient_original_forward_games")
        if any(v is not None and
               (type(v) not in (int, float) or not math.isfinite(v)
                or v < 0 or (key != "log_loss" and v > 1))
               for key, v in (("brier", brier), ("ece", ece), ("log_loss", loss))):
            raise ValueError("invalid_forward_calibration_metric")
        nba["research_models"].append({
            "model_version": m["model_version"],
            "original_forward_games_graded": n,
            "exploratory_brier": brier,
            "exploratory_log_loss": loss,
            "exploratory_ece": ece,
            "probability_bins": m["fixed_predeclared_probability_bins"],
            "independently_calibrated": False,
        })
    if len(models) == 1:
        m = models[0]
        nba["model_version"] = m["model_version"]
        nba["research_brier_score"] = m["research_Brier"]
        nba["research_log_loss"] = m["research_log_loss"]
        nba["research_expected_calibration_error"] = m["exploratory_expected_calibration_error"]
        nba["calibration_probability_bin_diagnostics"] = m["fixed_predeclared_probability_bins"]
    # No benchmark is allowed to calibrate current SharpAPI event probabilities
    # automatically: originals must be matched on exact market and temporal
    # independence, and original training/calibration must be evaluated OOS.
    return {
        "report_type": "v8_nba_nfl_sharp_edge_calibration_evidence_status",
        "persisted_nba_original_forward_calibration_status": source["status"],
        "nba_original_archived_forecasts": source["archived_original_forward_forecasts"],
        "nba_original_graded_outcomes": source["graded_research_NBA_games"],
        "nba_original_pending_grading": source["pending_ungraded"],
        "nba_original_quarantined": source["quarantined"],
        "minimum_exploratory_brier_graded_games": MIN_PUBLIC_SCORE_BRIER_GAMES,
        "minimum_exploratory_ece_graded_games": MIN_RESEARCH_ECE_GAMES,
        "market_calibration": markets,
        "native_calibration_applied_to_current_sharp_edge_quotes": False,
        "sportsbook_implied_probabilities_are_not_calibration_data": True,
        "independent_event_player_outcome_authentication_performed": False,
        "calibration_certified": False,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
        "stake_usd": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "decision": "HOLD_NO_INDEPENDENTLY_CERTIFIED_EXACT_MARKET_CALIBRATION",
        "warning": (
            "Only original NBA pregame home-win research may be assessed by the "
            "persisted forward calibration file. NBA spreads/totals, all NFL "
            "games and all NBA/NFL player props need their OWN authentic "
            "pregame probability/outcome pairs and market-specific settlement "
            "validation. Research Brier/ECE, if available, do not certify "
            "or automatically recalibrate a current bet, or turn sportsbook "
            "no-vig market price percentages into native model predictions."
        ),
    }
