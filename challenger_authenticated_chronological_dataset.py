"""Fail-closed external-witness admission for Challenger chronological training.

A local SHA256, unsigned review flag, retrospectively supplied source URL, or
GitHub action completion is NOT independent source authentication. Two distinct,
out-of-repository Ed25519 trust anchors must attest original pregame and outcome
bytes. The operator must independently vet those custodians and source custody.
This stage never fits a model, opens a sportsbook or changes Champion-001.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from challenger_multisport_native_capture import CAPTURE_LEAGUES
from challenger_multisport_native_training import validate_row
from challenger_prospective_outcome_validation import instant

MIN_TRAIN = 200
MIN_HOLDOUT = 50
MAX_FILE_BYTES = 5_000_000
VERSION = "independent-external-witness-admission-v1"


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def key_from_path(path):
    if not path:
        raise ValueError("missing_external_independent_witness_public_key")
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("witness_key_must_be_ed25519")
    return key


def original_bytes(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("unsafe_original_evidence_path")
    base = Path(root).resolve(strict=True)
    file = (base / relative).resolve(strict=True)
    if not file.is_relative_to(base) or not file.is_file() or file.is_symlink():
        raise ValueError("unsafe_original_evidence_path")
    if file.stat().st_size <= 0 or file.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("empty_or_oversized_original_source")
    return file.read_bytes()


def verified_attestation(proof, expected, key, evidence_root):
    if not isinstance(proof, dict) or set(proof) != {"attestation", "signature_b64", "original_path"}:
        raise ValueError("missing_external_witness_attestation")
    signed = proof["attestation"]
    if not isinstance(signed, dict) or signed != expected:
        raise ValueError("external_witness_payload_does_not_match_record")
    try:
        sig = base64.b64decode(proof["signature_b64"], validate=True)
        key.verify(sig, canon(signed))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise ValueError("external_witness_signature_invalid") from exc
    raw = original_bytes(evidence_root, proof["original_path"])
    if sha256(raw) != signed["original_sha256"]:
        raise ValueError("original_source_bytes_digest_mismatch")


def expected_pregame(row):
    return {
        "role": "independent_pregame_custodian",
        "league": row["league"], "event_id": row["event_id"],
        "market_type": row["market_type"], "settlement_scope": row["settlement_scope"],
        "event_source_url": row["event_source_url"],
        "source_url": row["feature_source_url"],
        "original_sha256": row["feature_snapshot_sha256"],
        "features_sha256": sha256(canon(row["features"])),
        "captured_at_utc": row["snapshot_utc"],
        "features_asof_utc": row["features_asof_utc"],
        "start_utc": row["start_utc"],
    }


def expected_outcome(row):
    return {
        "role": "independent_outcome_custodian",
        "league": row["league"], "event_id": row["event_id"],
        "market_type": row["market_type"], "settlement_scope": row["settlement_scope"],
        "event_source_url": row["event_source_url"],
        "source_url": row["outcome_source_url"],
        "original_sha256": row["outcome_snapshot_sha256"],
        "outcome": row["outcome"],
        "captured_at_utc": row["outcome_verified_at_utc"],
        "start_utc": row["start_utc"],
    }


def admit_one(row, now, evidence_root, pregame_key, outcome_key):
    if not isinstance(row, dict):
        raise ValueError("non_object_evidence_record")
    # The existing native trainer enforces sport, game market, canonical UTC,
    # source URLs, numeric-only pregame features, leakage and settlement scope.
    validate_row(row, now)
    p, o = expected_pregame(row), expected_outcome(row)
    if not (instant(p["features_asof_utc"]) <= instant(p["captured_at_utc"])
            < instant(p["start_utc"]) < instant(o["captured_at_utc"]) <= now):
        raise ValueError("external_witness_timing_failed")
    verified_attestation(row.get("pregame_proof"), p, pregame_key, evidence_root)
    verified_attestation(row.get("outcome_proof"), o, outcome_key, evidence_root)
    return {key: value for key, value in row.items() if key not in ("pregame_proof", "outcome_proof")}


def chrono_split(rows):
    """Holdout starts on a distinct UTC game date, never on a same-day split."""
    ordered = sorted(rows, key=lambda r: (instant(r["start_utc"]), r["event_id"]))
    if len(ordered) < MIN_TRAIN + MIN_HOLDOUT:
        return [], [], "need_250_externally_witnessed_games"
    cut_day = instant(ordered[-MIN_HOLDOUT]["start_utc"]).date()
    prior = [r for r in ordered if instant(r["start_utc"]).date() < cut_day]
    holdout = [r for r in ordered if instant(r["start_utc"]).date() >= cut_day]
    first_holdout_capture = min(instant(r["snapshot_utc"]) for r in holdout)
    train = [r for r in prior if instant(r["outcome_verified_at_utc"]) <= first_holdout_capture]
    if len(train) < MIN_TRAIN or len(holdout) < MIN_HOLDOUT:
        return train, holdout, "chronological_split_or_prior_outcomes_not_available_in_time"
    fields = sorted(train[0]["features"])
    if any(sorted(r["features"]) != fields for r in train + holdout):
        return train, holdout, "feature_schema_drift"
    return train, holdout, "externally_witnessed_research_candidate_not_certified"


def build(rows, evidence_root, pregame_key=None, outcome_key=None, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("naive_audit_clock")
    now = now.astimezone(timezone.utc)
    admitted, rejected = defaultdict(list), Counter()
    seen = set()
    if pregame_key is None or outcome_key is None:
        return {"status": "HOLD_MISSING_INDEPENDENT_TRUST_ANCHORS",
                "admitted_games": 0, "rejected": {"missing_trust_anchor": len(rows)},
                "by_league": {}, "certified_bets": 0, "champion_001_modified": False}, {}
    if pregame_key.public_bytes(encoding=serialization.Encoding.Raw,
                                format=serialization.PublicFormat.Raw) == outcome_key.public_bytes(
                                    encoding=serialization.Encoding.Raw,
                                    format=serialization.PublicFormat.Raw):
        raise ValueError("independent_pregame_and_outcome_custodians_must_differ")
    for row in rows:
        try:
            qualified = admit_one(row, now, evidence_root, pregame_key, outcome_key)
            identity = (qualified["league"], qualified["event_id"])
            if identity in seen:
                raise ValueError("duplicate_game_identity")
            seen.add(identity)
            admitted[qualified["league"]].append(qualified)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            rejected[str(exc)] += 1
    accepted = {}
    report = {}
    for league in sorted(CAPTURE_LEAGUES):
        train, holdout, status = chrono_split(admitted[league])
        report[league] = {
            "authenticated_candidate_games": len(admitted[league]),
            "chronological_training_games": len(train),
            "untouched_holdout_games": len(holdout),
            "status": status,
        }
        if status == "externally_witnessed_research_candidate_not_certified":
            accepted[league] = {"train": train, "holdout": holdout}
    return {
        "version": VERSION,
        "status": "RESEARCH_EVIDENCE_ONLY_NO_MODEL_RELEASE",
        "admitted_games": sum(map(len, admitted.values())),
        "rejected": dict(rejected),
        "by_league": report,
        "externally_witnessed_leagues_meeting_200_50": sorted(accepted),
        "source_custodian_identity_independently_vetted_by_software": False,
        "timestamp_authority_or_original_publisher_independently_verified": False,
        "holdout_external_immutability_established": False,
        "certified_bets": 0, "bet_ready": False,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "champion_001_modified": False,
    }, accepted


def read_jsonl(path):
    if not path or not Path(path).is_file():
        return []
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_output(root, report, accepted):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "admission_report.json").write_bytes(canon(report) + b"\n")
    for league, groups in accepted.items():
        # Separate files: trainer must not be allowed to inspect holdout while
        # feature selection or model fitting is underway.
        for part in ("train", "holdout"):
            path = root / (league + "_" + part + "_witnessed.jsonl")
            incoming = b"".join(canon(row) + b"\n" for row in groups[part])
            if path.exists() and path.read_bytes() != incoming:
                raise ValueError("prior_split_changed_refuse_overwrite")
            path.write_bytes(incoming)
        lock = root / (league + "_holdout_lock.json")
        entry = {"league": league, "holdout_event_ids": [r["event_id"] for r in groups["holdout"]],
                 "holdout_sha256": sha256((root / (league + "_holdout_witnessed.jsonl")).read_bytes()),
                 "warning": "A local lock is NOT an external immutable third-party archive."}
        if lock.exists() and json.loads(lock.read_text()) != entry:
            raise ValueError("prior_holdout_lock_changed_refuse_overwrite")
        lock.write_bytes(canon(entry) + b"\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", default="absent_external_reviewed_games.jsonl")
    p.add_argument("--evidence-root", default="external_original_source_bytes")
    p.add_argument("--pregame-public-key")
    p.add_argument("--outcome-public-key")
    p.add_argument("--outdir", default="challenger_results/authenticated_admission")
    args = p.parse_args(argv)
    pre = key_from_path(args.pregame_public_key) if args.pregame_public_key else None
    out = key_from_path(args.outcome_public_key) if args.outcome_public_key else None
    report, accepted = build(read_jsonl(args.candidates), args.evidence_root, pre, out)
    write_output(args.outdir, report, accepted)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
