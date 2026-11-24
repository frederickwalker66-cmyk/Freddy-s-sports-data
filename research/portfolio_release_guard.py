"""Conservative portfolio diagnostics; never authorizes wagers."""
from collections import Counter
from itertools import combinations

def audit_portfolio(tickets):
    reasons = set()
    exposure = Counter()
    overlaps = []
    identities = []
    if not isinstance(tickets, list) or not tickets:
        return {"status": "HOLD", "reasons": ["PORTFOLIO_EVIDENCE_MISSING"], "overlaps": [], "actionable": False}
    for ticket in tickets:
        keys = set()
        events = Counter()
        if not isinstance(ticket, dict) or not isinstance(ticket.get("legs"), list) or not ticket["legs"]:
            reasons.add("INVALID_TICKET")
            identities.append(keys)
            continue
        for leg in ticket["legs"]:
            if not isinstance(leg, dict):
                reasons.add("INVALID_LEG_IDENTITY")
                continue
            event, market, selection = (leg.get(k) for k in ("event_id", "market_type", "selection_id"))
            if not all(isinstance(v, str) and v.strip() for v in (event, market, selection)):
                reasons.add("INVALID_LEG_IDENTITY")
                continue
            key = tuple(v.strip().casefold() for v in (event, market, selection))
            if key in keys:
                reasons.add("DUPLICATE_LEG")
            keys.add(key)
            events[key[0]] += 1
        exposure.update(keys)
        if any(n > 1 for n in events.values()):
            reasons.add("SAME_GAME_JOINT_PROBABILITY_NOT_AUTHENTICATED")
        identities.append(keys)
    for (i, a), (j, b) in combinations(enumerate(identities), 2):
        shared = a & b
        if shared:
            reasons.add("OVERLAPPING_TICKETS")
            overlaps.append({"ticket_indices": [i, j], "shared_legs": len(shared), "union_fraction": len(shared)/len(a | b)})
    reasons.add("INDEPENDENT_PORTFOLIO_ATTESTATION_MISSING")
    return {"status": "HOLD", "actionable": False, "reasons": sorted(reasons), "overlaps": overlaps,
            "repeated_selection_count": sum(n > 1 for n in exposure.values())}
