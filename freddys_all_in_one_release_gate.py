"""One-shot read-only research release gate for Freddy's Picks AI.

Runs original source inventory, external NBA/seven-league admissions, exact
chronological train/holdout, (optional) research-only native fitting,
first-observed forward NBA/NFL/NHL grading, and primary-checkout witness
research reconciliation. Never modifies Champion-001, repository branches,
original research archives or makes any real-money bet.

No internal artifact, self-issued digest, URL or unsigned review flag can
independently authenticate a source or sportsbook checkout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from collections import Counter

from challenger_authenticated_chronological_dataset import (
    build as admit_non_nba, canon, key_from_path, read_jsonl,
    write_output as write_seven_league_evidence)
from challenger_multisport_native_training import train as train_non_nba
from challenger_nba_independent_source_admission import (
    build as admit_nba, save as save_nba_evidence)
from challenger_nba_probability import train_engine as train_nba
from nba_actual_original_source_inventory import audit_archives
from v8_external_price_receipt_audit import reconcile as reconcile_checkout
from v8_forward_leaderboard_view import read_leaderboard
from v8_durable_forward_ledger import sync as refresh_nba_forward
from v8_nfl_nhl_durable_ledger import sync as refresh_nfl_nhl_forward

VERSION = "freddys-all-in-one-independent-release-gate-v1"
LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league")
DIRECT_CHECKOUT_CERTIFICATIONS = 0
MIN_TRAIN = 200
MIN_HOLDOUT = 50


def _write(path, value):
    loc=Path(path)
    loc.parent.mkdir(parents=True,exist_ok=True)
    loc.write_bytes(canon(value)+b"\n")


def _report_clock(now):
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("all_in_one_requires_timezone_aware_now")
    return now.astimezone(timezone.utc)


def _copy_ledger(src, dest):
    src=Path(src)
    if src.is_symlink() or not src.is_dir():
        raise ValueError("unsafe_or_missing_original_research_ledger")
    dest=Path(dest)
    if dest.exists():
        raise FileExistsError("output_ledger_must_be_new_and_disjoint_from_original")
    if dest.resolve().is_relative_to(src.resolve()) or src.resolve().is_relative_to(dest.resolve()):
        raise ValueError("research_and_output_paths_must_be_disjoint")
    shutil.copytree(src,dest,symlinks=False)
    return dest


def _independent_nba_history(rows, keys, evidence_root, outdir, now):
    pre, final = keys
    prekey = key_from_path(pre) if pre else None
    fin_key = key_from_path(final) if final else None
    admission, groups=admit_nba(rows,evidence_root,prekey,fin_key,now)
    save_nba_evidence(Path(outdir)/"historical"/"nba",admission,groups)
    model=None
    if groups is not None:
        # The exact externally-witnessed holdout identities must survive
        # intact; do not use a trainer-created percentage split.
        combined=groups["train"]+groups["holdout"]
        ids=[r["event_id"] for r in groups["holdout"]]
        result,model=train_nba(combined,as_of=now,sealed_holdout_ids=ids)
        if result["chronological_train_games"]<MIN_TRAIN or result["chronological_holdout_games"]<MIN_HOLDOUT:
            raise ValueError("nba_model_trainer_unexpectedly_accepts_unqualified_split")
    else:
        result,model=train_nba([],as_of=now)
    result["externally_witnessed_admission_status"]=admission["status"]
    result["source_witness_custody_externally_approved"]=False
    result["model_release_approved"]=False
    _write(Path(outdir)/"historical"/"nba"/"trainer_research_report.json",result)
    if model is not None:
        _write(Path(outdir)/"historical"/"nba"/"UNVERIFIED_RESEARCH_MODEL.json",model)
    return admission,result,model is not None


def _independent_seven_league_history(rows, keys, evidence_root, outdir, now):
    pre, final=keys
    prekey=key_from_path(pre) if pre else None
    fin_key=key_from_path(final) if final else None
    admission, groups=admit_non_nba(rows,evidence_root,prekey,fin_key,now)
    root=Path(outdir)/"historical"/"other_leagues"
    write_seven_league_evidence(root,admission,groups)
    eligible=[r for league in sorted(groups)
              for part in ("train","holdout")
              for r in groups[league][part]]
    fit_report,models=train_non_nba(eligible,now=now)
    fit_report["source_witness_custody_externally_approved"]=False
    fit_report["model_release_approved"]=False
    _write(root/"trainer_research_report.json",fit_report)
    for league,model in models.items():
        _write(root/"UNVERIFIED_MODELS"/(league+".json"),model)
    return admission,fit_report,sorted(models)


def _nba_market_side_research(original_root, valid_review_rows):
    """Map only real checked original NBA Elo forecasts to research markets.

    Never use NFL conditional no-tie or NHL unverified OT/SO model as a
    bookmaker moneyline. Market sides below remain uncertified.
    """
    approved={r["espn_event_id"]:r for r in valid_review_rows}
    if not approved or not Path(original_root).is_dir():
        return []
    first={}
    for run in sorted(Path(original_root).iterdir()):
        if not run.is_dir() or run.is_symlink() or not run.name.isdigit():
            continue
        p=run/"nba_forward"/"NBA_FORWARD_FORECASTS.jsonl"
        if not p.is_file() or p.is_symlink() or p.stat().st_size>10_000_000:
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r=json.loads(line)
            eid=r.get("espn_event_id")
            witness=approved.get(eid)
            if witness is None:
                continue
            if (witness["original_github_run_id"]!=int(run.name)
                or witness["first_observed_forecast_utc"]!=r.get("forecast_recorded_utc")
                or witness["event_start_utc"]!=r.get("start_utc")
                or witness["model_version"]!=r.get("model_version")
                or witness["original_schedule_sha256"]!=r.get("schedule_original_sha256_local_receipt")):
                continue
            p_home=r.get("model_probability_home_win_research_only")
            if type(p_home) not in (float,int) or not 0<p_home<1:
                raise ValueError("invalid_original_forward_probability")
            for side,prob in (("home",float(p_home)),("away",1-float(p_home))):
                row={
                    "league":"nba","event_id":eid,"market_type":"moneyline",
                    "selection":side,"line":None,"settlement_scope":"including_overtime",
                    "start_utc":r["start_utc"],"forecast_utc":r["forecast_recorded_utc"],
                    "model_version":r["model_version"],"model_probability":prob,
                    "research_only":True,"certified_prediction":False,
                    "bet_ready":False,"champion_001_modified":False,
                }
                key=(eid,side)
                previous=first.get(key)
                if previous is None or row["forecast_utc"]<previous["forecast_utc"]:
                    first[key]=row
    return sorted(first.values(),key=lambda r:(r["start_utc"],r["event_id"],r["selection"]))


def _refresh_nba_ledger(source, outdir, now, enabled):
    path=Path(source) if source is not None else None
    if path is None or not path.is_dir():
        return {"status":"NO_PERSISTED_NBA_FORWARD_LEDGER","original_forecasts":0,
                "graded":0,"pending":0,"research_only":True}
    original=read_leaderboard(path/"LEADERBOARD.json")
    if original["status"]=="NOT_YET_PERSISTED":
        raise ValueError("persisted_nba_forward_ledger_missing_scorecard")
    if enabled:
        dest=_copy_ledger(path,Path(outdir)/"forward"/"nba")
        board,_=refresh_nba_forward(dest/"original_run_receipts",dest,now=now)
        if (board["certified_positive_ev_bets"]!=0 or
            board["certified_champion_001_shadows"]!=0 or
            board["bet_ready"] is not False):
            raise ValueError("forward_research_certification_not_authorized")
        return {
            "status":board["ranking_status"],"original_forecasts":board["nba_unique_original_forecasts_archived"],
            "graded":board["nba_forward_forecasts_graded_research_only"],
            "pending":board["nba_forecasts_pending_48h"],
            "due_without_published_grade":board["nba_forecasts_due_without_published_grade"],
            "original_ledger_not_mutated":True,"research_only":True,
            "calibration_status":board["forward_calibration_status"],
            "new_provisional_scores":board["new_forecast_sync"]["new_ESPN_published_outcomes_recorded"],
        }
    return {"status":original["status"],"original_forecasts":original["original_archived_forecasts"],
            "graded":original["graded_forward_research_games"],"pending":original["pending_48h"],
            "due_without_published_grade":original["due_without_published_grade"],
            "original_ledger_not_mutated":True,"research_only":True,
            "new_provisional_scores":0}


def _refresh_other_league(league, research_root, outdir, now, enabled):
    root=Path(research_root) if research_root is not None else None
    src=root/league if root is not None else None
    if src is None or not src.is_dir():
        return {"status":"NO_PERSISTED_"+league.upper()+"_FORWARD_LEDGER",
                "original_forecasts":0,"graded":0,"research_only":True}
    header=src/"FORWARD_RESEARCH_LEADERBOARD.json"
    if not header.is_file():
        raise ValueError("missing_original_"+league+"_scoreboard")
    before=json.loads(header.read_text(encoding="utf-8"))
    if (before.get("champion_001_modified") is not False or
            before.get("certified_positive_ev_bets")!=0 or
            before.get("bet_ready") is not False):
        raise ValueError("untrusted_saved_"+league+"_ledger")
    if enabled:
        dest=_copy_ledger(src,Path(outdir)/"forward"/league)
        incoming=Path(outdir)/"temporary_forward_original_inputs"
        incoming.mkdir(parents=True,exist_ok=True)
        archive=incoming/league
        if archive.exists():
            raise ValueError("duplicate_research_incoming_archive")
        shutil.copytree(src/"original_source_receipts",archive)
        board,_=refresh_nfl_nhl_forward(league,incoming,dest,now=now)
    else:
        board=before
    if (board.get("champion_001_modified") is not False or
            board.get("certified_positive_ev_bets")!=0 or
            board.get("bet_ready") is not False):
        raise ValueError("research_forward_promoted_without_corroboration")
    return {
        "status":board.get("ranking_status") or board.get("status"),
        "original_forecasts":board["original_saved_forecasts"],
        "graded":board["graded_research_games"],
        "pending":board["pending_48h"],
        "original_ledger_not_mutated":True,
        "research_only":True,"NFL_ties_excluded":board.get("published_NFL_ties_excluded",0),
    }


def build_release(
    *, nba_research=None, other_research=None, live_run_metadata=None,
    nba_candidates=None, other_candidates=None, historical_original_root=None,
    pregame_public_key=None, final_public_key=None,
    other_pregame_public_key=None, other_final_public_key=None,
    quote_candidates=None, checkout_original_root=None,
    checkout_public_key=None, output_dir, now=None,
    refresh_forward=False,
):
    clock=_report_clock(now or datetime.now(timezone.utc))
    dest=Path(output_dir)
    if dest.exists():
        if not dest.is_dir() or dest.is_symlink() or any(dest.iterdir()):
            raise ValueError("output_dir_must_be_new_or_empty")
    else:
        dest.mkdir(parents=True)
    original_root=Path(nba_research)/"original_run_receipts" if nba_research else Path("MISSING_ORIGINAL_NBA")
    reviewed,original_inventory=audit_archives(original_root,live_run_metadata)
    _write(dest/"original_nba_source_inventory.json",original_inventory)
    source_path=dest/"original_nba_review_rows.jsonl"
    source_path.write_bytes(b"".join(canon(x)+b"\n" for x in reviewed))
    nba_history, nba_fit, nba_has_model=_independent_nba_history(
        read_jsonl(nba_candidates), (pregame_public_key, final_public_key),
        historical_original_root or "unprovided_original_evidence",dest,clock)
    all_history, seven_fit, models=_independent_seven_league_history(
        read_jsonl(other_candidates),(other_pregame_public_key,other_final_public_key),
        historical_original_root or "unprovided_original_evidence",dest,clock)
    nba_forward=_refresh_nba_ledger(nba_research, dest, clock, refresh_forward)
    nfl_forward=_refresh_other_league("nfl",other_research,dest,clock,refresh_forward)
    nhl_forward=_refresh_other_league("nhl",other_research,dest,clock,refresh_forward)
    archived_markets=_nba_market_side_research(original_root,reviewed)
    _write(dest/"nba_first_research_model_market_sides.json",{
        "original_nba_games":len(reviewed),
        "research_sides":len(archived_markets),
        "markets_are_not_certified_probabilities":True,
        "first_observed_research_only":True,
    })
    quote_key=key_from_path(checkout_public_key) if checkout_public_key else None
    price=reconcile_checkout(archived_markets,read_jsonl(quote_candidates),
                             checkout_original_root or "unprovided_checkout_originals",
                             quote_key,now=clock)
    _write(dest/"exact_market_price_witness_research_audit.json",price)
    blocked=[
        "original_Champion_001_executable_not_independently_authenticated",
        "pre_event_feature_publication_and_custodian_not_independently_vetted",
        "200_chronological_NBA_games_and_50_external_WORM_holdout_not_independently_qualified",
        "fitted_model_not_independently_calibrated_in_live_forward_testing",
        "sportsbook_direct_executable_checkout_not_independently_verified",
    ]
    if original_inventory["unique_nba_first_original_research_forecasts_reviewable"]==0:
        blocked.append("no_actual_pregame_forward_original_source_receipts_recovered")
    if not nba_has_model:
        blocked.append("native_NBA_training_model_not_eligible")
    if not models:
        blocked.append("non_NBA_native_league_training_models_not_eligible")
    if not refresh_forward:
        blocked.append("forward_grading_not_refreshed_in_this_run")
    if nba_forward["graded"]<50:
        blocked.append("NBA_original_forward_research_graded_sample_below_50")
    for league,report in (("nfl",nfl_forward),("nhl",nhl_forward)):
        if report["graded"]<50:
            blocked.append(league+"_original_forward_research_graded_sample_below_50")
    counts={"nba_original_research_games_reviewed":len(reviewed),
            "nba_chronological_training_games_externally_witnessed":nba_history["chronological_training_games"],
            "nba_untouched_later_holdout_games_externally_witnessed":nba_history["untouched_holdout_games"],
            "nba_historical_independently_released_games":0,
            "other_leagues_with_200_training_50_holdout_research_splits":len(
                all_history.get("externally_witnessed_leagues_meeting_200_50",[])),
            "nba_original_graded_research_forecasts":nba_forward["graded"],
            "nfl_original_graded_research_forecasts":nfl_forward["graded"],
            "nhl_original_graded_research_forecasts":nhl_forward["graded"],
            "nba_markets_first_research_sides":len(archived_markets),
            "direct_executable_DraftKings_quotes_certified":DIRECT_CHECKOUT_CERTIFICATIONS,
            "original_Champion_001_certified_predictions":0,
            "native_Challenger_certified_predictions":0,
            "certified_positive_EV_bets":0,"automated_wagers_placed":0}
    report={
        "version":VERSION,"as_of_utc":clock.isoformat(),
        "status":"HOLD_NO_INDEPENDENT_MODEL_OR_EXECUTABLE_PRICE_CERTIFICATION",
        "source_provenance":"actual_archived_source_review_plus_separate_unverified_external_witness_lanes",
        "chronological_requirements":{"minimum_training_per_league":MIN_TRAIN,
                                      "minimum_untouched_holdout_per_league":MIN_HOLDOUT},
        "counts":counts,"nba_source_inventory_status":original_inventory["status"],
        "nba_admission_status":nba_history["status"],
        "other_league_admission_status":all_history["status"],
        "native_NBA_research_model_fitted_not_released":nba_has_model,
        "native_other_research_models_fitted_not_released":models,
        "forward_research_by_league":{"nba":nba_forward,"nfl":nfl_forward,"nhl":nhl_forward},
        "price_audit_decision":price["decision"],
        "price_research_witness_pairs_uncertified":price["externally_witnessed_quote_pairs_research_only"],
        "release_blockers":blocked,
        "unverified_witness_keys_not_a_trusted_timestamp_authority":True,
        "external_source_custody_and_holdout_WORM_verified":False,
        "bookmaker_quotes_verified_current_and_executable":False,
        "independently_authenticated_frozen_Champion_executable":False,
        "champion_001_modified":False,
        "bet_ready":False,
        "automated_bets_placed":0,
        "certified_positive_ev_bets":0,
    }
    for x in (nba_history,all_history,nba_fit,seven_fit):
        if x.get("champion_001_modified") is not False:
            raise ValueError("champion_001_safety_boundary_violated")
    if price.get("certified_positive_ev_picks")!=0 or price.get("bet_ready") is not False:
        raise ValueError("price_research_may_not_certify_a_bet")
    _write(dest/"ALL_IN_ONE_RELEASE_READINESS.json",report)
    lines=[
        "# Freddy's Picks AI — All-in-one independently gated audit",
        "","**Decision: HOLD — no certified EV or real-money wagers.**",
        "","| Actual evidence | Count |","|---|---:|",
        f"| Archived NBA original pregame research games | {counts['nba_original_research_games_reviewed']} |",
        f"| Externally witnessed earlier NBA training games | {counts['nba_chronological_training_games_externally_witnessed']} / 200 |",
        f"| Externally witnessed later NBA holdout games | {counts['nba_untouched_later_holdout_games_externally_witnessed']} / 50 |",
        f"| NBA ESPN-published forward research grades | {counts['nba_original_graded_research_forecasts']} |",
        f"| NFL ESPN-published forward research grades | {counts['nfl_original_graded_research_forecasts']} |",
        f"| NHL ESPN-published forward research grades | {counts['nhl_original_graded_research_forecasts']} |",
        f"| Direct executable DraftKings prices independently certified | 0 |",
        f"| Certified positive-EV picks / wagers | 0 |",
        "","No automatically generated source reviewer approvals, odds substitutions,",
        "holdout contamination or postgame probability reconstruction are permitted.",
        "The NBA/NFL/NHL grades and research model fits are not independent",
        "bookmaker settlement or authenticated model certification.",
        "","## Required external proof",
        *("- "+item for item in blocked),
        "","Champion-001 was not accessed or modified.",
    ]
    (dest/"ALL_IN_ONE_STATUS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nba-research")
    p.add_argument("--other-research")
    p.add_argument("--live-run-metadata")
    p.add_argument("--nba-candidates")
    p.add_argument("--other-candidates")
    p.add_argument("--historical-original-root")
    p.add_argument("--pregame-public-key")
    p.add_argument("--final-public-key")
    p.add_argument("--other-pregame-public-key")
    p.add_argument("--other-final-public-key")
    p.add_argument("--quote-candidates")
    p.add_argument("--checkout-original-root")
    p.add_argument("--checkout-public-key")
    p.add_argument("--output-dir",default="all_in_one_release_audit")
    p.add_argument("--refresh-forward",action="store_true")
    args=p.parse_args(argv)
    report=build_release(
        nba_research=args.nba_research,other_research=args.other_research,
        live_run_metadata=args.live_run_metadata,
        nba_candidates=args.nba_candidates,other_candidates=args.other_candidates,
        historical_original_root=args.historical_original_root,
        pregame_public_key=args.pregame_public_key,final_public_key=args.final_public_key,
        other_pregame_public_key=args.other_pregame_public_key,
        other_final_public_key=args.other_final_public_key,
        quote_candidates=args.quote_candidates,
        checkout_original_root=args.checkout_original_root,
        checkout_public_key=args.checkout_public_key,
        output_dir=args.output_dir,refresh_forward=args.refresh_forward)
    print(json.dumps({"status":report["status"],"counts":report["counts"],
                      "release_blockers":report["release_blockers"]},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
