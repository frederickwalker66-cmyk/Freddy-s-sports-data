"""Fail-closed player identity crosswalk. Never match on names alone."""
def match_player(quote, player_history, crosswalk):
    result={"decision":"HOLD","identity_verified":False,"reason":"missing_verified_crosswalk",
            "model_probability":None,"ev":None,"champion_001_modified":False}
    if not isinstance(crosswalk,dict) or crosswalk.get("independently_verified") is not True:
        return result
    required=("league","provider_player_id","espn_player_id","provider_event_id","espn_event_id")
    if any(not isinstance(crosswalk.get(k),str) or not crosswalk[k] for k in required):
        return result
    if quote.get("league")!=crosswalk["league"] or quote.get("player_id")!=crosswalk["provider_player_id"]:
        return dict(result,reason="provider_player_mismatch")
    if quote.get("provider_event_id")!=crosswalk["provider_event_id"]:
        return dict(result,reason="provider_event_mismatch")
    if player_history.get("historical_espn_player_id")!=crosswalk["espn_player_id"]:
        return dict(result,reason="historical_player_mismatch")
    if player_history.get("scheduled_event_id")!=crosswalk["espn_event_id"]:
        return dict(result,reason="historical_event_mismatch")
    if quote.get("player_identity_independently_verified") is not True:
        return dict(result,reason="provider_identity_unverified")
    if player_history.get("current_roster_status_verified") is not True:
        return dict(result,reason="roster_unverified")
    return dict(result,identity_verified=True,reason="identity_matched_research_only")

def evidence_gaps(quote, history=None, crosswalk=None):
    """List concrete missing evidence without inventing a crosswalk."""
    history=history or {}
    crosswalk=crosswalk or {}
    gaps=[]
    for field in ("league","provider_event_id","player_id","player_name"):
        if not quote.get(field):
            gaps.append("quote."+field)
    for field in ("historical_espn_player_id","scheduled_event_id"):
        if not history.get(field):
            gaps.append("history."+field)
    if history.get("current_roster_status_verified") is not True:
        gaps.append("history.current_roster_status_verified")
    for field in ("league","provider_player_id","espn_player_id","provider_event_id","espn_event_id"):
        if not crosswalk.get(field):
            gaps.append("crosswalk."+field)
    if crosswalk.get("independently_verified") is not True:
        gaps.append("crosswalk.independently_verified")
    if quote.get("player_identity_independently_verified") is not True:
        gaps.append("quote.player_identity_independently_verified")
    return {"missing_evidence":gaps,"decision":"HOLD","certified":False}
