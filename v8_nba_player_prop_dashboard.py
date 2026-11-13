"""NBA all-player-props reference board for the one-command model.

Shows EVERY available two-sided source-labeled pregame player prop without
conflating player/team association, archived bookmaker labels, independent
model probabilities, or verified sports-book checkout. Retains all provider
identifiers and timestamps for later independent validation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import math

STATS = {
    "player_points": ("points", 0),
    "player_rebounds": ("rebounds", 1),
    "player_assists": ("assists", 2),
    "player_threePointersMade": ("threes", 3),
    "player_points+rebounds": ("points+rebounds", 4),
    "player_points+assists": ("points+assists", 5),
    "player_rebounds+assists": ("rebounds+assists", 6),
    "player_points+rebounds+assists": ("PRA", 7),
    "player_steals": ("steals", 8),
    "player_blocks": ("blocks", 9),
}
ORDER = {v[0]: v[1] for v in STATS.values()}
PREVIEW_LIMIT = 40


def _safe(v):
    if v is None:
        return "N/A"
    return str(v).replace("|", "/").replace("\n", " ")[:95]


def _number(v):
    if type(v) not in (int, float) or not math.isfinite(v):
        raise ValueError("invalid_player_prop_reference_numeric")
    return v


def create_player_props_board(games, archive_pairs):
    """Build a sortable, typed research board; do not promote any bet or identity."""
    if not isinstance(games, list) or not isinstance(archive_pairs, list):
        raise ValueError("NBA_games_and_pairs_required")
    index = {g["espn_event_id"]: g for g in games}
    if len(index) != len(games):
        raise ValueError("NBA_duplicate_espn_game_id")
    records, seen = [], set()
    for pair in archive_pairs:
        if not isinstance(pair, dict):
            raise ValueError("untrusted_market_pair")
        market = pair.get("market")
        if not isinstance(market, str) or not market.startswith("player_"):
            continue
        if (pair.get("market_scope") != "player_prop_unverified"
                or pair.get("player_team_assignment_verified") is not False
                or pair.get("source_quote_not_executable") is not True
                or pair.get("independently_calibrated_model_probability_percent") is not None
                or pair.get("certified_sharp_edge_pp") is not None
                or pair.get("certified_expected_roi_percent") is not None):
            raise ValueError("untrusted_player_prop_certification_attempt")
        eid = pair.get("espn_event_id_research_match")
        if eid not in index:
            raise ValueError("source_player_prop_without_scheduled_NBA_game")
        name = pair.get("player_name_unverified")
        provider_id = pair.get("player_id_unverified")
        if (not isinstance(name, str) or not name.strip()
                or not isinstance(provider_id, str) or not provider_id):
            raise ValueError("unverified_prop_missing_provider_identity")
        sides = pair.get("sides")
        if (not isinstance(sides, list) or len(sides) != 2
                or [s.get("selection_side") for s in sides] != ["over", "under"]):
            raise ValueError("prop_requires_two_exactly_paired_opposite_sides")
        line = _number(pair.get("line_or_absolute_spread"))
        if not 0 <= line <= 1000:
            raise ValueError("invalid_prop_line")
        for side in sides:
            if (side.get("athlete_identity_independently_verified") is True
                    or side.get("actual_sportsbook_checkout_verified") is True
                    or side.get("player_team_assignment_verified") is not False):
                raise ValueError("provider_player_identity_or_checkout_promotion")
            _number(side.get("american_odds"))
            _number(side.get("break_even_percent"))
            _number(side.get("no_vig_market_percent"))
        if abs(sum(s["no_vig_market_percent"] for s in sides) - 100) > 0.03:
            raise ValueError("player_prop_invalid_no_vig_price_pair")
        source_time = max(s["quoted_utc"] for s in sides)
        # Original quote timestamps are explicitly separate from today's scan.
        try:
            parsed = datetime.fromisoformat(source_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("source_quote_missing_timezone")
        except (ValueError, TypeError, AttributeError):
            raise ValueError("source_quote_missing_valid_timestamp") from None
        key = (eid, pair.get("sgo_event_id_unverified"), provider_id, market, line)
        if key in seen:
            raise ValueError("duplicate_source_prop_market")
        seen.add(key)
        g = index[eid]
        family = STATS.get(market, (market.removeprefix("player_"), 100))[0]
        over, under = sides
        records.append({
            "espn_scheduled_event_id_reference": eid,
            "source_sgo_event_id_unverified": pair.get("sgo_event_id_unverified"),
            "source_player_id_unverified": provider_id,
            "source_player_name_unverified": name.strip(),
            "source_labeled_matchup_unverified":
                f"{g['away_team']} @ {g['home_team']}",
            "scheduled_start_utc": g["start_utc"],
            "game_state_at_scan": g.get("source_event_state"),
            "stat_market": market,
            "stat_family": family,
            "line": line,
            "over_odds_american": over["american_odds"],
            "under_odds_american": under["american_odds"],
            "over_no_vig_market_percent": over["no_vig_market_percent"],
            "under_no_vig_market_percent": under["no_vig_market_percent"],
            "over_break_even_percent": over["break_even_percent"],
            "under_break_even_percent": under["break_even_percent"],
            "over_source_quote_utc": over["quoted_utc"],
            "under_source_quote_utc": under["quoted_utc"],
            "latest_source_quote_utc": source_time,
            "source_pair_recent_but_not_checkout": pair["source_pair_quote_fresh"],
            "provider_event_identity_not_crosschecked": True,
            "provider_player_team_assignment_verified": False,
            "player_active_today_verified": False,
            "bookmaker_checkout_verified": False,
            "provider_primary_or_alternate_line_verified": False,
            "independently_generated_prop_over_probability_percent": None,
            "independently_generated_prop_under_probability_percent": None,
            "independently_certified_prop_edge_pp": None,
            "independently_certified_prop_roi_percent": None,
            "sharp_handle_percent_verified": None,
            "decision": "HOLD_UNVERIFIED_PLAYER_TEAM_AND_UNCALIBRATED_PROP",
        })
    records.sort(key=lambda r: (
        r["scheduled_start_utc"], r["espn_scheduled_event_id_reference"],
        ORDER.get(r["stat_family"], 100), r["source_player_name_unverified"].casefold(),
        r["line"], r["source_player_id_unverified"]))
    stats = Counter(r["stat_family"] for r in records)
    per_game = defaultdict(Counter)
    for row in records:
        per_game[row["espn_scheduled_event_id_reference"]][row["stat_family"]] += 1
    # Representative rows span different stat families and matchups; no edge
    # ranking or false probability claims from the bookmaker price.
    groups = defaultdict(list)
    for row in records:
        groups[(row["stat_family"], row["espn_scheduled_event_id_reference"])].append(row)
    preview = []
    family_order = sorted(stats, key=lambda k: (ORDER.get(k, 100), k))
    for family in family_order:
        for g in games:
            chosen = groups.get((family, g["espn_event_id"])) or []
            if chosen and len(preview) < PREVIEW_LIMIT:
                preview.append(chosen[0])
    return {
        "report_type": "NBA_PLAYER_PROP_EVERY_AVAILABLE_ARCHIVED_TWO_SIDED_MARKET",
        "paired_source_prop_market_count": len(records),
        "paired_prop_counts_by_stat": dict(sorted(stats.items())),
        "paired_prop_counts_by_event_id": {
            key: dict(sorted(val.items())) for key, val in sorted(per_game.items())},
        "source_prop_event_and_player_IDs_cross_verified": False,
        "active_player_status_confirmed": 0,
        "verified_book_checkout_prop_prices": 0,
        "independent_prop_model_probability_count": 0,
        "certified_positive_ev_prop_bets": 0,
        "source_provider_player_prop_pairs": records,
        "preview_unranked_research_only": preview,
        "preview_limit": PREVIEW_LIMIT,
        "betting_decision": "HOLD_PLAYER_TEAM_INJURY_PRICE_AND_MODEL_UNVERIFIED",
        "warning": ("Player labels and scheduled game association are provider research "
                    "references only. Some source assignments conflict with actual "
                    "rosters. Do not interpret these rows as available bets, real "
                    "sportsbook checkout odds, verified active players, or sharp edges."),
    }


def _table(rows):
    lines = [
        "| Source-labeled matchup (UNVERIFIED player association) | "
        "Provider player label | Stat | Line | Over odds / no-vig % | "
        "Under odds / no-vig % | Quote UTC | Status |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {_safe(row['source_labeled_matchup_unverified'])} "
            f"| {_safe(row['source_player_name_unverified'])} "
            f"| {_safe(row['stat_family'])} "
            f"| {_safe(row['line'])} "
            f"| {_safe(row['over_odds_american'])} / {_safe(row['over_no_vig_market_percent'])}% "
            f"| {_safe(row['under_odds_american'])} / {_safe(row['under_no_vig_market_percent'])}% "
            f"| {_safe(row['latest_source_quote_utc'])} "
            "| HOLD — player/team + price unverified |"
        )
    if not rows:
        lines.append("| No source-verified two-sided NBA prop references | "
                     "N/A | N/A | N/A | N/A | N/A | N/A | HOLD |")
    return lines


def render_player_props(board, *, preview=False):
    if not isinstance(board, dict) or board.get("certified_positive_ev_prop_bets") != 0:
        raise ValueError("untrusted_player_props_board")
    rows = (board["preview_unranked_research_only"] if preview
            else board["source_provider_player_prop_pairs"])
    lines = [
        ("## NBA player props — included in every NBA scan "
         "(UNVERIFIED RESEARCH)" if preview
         else "# Freddy's Picks AI — every archived NBA player-prop market"),
        f"**Source-labeled player-prop market pairs:** "
        f"{board['paired_source_prop_market_count']} · "
        "**Verified player/team associations:** 0 · "
        "**Certified +EV player props:** 0.",
        "**These are archived sportsbook-provider labels, NOT live executable "
        "prices or confirmed player availability.**",
        "**Model prop p% / model edge pp / EV ROI%:** N/A / N/A / N/A.",
        "",
        "**Stat coverage:** " + (", ".join(
            f"{name}: {n}" for name, n in board["paired_prop_counts_by_stat"].items()
        ) or "No available paired player-prop markets."),
        "",
        ("Representative markets across scheduled source games and stat families "
         "(not ranked as best bets):" if preview
         else "All source-paired player-prop markets; provider identity "
              "and matchup labeling are NOT independently verified."),
    ]
    lines.extend(_table(rows))
    if preview:
        lines.extend([
            "",
            "**View every paired player prop:** NBA_PLAYER_PROPS_ALL_MARKETS.md",
            "**Machine-readable prop detail:** NBA_PLAYER_PROPS_ALL_MARKETS.json",
        ])
    return "\n".join(lines) + "\n"
