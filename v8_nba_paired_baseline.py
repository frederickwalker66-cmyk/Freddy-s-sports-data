"""Leakage-guarded retrospective NBA Elo vs rolling-home-prior research check.

Both comparison streams are simulated AFTER past games, not actual timestamped
pregame shadow picks. Results update only 48h after their event start; this
assumed delay is NOT independent proof of when a final was published.
All comparisons are purely exploratory and NOT model or betting certification.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from itertools import groupby
import math
from random import Random
from statistics import mean
from zoneinfo import ZoneInfo

MIN_EVALUATION_GAMES = 30
MIN_BOOTSTRAP_DAYS = 5
SIMULATIONS = 1000
BOOTSTRAP_SEED = 20261109
NY = ZoneInfo("America/New_York")


def _loss(y, p):
    if type(y) is not int or y not in (0, 1) or not isinstance(p, float) or not 0 < p < 1:
        raise ValueError("invalid_retro_probability_or_label")
    return (p-y)**2, -(y*math.log(p)+(1-y)*math.log1p(-p))


def rolling_home_prior(games, embargo_hours=48):
    """Replay an evolving home-win baseline using only presumed matured finals.

    Simultaneous starts share exactly the same prior and are only updated after
    later events. Laplace prior Beta(1,1) avoids unseen future mean leakage.
    """
    if type(embargo_hours) is not int or embargo_hours < 24:
        raise ValueError("invalid_minimum_result_embargo")
    pending = []
    seen = 0
    home_wins = 0
    result = []
    for started, group in groupby(games, key=lambda g:g[0]):
        matured = [item for item in pending if item[0] <= started]
        pending = [item for item in pending if item[0] > started]
        for _, y in matured:
            seen += 1
            home_wins += y
        probability = (home_wins+1)/(seen+2)
        for _, event_id, home, away, y in group:
            if y not in (0,1):
                raise ValueError("only_binary_NBA_final")
            result.append(probability)
            pending.append((started+timedelta(hours=embargo_hours),y))
    return result


def compare(games, elo_replay, warmup=80, minimum=MIN_EVALUATION_GAMES):
    if (not isinstance(games, list) or not isinstance(elo_replay, list)
            or len(games) != len(elo_replay)):
        raise ValueError("NBA_elo_replay_length_mismatch")
    if type(warmup) is not int or warmup < 1 or type(minimum) is not int or minimum < 1:
        raise ValueError("invalid_evaluation_thresholds")
    rolling = rolling_home_prior(games)
    paired = []
    for (date, eid, home, away, y),(p_elo, y2, recorded),prior in zip(
            games,elo_replay,rolling):
        if y != y2 or date.isoformat() != recorded:
            raise ValueError("forecast_alignment_failure")
        elo_brier, elo_logloss = _loss(y, float(p_elo))
        prior_brier, prior_logloss = _loss(y, float(prior))
        paired.append({
            "event_id":eid,
            "event_start_utc":date.isoformat(),
            "home_win_prior_reconstructed_after_game":round(prior,9),
            "date_et":date.astimezone(NY).date().isoformat(),
            "elo_brier":elo_brier,
            "rolling_prior_brier":prior_brier,
            "elo_logloss":elo_logloss,
            "rolling_prior_logloss":prior_logloss,
            "paired_brier_improvement":prior_brier-elo_brier,
            "paired_logloss_improvement":prior_logloss-elo_logloss,
            "historical_forecast_actually_recorded_before_tipoff":False,
        })
    evaluation = paired[warmup:]
    enough = len(evaluation) >= minimum
    summary = {
        "version":"v8-NBA-retrospective-paired-baseline-v1",
        "baseline":"Laplace_smoothed_rolling_home_win_rate_with_48h_assumed_publication_delay",
        "reconstructed_history_events":len(games),
        "warmup_events":min(warmup,len(games)),
        "later_reconstructed_evaluation_events":len(evaluation),
        "retrospective_only":True,
        "scores_available":enough,
        "rolling_home_win_baseline_brier":None,
        "rolling_home_win_baseline_logloss":None,
        "elo_brier_unrounded":None,
        "elo_logloss_unrounded":None,
        "elo_minus_rolling_baseline_brier_improvement":None,
        "elo_minus_rolling_baseline_logloss_improvement":None,
        "approximate_paired_day_bootstrap_brier_improvement_95pct_CI":None,
        "elo_beat_rolling_prior_with_exploratory_day_interval":False,
        "bootstrap_days":0,
        "bootstrap_iterations":0,
        "real_pregame_receipts":0,
        "independently_authenticated_final_publication_times":False,
        "independently_certified_model":False,
        "certified_predictions":0,
        "bet_ready":False,
        "champion_001_modified":False,
        "warning":(
            "Fixed Elo and rolling prior both reconstructed after games using "
            "only presumed 48h-matured results. Paired day bootstrap is "
            "exploratory, does not certify model skill, and ignores data "
            "selection/source error; no real pregame receipts, sportsbook "
            "checkout prices, or proven expected value.")
    }
    if not enough:
        return summary, paired
    for field, key in (
        ("rolling_home_win_baseline_brier","rolling_prior_brier"),
        ("rolling_home_win_baseline_logloss","rolling_prior_logloss"),
        ("elo_brier_unrounded","elo_brier"),
        ("elo_logloss_unrounded","elo_logloss"),
        ("elo_minus_rolling_baseline_brier_improvement","paired_brier_improvement"),
        ("elo_minus_rolling_baseline_logloss_improvement","paired_logloss_improvement"),
    ):
        summary[field]=round(mean(x[key] for x in evaluation),9)
    by_day=defaultdict(list)
    for item in evaluation:
        by_day[item["date_et"]].append(item["paired_brier_improvement"])
    summary["bootstrap_days"]=len(by_day)
    if len(by_day)>=MIN_BOOTSTRAP_DAYS:
        clusters=[by_day[day] for day in sorted(by_day)]
        rng=Random(BOOTSTRAP_SEED)
        simulated=[]
        for _ in range(SIMULATIONS):
            picked=[clusters[rng.randrange(len(clusters))] for __ in clusters]
            values=[x for day in picked for x in day]
            simulated.append(sum(values)/len(values))
        simulated.sort()
        lo=simulated[int(.025*len(simulated))]
        hi=simulated[int(.975*len(simulated))-1]
        summary["bootstrap_iterations"]=SIMULATIONS
        summary["approximate_paired_day_bootstrap_brier_improvement_95pct_CI"]=[
            round(lo,9),round(hi,9)]
        summary["elo_beat_rolling_prior_with_exploratory_day_interval"]=lo>0
    return summary, paired
