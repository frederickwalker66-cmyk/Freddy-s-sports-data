"""Fail-closed player identity and roster evidence checks.

Inputs must come from independently sourced, timestamped roster and event data.
This module does not query providers or certify a wager.
"""
from datetime import datetime, timezone

def _time(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except ValueError:
        return None

def verify_player_prop(market, evidence, now=None, max_age_seconds=3600):
    now = now or datetime.now(timezone.utc)
    reasons = []
    if not isinstance(market, dict) or not isinstance(evidence, dict):
        return {"status": "HOLD", "reasons": ["missing_structured_evidence"]}
    if market.get("is_player_prop") is not True:
        return {"status": "NOT_APPLICABLE", "reasons": ["not_player_prop"]}
    player_id = evidence.get("player_id")
    team_id = evidence.get("team_id")
    event_id = evidence.get("event_id")
    if not isinstance(player_id, str) or not player_id.strip():
        reasons.append("player_id_unverified")
    if not isinstance(team_id, str) or not team_id.strip():
        reasons.append("team_id_unverified")
    if not isinstance(event_id, str) or not event_id.strip() or str(market.get("event_id")) != event_id:
        reasons.append("event_identity_unverified")
    team_ids = evidence.get("event_team_ids")
    if not isinstance(team_ids, (list, tuple)) or len(team_ids) != 2 or len(set(map(str, team_ids))) != 2 or team_id not in team_ids:
        reasons.append("team_not_confirmed_in_event")
    if evidence.get("roster_confirmed") is not True:
        reasons.append("current_roster_unverified")
    if evidence.get("player_name_matched") is not True:
        reasons.append("player_name_identity_unverified")
    if evidence.get("injury_status_verified") is not True:
        reasons.append("injury_report_unverified")
    if evidence.get("eligible_to_play") is not True:
        reasons.append("player_eligibility_unverified")
    if not isinstance(evidence.get("source"), str) or not evidence["source"].strip():
        reasons.append("roster_source_unverified")
    checked = _time(evidence.get("verified_at"))
    if checked is None or not 0 <= (now - checked).total_seconds() <= max_age_seconds:
        reasons.append("roster_evidence_missing_or_stale")
    return {"status": "HOLD" if reasons else "IDENTITY_CHECK_PASS",
            "reasons": reasons or ["market_and_model_certification_still_required"]}
