"""Research-only integer winning-margin constraints for same-game tickets.

Given independently supplied home/away identities and the exact SIGNED
point spread from the selected team's perspective, show when a moneyline
plus spread constrains (or precludes) joint wins. This is logical geometry:
NO probability estimation, wagering advice, odds, or model modification.
Missing identities fail closed rather than guessing from team names.
"""
from collections import defaultdict
from math import ceil, floor, isfinite


def analyze_margin_overlap(legs):
    """Return diagnostic rows and flags; never infer team_side from selection.

    Expected optional 'team_side': 'home' or 'away' for each moneyline and
    point_spread selection. Point-spread 'line' includes the sign for the
    selected team: an away +6.5 side wins if home_margin < 6.5.
    Winning game margin is home score minus away score, an integer.
    Pushes/ties are NOT counted as a winning parlay leg.
    """
    if not isinstance(legs, list):
        raise ValueError("legs_must_be_list")
    groups = defaultdict(list)
    for number, leg in enumerate(legs, 1):
        if not isinstance(leg, dict):
            raise ValueError("leg_must_be_object")
        if leg.get("market") not in ("moneyline", "point_spread"):
            continue
        side = leg.get("team_side")
        if side is not None and side not in ("home", "away"):
            raise ValueError("invalid_team_side")
        if not isinstance(leg.get("event_id"), str) or not leg["event_id"].strip():
            raise ValueError("event_id_required")
        groups[(leg.get("league"), leg["event_id"])].append((number, leg))
    outcomes, flags = [], set()
    for (league, event), records in sorted(groups.items(), key=lambda v: str(v[0])):
        moneylines = [(n, l) for n, l in records if l["market"] == "moneyline"]
        spreads = [(n, l) for n, l in records if l["market"] == "point_spread"]
        if not moneylines or not spreads:
            continue
        numbers = [n for n, _ in records]
        if any(leg.get("team_side") not in ("home", "away") for _, leg in records):
            outcomes.append({"league": league, "event_id": event, "leg_numbers": numbers,
                             "status": "UNRESOLVED_TEAM_SIDE", "home_margin_min": None,
                             "home_margin_max": None, "number_of_integer_winning_margins": None})
            flags.add("moneyline_spread_team_side_unverified_block_joint_assessment")
            continue
        minimum, maximum = None, None
        for _, leg in records:
            side = leg["team_side"]
            if leg["market"] == "moneyline":
                bound = 1 if side == "home" else -1
                if side == "home":
                    minimum = bound if minimum is None else max(minimum, bound)
                else:
                    maximum = bound if maximum is None else min(maximum, bound)
            else:
                line = leg.get("line")
                if type(line) not in (int, float) or not isfinite(line):
                    raise ValueError("signed_spread_line_required")
                if side == "home":
                    bound = floor(-line) + 1
                    minimum = bound if minimum is None else max(minimum, bound)
                else:
                    bound = ceil(line) - 1
                    maximum = bound if maximum is None else min(maximum, bound)
        empty = minimum is not None and maximum is not None and minimum > maximum
        count = (maximum - minimum + 1 if minimum is not None and
                 maximum is not None and not empty else 0 if empty else None)
        row = {"league": league, "event_id": event, "leg_numbers": numbers,
               "status": "NO_JOINT_WINNING_MARGIN" if empty else "CONSTRAINED_JOINT_WIN",
               "home_margin_min": minimum, "home_margin_max": maximum,
               "number_of_integer_winning_margins": count}
        outcomes.append(row)
        flags.add("moneyline_spread_requires_joint_margin_review")
        if empty:
            flags.add("moneyline_spread_joint_win_mathematically_impossible")
        elif count is not None and count <= 7:
            flags.add("moneyline_spread_only_seven_or_fewer_winning_margins")
    return {"margin_overlap_groups": outcomes, "margin_overlap_warning_codes": sorted(flags),
            "probability_estimated": False, "champion_001_modified": False}
