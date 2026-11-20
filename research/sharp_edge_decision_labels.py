"""Uniform Sharp Edge decision labels. Never upgrade unverified research to TAKE."""

VALID = frozenset({"TAKE", "HOLD", "PASS"})


def classify(selection):
    """Return a user-visible decision with an explicit explanation."""
    if not isinstance(selection, dict):
        raise TypeError("selection must be a mapping")
    if selection.get("decision") == "PASS":
        return {"decision": "PASS", "reason": selection.get("reason") or "Rejected by research filters"}
    if selection.get("decision") == "TAKE" and selection.get("certified") is True and selection.get("authenticated_source") is True and selection.get("native_champion_probability_verified") is True and selection.get("positive_ev_verified") is True:
        return {"decision": "TAKE", "reason": "Authenticated source, native model probability and positive EV verified"}
    return {"decision": "HOLD", "reason": "Independent source/model/EV certification incomplete"}


def label_board(selections):
    if not isinstance(selections, list):
        raise TypeError("selections must be a list")
    return [{**item, **classify(item)} for item in selections]
