"""Read-only phone view of persisted V8 forward research leaderboard.

The Git branch is not externally immutable. Models and quoted accuracy
are research summaries of post-event ESPN published finals, not betting
certification. Missing or malformed stored evidence must never make up scores.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

VERSION = "v8-durable-forward-NBA-research-scoreboard-v1"


def _nonnegative_integer(obj, key):
    x = obj.get(key)
    if type(x) is not int or x < 0:
        raise ValueError("invalid_persistent_count_" + key)
    return x


def read_leaderboard(path):
    if path is None:
        return {
            "status": "NOT_YET_PERSISTED",
            "original_archived_forecasts": 0,
            "graded_forward_research_games": 0,
            "pending_48h": 0,
            "research_ranked_models": [],
            "certified_positive_ev_bets": 0,
            "certified_champion_001_shadows": 0,
            "bet_ready": False,
        }
    location = Path(path)
    if not location.is_file():
        return read_leaderboard(None)
    if location.is_symlink() or location.stat().st_size > 1_000_000:
        raise ValueError("unsafe_persisted_scoreboard_file")
    obj = json.loads(location.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("version") != VERSION:
        raise ValueError("unexpected_forward_leaderboard_version")
    if (obj.get("champion_001_modified") is not False
            or obj.get("bet_ready") is not False
            or obj.get("certified_champion_001_shadows") != 0
            or obj.get("certified_v8_probabilities") != 0
            or obj.get("certified_positive_ev_bets") != 0
            or obj.get("independently_verified_checkout_odds") != 0):
        raise ValueError("persisted_research_cannot_be_certified")
    total = _nonnegative_integer(obj, "nba_unique_original_forecasts_archived")
    graded = _nonnegative_integer(obj, "nba_forward_forecasts_graded_research_only")
    pending = _nonnegative_integer(obj, "nba_forecasts_pending_48h")
    holds = _nonnegative_integer(obj, "nba_forecasts_due_without_published_grade")
    quarantined = _nonnegative_integer(obj, "nba_original_forecasts_quarantined")
    if total < graded + pending + holds + quarantined:
        raise ValueError("persistent_forecast_counts_do_not_reconcile")
    models = obj.get("research_only_ranked_models")
    if not isinstance(models, list) or len(models) > 20:
        raise ValueError("invalid_ranked_models")
    versions = set()
    for model in models:
        if not isinstance(model, dict) or model.get("sport") != "nba":
            raise ValueError("unexpected_research_model_league")
        v = model.get("model_version")
        n = model.get("graded_forward_research_games")
        brier = model.get("mean_Brier_lower_is_better")
        if (not isinstance(v, str) or not v or v in versions
                or type(n) is not int or n < 50 or n > graded
                or type(brier) not in (float, int) or not math.isfinite(brier)
                or not 0 <= brier <= 1
                or model.get("research_only_not_certified") is not True
                or model.get("ranking_eligible") is not True
                or model.get("positive_ev_certified") != 0):
            raise ValueError("invalid_research_model_certification_or_score")
        versions.add(v)
    return {
        "status": obj.get("ranking_status"),
        "generated_at_utc": obj.get("generated_at_utc"),
        "original_archived_forecasts": total,
        "graded_forward_research_games": graded,
        "pending_48h": pending,
        "due_without_published_grade": holds,
        "quarantined_event_identities": quarantined,
        "research_ranked_models": models,
        "certified_positive_ev_bets": 0,
        "certified_champion_001_shadows": 0,
        "bet_ready": False,
        "git_branch_is_externally_immutable": False,
    }
