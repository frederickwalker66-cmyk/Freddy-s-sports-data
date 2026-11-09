"""Phone viewer of separate persistent NFL/NHL forward research scorecards.

Never turns saved scores into calibrated sportsbook probabilities or Champion
predictions. Missing branch/data gets explicit NOT_YET_PERSISTED, not zero.
"""
from __future__ import annotations

import json
from pathlib import Path
import math

VERSION="v8-NFL-NHL-durable-forward-v1"
SPORTS=("nfl","nhl")


def _read(sport,src):
    if not src or not Path(src).is_file():
        return {"sport":sport,"status":"NOT_YET_PERSISTED",
                "original_saved_forecasts":None,"graded_research_games":None,
                "pending_48h":None,"research_ranked_models_after_50":[],
                "certified_champion_001_shadows":0,
                "certified_positive_ev_bets":0,"bet_ready":False}
    file=Path(src)
    if file.is_symlink() or file.stat().st_size>2_000_000:
        raise ValueError("invalid_stored_source")
    data=json.loads(file.read_text(encoding="utf-8"))
    if (not isinstance(data,dict) or data.get("version")!=VERSION
            or data.get("sport")!=sport or data.get("champion_001_modified") is not False
            or data.get("certified_champion_001_shadows")!=0
            or data.get("certified_positive_ev_bets")!=0 or data.get("bet_ready") is not False
            or data.get("verified_sportsbook_checkout_quotes")!=0
            or data.get("ESPN_final_is_independently_verified_bookmaker_settlement") is not False):
        raise ValueError("untrusted_or_promoted_persisted_research")
    names=("original_saved_forecasts","pending_48h","graded_research_games",
           "original_game_identity_conflicts_quarantined",
           "unmatched_or_source_missing","published_NFL_ties_excluded")
    nums=[data.get(n) for n in names]
    if any(type(n) is not int or n<0 for n in nums):
        raise ValueError("missing_actual_forecast_count")
    total,pending,graded,conflict,unmatched,ties=nums
    if total != pending+graded+conflict+unmatched+ties:
        raise ValueError("source_research_outcomes_do_not_reconcile")
    models=data.get("research_ranked_models_after_50")
    if not isinstance(models,list) or len(models)>20:
        raise ValueError("unsupported_stored_model_ranking")
    for model in models:
        n=model.get("original_forward_ESPN_games_graded")
        brier=model.get("research_Brier")
        if (model.get("league")!=sport or model.get("rank_eligible_after_50") is not True
                or type(n) is not int or n<50 or n>graded
                or type(brier) not in (float,int)
                or not math.isfinite(brier) or not 0<=brier<=1
                or model.get("model_independently_calibrated") is not False
                or model.get("market_betting_ready") is not False):
            raise ValueError("unverified_research_model_ranking")
    return {
        "sport":sport,"status":data.get("status"),
        "original_saved_forecasts":total,"graded_research_games":graded,
        "pending_48h":pending,"unmatched_or_source_missing":unmatched,
        "NFL_ties_excluded_not_losses":ties,
        "original_conflicts_quarantined":conflict,
        "research_ranked_models_after_50":models,
        "source_Git_branch_independently_immutable":False,
        "certified_champion_001_shadows":0,
        "certified_positive_ev_bets":0,"bet_ready":False,
    }


def read_boards(paths=None):
    paths=paths or {}
    if not isinstance(paths,dict):
        raise ValueError("persisted_research_path_mapping_required")
    return {
        "version":"v8-forward-multi-sport-research-phone-v1",
        "by_sport":{sport:_read(sport,paths.get(sport)) for sport in SPORTS},
        "source":"separate research/nfl-nhl-forward-ledger Git branch",
        "does_not_include_frozen_champion_001":True,
        "sportsbook_checkout_prices_verified":0,
        "certified_champion_001_predictions":0,
        "certified_positive_ev_bets":0,
        "automated_wagers":0,
        "bet_ready":False,
    }
