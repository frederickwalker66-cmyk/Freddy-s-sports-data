"""NBA-original external-source admission for Challenger-001 research only.

Do not promote self-attested NBA history, retrospective ESPN scores, demo API
numbers or locally-issued hashes. This stage verifies two externally supplied
Ed25519 witness statements against original preserved bytes and the *NBA*
trainer's binary home-moneyline schema. It cannot itself independently prove
that an external custodian or publication timestamp was genuine.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from challenger_authenticated_chronological_dataset import (
    canon, key_from_path, original_bytes, read_jsonl, sha256, verified_attestation)
from challenger_nba_probability import qualified_history
from challenger_backtest import timestamp

MIN_TRAIN = 200
MIN_HOLDOUT = 50
ROW_TYPE = "nba_original_pregame_and_outcome_witness_v1"
VERSION = "nba-independent-original-source-admission-v1"


def pregame_attestation(row):
    return {
        "role": "independent_nba_pregame_custodian",
        "league": "nba",
        "event_id": row["event_id"],
        "market_type": "moneyline",
        "selection_type": "home",
        "settlement_scope": "including_overtime",
        "event_source_url": row["event_source_url"],
        "source_url": row["feature_source_url"],
        "original_sha256": row["feature_snapshot_sha256"],
        "features_sha256": sha256(canon(row["features"])),
        "features_asof_utc": row["features_asof_utc"],
        "captured_at_utc": row["snapshot_utc"],
        "start_utc": row["start_utc"],
    }


def outcome_attestation(row):
    return {
        "role": "independent_nba_final_custodian",
        "league": "nba",
        "event_id": row["event_id"],
        "market_type": "moneyline",
        "selection_type": "home",
        "settlement_scope": "including_overtime",
        "event_source_url": row["event_source_url"],
        "source_url": row["outcome_source_url"],
        "original_sha256": row["outcome_snapshot_sha256"],
        "home_won": row["outcome"],
        "captured_at_utc": row["outcome_verified_at_utc"],
        "start_utc": row["start_utc"],
    }


def vet_candidate(row, root, pre_key, final_key, now):
    if not isinstance(row, dict) or row.get("record_type") != ROW_TYPE:
        raise ValueError("nba_original_source_record_type_required")
    qualified_history(row)
    if (not isinstance(row.get("event_id"), str) or
            not row["event_id"].isdigit()):
        raise ValueError("real_numeric_nba_game_id_required")
    if row.get("settlement_scope") != "including_overtime":
        raise ValueError("nba_full_game_settlement_scope_required")
    if (row.get("champion_001_modified") is not False or
            row.get("qualified_for_challenger_backtest") is not True):
        raise ValueError("nba_research_lane_or_qualification_mismatch")
    if not (timestamp(row["features_asof_utc"]) <= timestamp(row["snapshot_utc"])
            < timestamp(row["start_utc"]) < timestamp(row["outcome_verified_at_utc"])
            <= now):
        raise ValueError("nba_asof_or_outcome_timing_invalid")
    verified_attestation(row.get("pregame_proof"), pregame_attestation(row),
                         pre_key, root)
    verified_attestation(row.get("outcome_proof"), outcome_attestation(row),
                         final_key, root)
    return {k: v for k, v in row.items()
            if k not in ("pregame_proof", "outcome_proof")}


def split_nba(rows):
    ordered = sorted(rows, key=lambda r: (timestamp(r["start_utc"]), r["event_id"]))
    if len(ordered) < MIN_TRAIN + MIN_HOLDOUT:
        return [], [], "blocked_need_250_independently_witnessed_nba_games"
    # Never split a UTC game date between training and untouched holdout.
    holdout_cutoff_day = timestamp(ordered[-MIN_HOLDOUT]["start_utc"]).date()
    prior = [r for r in ordered
             if timestamp(r["start_utc"]).date() < holdout_cutoff_day]
    holdout = [r for r in ordered
               if timestamp(r["start_utc"]).date() >= holdout_cutoff_day]
    holdout_first_snapshot = min(timestamp(r["snapshot_utc"]) for r in holdout)
    train = [r for r in prior
             if timestamp(r["outcome_verified_at_utc"]) <= holdout_first_snapshot]
    if len(train) < MIN_TRAIN or len(holdout) < MIN_HOLDOUT:
        return train, holdout, "blocked_200_train_50_holdout_not_asof_separated"
    schema = set(train[0]["features"])
    if any(set(r["features"]) != schema for r in train + holdout):
        return train, holdout, "blocked_nba_pregame_feature_schema_drift"
    if len({r["outcome"] for r in train}) < 2 or len({r["outcome"] for r in holdout}) < 2:
        return train, holdout, "blocked_nba_binary_outcome_class_coverage"
    return train, holdout, "externally_witnessed_nba_research_split_not_certified"


def build(rows, evidence_root, pre_key=None, final_key=None, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("naive_evidence_audit_clock")
    now = now.astimezone(timezone.utc)
    if pre_key is None or final_key is None:
        return {
            "version": VERSION, "status": "HOLD_MISSING_EXTERNAL_NBA_TRUST_ANCHORS",
            "rows_submitted": len(rows), "nba_original_games_witness_admitted": 0,
            "chronological_training_games": 0, "untouched_holdout_games": 0,
            "rejected": {"missing_independent_witness_keys": len(rows)},
            "champion_001_modified": False,
            "certified_nba_predictions": 0, "certified_positive_ev_bets": 0,
            "bet_ready": False,
        }, None
    public = lambda key: key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    if public(pre_key) == public(final_key):
        raise ValueError("nba_pregame_and_final_witnesses_must_be_distinct")
    accepted, rejected, seen = [], Counter(), set()
    for row in rows:
        try:
            vetted = vet_candidate(row, evidence_root, pre_key, final_key, now)
            identity = vetted["event_id"]
            if identity in seen:
                raise ValueError("duplicate_nba_event_id")
            seen.add(identity)
            accepted.append(vetted)
        except (ValueError, TypeError, OSError, KeyError) as exc:
            rejected[str(exc)] += 1
    training, holdout, status = split_nba(accepted)
    ok = status == "externally_witnessed_nba_research_split_not_certified"
    report = {
        "version": VERSION, "status": status if ok else "HOLD_INCOMPLETE_NBA_ORIGINAL_EVIDENCE",
        "reason": status,
        "rows_submitted": len(rows),
        "nba_original_games_witness_admitted": len(accepted),
        "chronological_training_games": len(training),
        "untouched_holdout_games": len(holdout),
        "rejected": dict(rejected),
        "missing_originals_or_signatures_do_not_qualify": True,
        "independent_primary_publication_custody_proven_by_software": False,
        "source_witness_identity_externally_vetted_by_software": False,
        "holdout_external_worm_custody_proven_by_software": False,
        "candidate_dataset_ready_for_external_review": ok,
        "champion_001_modified": False,
        "certified_nba_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
    }
    return report, {"train": training, "holdout": holdout} if ok else None


def save(root, report, groups):
    dest = Path(root)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "nba_admission_report.json").write_bytes(canon(report) + b"\n")
    if groups is None:
        return
    for name in ("train", "holdout"):
        content = b"".join(canon(row) + b"\n" for row in groups[name])
        target = dest / ("nba_" + name + "_original_witnessed.jsonl")
        if target.exists() and target.read_bytes() != content:
            raise ValueError("nba_original_split_changed_refuse_overwrite")
        target.write_bytes(content)
    holdout_path = dest / "nba_holdout_original_witnessed.jsonl"
    seal = {
        "version": VERSION,
        "nba_holdout_original_sha256": sha256(holdout_path.read_bytes()),
        "holdout_event_ids": [r["event_id"] for r in groups["holdout"]],
        "holdout_is_not_immutable_without_external_write_once_custody": True,
    }
    seal_path = dest / "nba_holdout_local_seal.json"
    if seal_path.exists() and json.loads(seal_path.read_text()) != seal:
        raise ValueError("nba_holdout_seal_changed_refuse_overwrite")
    seal_path.write_bytes(canon(seal) + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", default="absent_independent_nba_original_source_evidence.jsonl")
    parser.add_argument("--evidence-root", default="nba_external_original_source_bytes")
    parser.add_argument("--pregame-public-key")
    parser.add_argument("--final-public-key")
    parser.add_argument("--outdir", default="challenger_results/nba_authenticated_admission")
    args = parser.parse_args(argv)
    pre = key_from_path(args.pregame_public_key) if args.pregame_public_key else None
    final = key_from_path(args.final_public_key) if args.final_public_key else None
    report, groups = build(read_jsonl(args.candidates), args.evidence_root, pre, final)
    save(args.outdir, report, groups)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
