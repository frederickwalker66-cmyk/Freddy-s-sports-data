"""Strict read-only smartphone view of persisted forward NBA research calibration."""
from __future__ import annotations

import json
import math
from pathlib import Path

from v8_forward_calibration import (
    BIN_COUNT, MIN_BIN_FOR_OBSERVED_RATE, MIN_RESEARCH_ECE_GAMES,
    MIN_PUBLIC_SCORE_BRIER_GAMES, VERSION,
)


def read_calibration(path):
    missing = {
        "status": "NOT_YET_PERSISTED",
        "graded_research_NBA_games": None,
        "archived_original_forward_forecasts": None,
        "pending_ungraded": None,
        "models": [],
        "certified_positive_ev_bets": 0,
        "original_Champion_001_certified_shadows": 0,
        "bet_ready": False,
    }
    if path is None or not Path(path).is_file():
        return missing
    file = Path(path)
    if file.is_symlink() or file.stat().st_size > 2_000_000:
        raise ValueError("unsafe_persistent_calibration_file")
    data = json.loads(file.read_text(encoding="utf-8"))
    if (not isinstance(data,dict) or data.get("version") != VERSION
            or data.get("stage") != "genuinely_forward_recorded_NBA_research_calibration_only"
            or data.get("champion_001_modified") is not False
            or data.get("bet_ready") is not False
            or data.get("original_Champion_001_certified_shadows") != 0
            or data.get("certified_positive_ev_bets") != 0
            or data.get("independently_certified_models") != 0
            or data.get("independently_verified_sportsbook_checkout_quotes") != 0
            or data.get("data_is_independently_publisher_authenticated") is not False):
        raise ValueError("persisted_calibration_must_be_original_untested_research")
    keys = ("archived_original_forward_forecasts", "graded_research_NBA_games",
            "pending_ungraded", "quarantined")
    counts = [data.get(k) for k in keys]
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("missing_or_invalid_original_forward_counts")
    if counts[0] != sum(counts[1:]):
        raise ValueError("forward_calibration_counts_do_not_reconcile")
    models = data.get("models")
    if not isinstance(models,list) or len(models) > 25:
        raise ValueError("unsupported_NBA_calibration_models")
    total = 0
    names = set()
    for model in models:
        if not isinstance(model,dict):
            raise ValueError("unsupported_NBA_calibration_model_row")
        name = model.get("model_version")
        n = model.get("original_forward_pregame_games_graded")
        if (not isinstance(name,str) or not name or name in names
                or type(n) is not int or n < 1
                or model.get("independent_model_calibration_certified") is not False
                or model.get("model_betting_ready") is not False):
            raise ValueError("unreviewed_model_or_calibration_result")
        names.add(name)
        total += n
        bins = model.get("fixed_predeclared_probability_bins")
        if not isinstance(bins,list) or len(bins) != BIN_COUNT:
            raise ValueError("original_probability_bins_missing")
        bsum=0
        for index, b in enumerate(bins):
            if (not isinstance(b,dict)
                    or b.get("probability_min_inclusive") != round(.2*index,2)
                    or b.get("probability_max_exclusive") != round(.2*(index+1),2)):
                raise ValueError("non_predeclared_probability_bucket")
            k = b.get("observations")
            wins = b.get("home_wins")
            if (type(k) is not int or k < 0 or type(wins) is not int
                    or not 0 <= wins <= k):
                raise ValueError("invalid_calibration_bucket_observations")
            if k < MIN_BIN_FOR_OBSERVED_RATE and b.get("observed_home_win_frequency") is not None:
                raise ValueError("small_bin_frequency_prematurely_released")
            bsum += k
        if bsum != n:
            raise ValueError("model_game_and_bin_counts_disagree")
        brier = model.get("research_Brier")
        ece = model.get("exploratory_expected_calibration_error")
        if (n < MIN_PUBLIC_SCORE_BRIER_GAMES and brier is not None
                or n < MIN_RESEARCH_ECE_GAMES and ece is not None):
            raise ValueError("too_few_forward_games_for_calibration_metrics")
        for value in (brier,ece):
            if value is not None and (type(value) not in (int,float)
                                       or not math.isfinite(value)
                                       or not 0<=value<=1):
                raise ValueError("invalid_calibration_statistic")
    if total != counts[1]:
        raise ValueError("model_grade_total_does_not_equal_saved_grades")
    return {
        "status":data.get("status"),
        "graded_research_NBA_games": counts[1],
        "archived_original_forward_forecasts":counts[0],
        "pending_ungraded":counts[2],
        "quarantined":counts[3],
        "minimum_Brier_games":MIN_PUBLIC_SCORE_BRIER_GAMES,
        "minimum_exploratory_calibration_games":MIN_RESEARCH_ECE_GAMES,
        "models":models,
        "certified_positive_ev_bets":0,
        "original_Champion_001_certified_shadows":0,
        "bet_ready":False,
    }
