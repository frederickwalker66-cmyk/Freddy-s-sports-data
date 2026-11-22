"""Bridge SharpAPI player props to independently reviewed roster manifests.

SharpAPI sample schema exposes player_name, not a verified player ID.
Names cannot establish identity: do not infer player IDs from names or teams.
"""
from player_identity import verify_player_prop

def verify_sharpapi_player_prop(raw, roster_evidence=None, now=None):
    if not isinstance(raw, dict):
        return {"status": "HOLD", "reasons": ["invalid_sharpapi_record"]}
    if raw.get("is_player_prop") is not True:
        return {"status": "NOT_APPLICABLE", "reasons": ["not_player_prop"]}
    if not isinstance(raw.get("player_name"), str) or not raw["player_name"].strip():
        return {"status": "HOLD", "reasons": ["missing_player_name"]}
    if not isinstance(roster_evidence, dict):
        return {"status": "HOLD", "reasons": ["provider_player_id_crosswalk_missing",
                                              "independent_roster_evidence_missing"]}
    if roster_evidence.get("sharpapi_player_name") != raw["player_name"]:
        return {"status": "HOLD", "reasons": ["player_name_crosswalk_mismatch"]}
    if roster_evidence.get("sharpapi_event_id") != raw.get("event_id"):
        return {"status": "HOLD", "reasons": ["event_crosswalk_mismatch"]}
    if roster_evidence.get("provider_player_id_crosswalk_verified") is not True:
        return {"status": "HOLD", "reasons": ["provider_player_id_crosswalk_unverified"]}
    return verify_player_prop(raw, roster_evidence, now=now)
