"""Calibration diagnostics for EXISTING genuinely forward-recorded NBA V8 research.

Read only the SQLite database from the persistent NBA research ledger.
The original forecast is never changed. Grade provenance must have been
recorded no earlier than 48 hours after tipoff. Five bins are fixed in
advance (NOT fit on future outcomes). Small-sample calibration and
confidence intervals are withheld, not fabricated.

Not Champion-001; does NOT certify market value, betting EV, original
publisher custody, or independent model calibration at any sample size.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite, log, log1p, sqrt
from pathlib import Path
from random import Random
import json
import sqlite3

from historical_outcomes import parse_time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
VERSION = "v8-nba-forward-calibration-v1"
BIN_WIDTH = 0.20
BIN_COUNT = 5
MIN_PUBLIC_SCORE_BRIER_GAMES = 50
MIN_RESEARCH_ECE_GAMES = 100
MIN_BIN_FOR_OBSERVED_RATE = 20
MIN_BIN_FOR_ECE = 10
MIN_CLUSTER_DAYS = 10
BOOTSTRAP_RUNS = 1000
RANDOM_SEED = 20261109


def _p(value):
    if type(value) not in (int, float) or not isfinite(value) or not 0 < value < 1:
        raise ValueError("invalid_original_forward_probability")
    return float(value)


def _ts(value):
    return parse_time(value)


def _wilson(wins, n):
    """Wilson 95% interval; useful as a descriptive, not certainty measure."""
    if type(wins) is not int or type(n) is not int or not 0 <= wins <= n or n < 1:
        raise ValueError("invalid_bin_frequency")
    z = 1.959963984540054
    phat = wins / n
    d = 1 + z*z/n
    mid = (phat + z*z/(2*n))/d
    delta = (z/d)*sqrt(phat*(1-phat)/n + z*z/(4*n*n))
    return [round(max(0, mid-delta), 5), round(min(1, mid+delta), 5)]


def load_original_pairs(dbfile):
    """Fail closed on any inconsistent saved original forecast and later final."""
    path = Path(dbfile)
    if not path.is_file() or path.is_symlink():
        raise ValueError("persistent_original_forecast_database_missing")
    if path.stat().st_size > 150_000_000:
        raise ValueError("persistent_score_database_exceeds_budget")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("persistent_score_database_integrity_failed")
        if conn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("unsupported_persistent_forecast_database_version")
        rows = conn.execute("""
            SELECT f.espn_event_id, f.model_version, f.original_forecast_utc,
                f.original_tipoff_utc, f.original_p_home, f.original_run_id,
                f.original_record_json, f.quarantined, o.home_won,
                o.espn_published_home_score, o.espn_published_away_score,
                o.source_retrieved_at_utc, o.first_graded_at_utc
            FROM nba_forward_forecasts AS f
            LEFT JOIN nba_published_outcomes AS o ON f.espn_event_id=o.espn_event_id
            ORDER BY f.original_tipoff_utc, f.espn_event_id
        """).fetchall()
    finally:
        conn.close()
    if len(rows) > 200_000:
        raise ValueError("persistent_forecast_row_budget_exceeded")
    counted = dict(archived=len(rows), quarantined=0, pending_ungraded=0,
                   completed=0)
    paired = []
    for (eid, model, forecast_at, tipoff, probability, run, raw, quarantine,
         outcome, home, away, published_at, graded_at) in rows:
        original = json.loads(raw)
        p = _p(probability)
        started = _ts(tipoff)
        stamped = _ts(forecast_at)
        if (not isinstance(eid, str) or not eid.isdecimal()
                or type(model) is not str or not model.startswith("v8-nba-elo-forward-research")
                or type(run) is not int or run <= 0
                or not stamped < started
                or not isinstance(original, dict)
                or original.get("espn_event_id") != eid
                or original.get("model_version") != model
                or original.get("league") != "nba"
                or _ts(original.get("start_utc")) != started
                or _ts(original.get("forecast_recorded_utc")) != stamped
                or original.get("model_probability_home_win_research_only") != p
                or original.get("champion_001_modified") is not False
                or original.get("certified_prediction") is not False
                or original.get("qualifies_for_original_champion_shadow_quota") is not False
                or original.get("stake_usd") != 0):
            raise ValueError("stored_forecast_lost_first_original_research_provenance")
        if quarantine not in (0, 1):
            raise ValueError("invalid_original_forecast_quarantine")
        if quarantine:
            counted["quarantined"] += 1
            continue
        if outcome is None:
            counted["pending_ungraded"] += 1
            continue
        if (type(outcome) is not int or outcome not in (0,1)
                or type(home) is not int or type(away) is not int
                or not 0 <= home <= 999 or not 0 <= away <= 999
                or home == away or int(home > away) != outcome):
            raise ValueError("contradictory_published_outcome")
        published = _ts(published_at)
        graded = _ts(graded_at)
        if not (started < published <= graded
                and started + timedelta(hours=48) <= graded):
            raise ValueError("outcome_published_or_graded_before_allowed_maturity")
        counted["completed"] += 1
        paired.append({
            "id": eid,
            "version": model,
            "p": p,
            "y": outcome,
            "start": started,
            "date_et": started.astimezone(NY).date().isoformat(),
        })
    if sum(counted[k] for k in ("quarantined","pending_ungraded","completed")) != counted["archived"]:
        raise ValueError("original_forecast_and_final_counts_disagree")
    return paired, counted


def calibrate(pairs, totals):
    if not isinstance(pairs, list) or not isinstance(totals, dict):
        raise ValueError("real_original_forecast_pairs_and_counts_required")
    names = sorted({r["version"] for r in pairs})
    models = []
    for version in names:
        all_rows = [row for row in pairs if row["version"] == version]
        n = len(all_rows)
        buckets = [[] for _ in range(BIN_COUNT)]
        day_clusters = defaultdict(list)
        for row in all_rows:
            p = _p(row["p"])
            y = row["y"]
            if type(y) is not int or y not in (0,1):
                raise ValueError("nonbinary_NBA_public_final")
            index = min(BIN_COUNT-1, int(p / BIN_WIDTH))
            buckets[index].append((p,y))
            day_clusters[row["date_et"]].append((p,y))
        bin_rows = []
        ece = 0
        can_ece = n >= MIN_RESEARCH_ECE_GAMES
        for idx, bucket in enumerate(buckets):
            ct = len(bucket)
            wins = sum(y for p,y in bucket)
            mean_p = sum(p for p,y in bucket) / ct if ct else None
            empirical = wins/ct if ct else None
            if ct and ct < MIN_BIN_FOR_ECE:
                can_ece = False
            if ct:
                ece += ct/n * abs(empirical-mean_p)
            bin_rows.append({
                "probability_min_inclusive": round(idx*BIN_WIDTH,2),
                "probability_max_exclusive": round((idx+1)*BIN_WIDTH,2),
                "observations":ct,
                "home_wins":wins,
                "mean_original_forecast_probability":round(mean_p,7) if ct else None,
                "observed_home_win_frequency":(
                    round(empirical,7) if ct >= MIN_BIN_FOR_OBSERVED_RATE else None),
                "wilson_95pct_descriptive_interval":(
                    _wilson(wins,ct) if ct >= MIN_BIN_FOR_OBSERVED_RATE else None),
                "withheld_small_bin":0 < ct < MIN_BIN_FOR_OBSERVED_RATE,
            })
        active = n >= MIN_PUBLIC_SCORE_BRIER_GAMES
        # Classification and neutral-reference skill are descriptive ONLY and
        # follow the same 50-grade minimum as Brier/log-loss. There is no
        # sportsbook comparison or original Champion calibration here.
        decisions = [(row["p"], row["y"]) for row in all_rows if row["p"] != .5]
        correct = sum(int((p > .5) == bool(y)) for p, y in decisions)
        directional_accuracy = correct / len(decisions) if decisions else None
        brier = (sum((row["p"]-row["y"])**2 for row in all_rows) / n) if n else None
        loss = (sum(-(row["y"]*log(row["p"])+(1-row["y"])*log1p(-row["p"])) for row in all_rows) / n) if n else None
        metric_ci = None
        if active and len(day_clusters) >= MIN_CLUSTER_DAYS:
            clusters=[day_clusters[d] for d in sorted(day_clusters)]
            rand=Random(RANDOM_SEED)
            boot=[]
            for _ in range(BOOTSTRAP_RUNS):
                selected=[clusters[rand.randrange(len(clusters))] for __ in clusters]
                samples=[(p,y) for day in selected for p,y in day]
                boot.append(sum((p-y)**2 for p,y in samples)/len(samples))
            boot.sort()
            metric_ci=[round(boot[25],7),round(boot[974],7)]
        models.append({
            "model_version":version,
            "original_forward_pregame_games_graded":n,
            "minimum_games_for_exploratory_Brier":MIN_PUBLIC_SCORE_BRIER_GAMES,
            "minimum_games_for_exploratory_ECE":MIN_RESEARCH_ECE_GAMES,
            "minimum_bin_size_for_observed_rate":MIN_BIN_FOR_OBSERVED_RATE,
            "fixed_predeclared_probability_bins":bin_rows,
            "research_Brier":round(brier,7) if active else None,
            "research_log_loss":round(loss,7) if active else None,
            "neutral_50_50_Brier_NOT_sportsbook": .25 if active else None,
            "neutral_50_50_log_loss_NOT_sportsbook": round(log(2),7) if active else None,
            "research_directional_decisions": len(decisions),
            "research_directional_correct": correct,
            "research_directional_accuracy": (
                round(directional_accuracy,7) if active and decisions else None),
            "research_directional_accuracy_wilson_95pct": (
                _wilson(correct,len(decisions)) if active and decisions else None),
            "research_Brier_skill_vs_fixed_50_50_NOT_sportsbook": (
                round(1-brier/.25,7) if active else None),
            "research_log_loss_skill_vs_fixed_50_50_NOT_sportsbook": (
                round(1-loss/log(2),7) if active else None),
            "day_cluster_bootstrap_approximate_Brier_95pct_CI":metric_ci,
            "exploratory_expected_calibration_error":round(ece,7) if can_ece else None,
            "retained_uncertainty_not_certification":True,
            "independent_model_calibration_certified":False,
            "model_betting_ready":False,
        })
    summary = {
        "version": VERSION,
        "stage":"genuinely_forward_recorded_NBA_research_calibration_only",
        "status":(
            "EXPLORATORY_BINNED_CALIBRATION_AVAILABLE_NOT_CERTIFIED"
            if any(x["exploratory_expected_calibration_error"] is not None for x in models)
            else "HOLD_WAITING_FOR_100_FORWARD_GRADED_AND_WELL_POPULATED_BINS"),
        "archived_original_forward_forecasts":totals["archived"],
        "graded_research_NBA_games":totals["completed"],
        "pending_ungraded":totals["pending_ungraded"],
        "quarantined":totals["quarantined"],
        "minimum_forward_graded_games_for_initial_research_metrics":MIN_PUBLIC_SCORE_BRIER_GAMES,
        "minimum_forward_graded_games_for_exploratory_calibration":MIN_RESEARCH_ECE_GAMES,
        "models":models,
        "data_is_independently_publisher_authenticated":False,
        "ESPN_published_final_is_official_bet_settlement":False,
        "original_Champion_001_executable_authenticated":False,
        "original_Champion_001_certified_shadows":0,
        "independently_certified_models":0,
        "independently_verified_sportsbook_checkout_quotes":0,
        "certified_positive_ev_bets":0,
        "automatic_wagers":0,
        "champion_001_modified":False,
        "bet_ready":False,
        "warning":(
            "Forecasts are original research probabilities archived before "
            "tipoff; later ESPN results are provisional. Brier/log-loss are "
            "withheld for fewer than 50 graded forward games and bin frequencies "
            "for fewer than 20 observations; ECE is withheld until >=100 "
            "games AND >=10 observations in every occupied bin. Research "
            "directional accuracy and skill versus a fixed 50/50 reference "
            "also require 50 grades; neither is a sportsbook comparison. No statistics "
            "here validate future profits, original Champion-001, or book prices."),
    }
    return summary


def build_from_database(dbfile, output):
    pairs, totals=load_original_pairs(dbfile)
    report=calibrate(pairs,totals)
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database",required=True)
    ap.add_argument("--output",default="data/v8_forward/CALIBRATION.json")
    args=ap.parse_args()
    result=build_from_database(args.database,args.output)
    print(json.dumps({
        "status":result["status"],
        "graded_games":result["graded_research_NBA_games"],
        "models":len(result["models"]),
        "certified_positive_ev_bets":0,
    },sort_keys=True))
