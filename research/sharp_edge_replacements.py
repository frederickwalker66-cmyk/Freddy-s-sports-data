"""Fail-closed Sharp Edge replacement engine (research-only until verified inputs exist).

No odds fetching, model inference, or bet placement occurs here. The caller must
supply timestamped, independently verified Champion-001 probabilities.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Optional


@dataclass(frozen=True)
class Candidate:
    selection_id: str
    market: str
    american_odds: int
    model_probability: Optional[float]
    model_id: str
    model_verified: bool
    odds_verified: bool
    odds_timestamp: Optional[datetime]
    evaluation_timestamp: datetime
    injury_verified: bool
    matchup_verified: bool
    minutes_verified: bool
    calibrated: bool
    game_started: bool = False
    correlation_group: str = ""
    confidence_grade: str = ""


def decimal_odds(american: int) -> float:
    if american == 0 or -100 < american < 100:
        raise ValueError("Invalid American odds")
    return 1 + (american / 100 if american > 0 else 100 / abs(american))


def evaluate(candidate: Candidate, *, max_odds_age_minutes: int = 15,
             min_ev: float = 0.03, min_probability: float = 0.0) -> dict:
    """Only TAKE when all verification gates and positive EV are satisfied."""
    reasons = []
    if candidate.model_id != "Champion-001" or not candidate.model_verified:
        reasons.append("unverified_native_champion_probability")
    if not candidate.odds_verified or candidate.odds_timestamp is None:
        reasons.append("unverified_odds")
    if not candidate.injury_verified or not candidate.matchup_verified:
        reasons.append("unverified_injury_or_matchup")
    if not candidate.minutes_verified:
        reasons.append("unverified_minutes")
    if not candidate.calibrated:
        reasons.append("uncalibrated_model")
    if candidate.game_started:
        reasons.append("game_already_started")
    if candidate.evaluation_timestamp.tzinfo is None:
        reasons.append("missing_evaluation_timezone")
    if candidate.odds_timestamp is not None:
        if candidate.odds_timestamp.tzinfo is None:
            reasons.append("missing_odds_timezone")
        elif candidate.evaluation_timestamp.tzinfo is not None:
            age = (candidate.evaluation_timestamp - candidate.odds_timestamp).total_seconds() / 60
            if age < 0 or age > max_odds_age_minutes:
                reasons.append("stale_or_future_odds")
    p = candidate.model_probability
    if p is None or not isfinite(p) or not 0 < p < 1:
        reasons.append("invalid_or_missing_probability")
    try:
        decimal = decimal_odds(candidate.american_odds)
    except ValueError:
        reasons.append("invalid_odds")
        decimal = None
    ev = (p * decimal - 1) if decimal is not None and p is not None and isfinite(p) and 0 < p < 1 else None
    if not reasons and (ev is None or ev < min_ev or p < min_probability):
        return {"selection_id": candidate.selection_id, "decision": "PASS", "ev": ev,
                "reason": "insufficient_verified_edge"}
    if reasons:
        return {"selection_id": candidate.selection_id, "decision": "HOLD", "ev": None,
                "reason": ",".join(reasons)}
    return {"selection_id": candidate.selection_id, "decision": "TAKE", "ev": ev,
            "reason": "verified_positive_ev"}


def replace_passes(original: Iterable[dict], candidates: Iterable[Candidate],
                   *, max_legs: int = 8, min_ev: float = 0.03) -> dict:
    """Replace PASS slots with highest verified TAKE candidates, never fill by force.

    Existing non-PASS legs remain unchanged and are not certified by this function.
    Correlation groups are conservatively treated as mutually exclusive.
    """
    board = [dict(leg) for leg in original]
    used_ids = {leg["selection_id"] for leg in board}
    used_groups = {leg.get("correlation_group") for leg in board
                   if leg.get("correlation_group") and leg.get("decision") != "PASS"}
    ranked = []
    for c in candidates:
        result = evaluate(c, min_ev=min_ev)
        if result["decision"] == "TAKE" and c.selection_id not in used_ids:
            ranked.append((result["ev"], c.selection_id, c, result))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    audit = []
    for leg in board:
        if leg.get("decision") != "PASS":
            continue
        selected = None
        for entry in ranked:
            _, _, candidate, result = entry
            if candidate.selection_id in used_ids:
                continue
            if candidate.correlation_group and candidate.correlation_group in used_groups:
                continue
            selected = (candidate, result)
            break
        if selected is None:
            audit.append({"original": leg["selection_id"], "replacement": None,
                          "decision": "HOLD", "reason": "no_certified_take_available"})
            leg["decision"] = "HOLD"
            leg["replacement_pending"] = True
            continue
        candidate, result = selected
        audit.append({"original": leg["selection_id"], "replacement": candidate.selection_id,
                      "decision": "TAKE", "ev": result["ev"],
                      "odds": candidate.american_odds,
                      "model_probability": candidate.model_probability,
                      "confidence_grade": candidate.confidence_grade})
        used_ids.add(candidate.selection_id)
        if candidate.correlation_group:
            used_groups.add(candidate.correlation_group)
        leg.update(selection_id=candidate.selection_id, market=candidate.market,
                   decision="TAKE", replacement_for=leg["selection_id"],
                   correlation_group=candidate.correlation_group)
    return {"board": board[:max_legs], "replacements": audit,
            "betting_status": "HOLD_UNTIL_FULL_TICKET_VERIFIED"}
