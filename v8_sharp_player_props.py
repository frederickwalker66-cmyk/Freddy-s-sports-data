"""Research-only NBA/NFL/NCAAF SharpAPI player-prop *price movement* audit.

Reads already saved DraftKings-LABELED aggregator quotes; never calls providers,
confirms active players, infers sharp-money flow, produces a model probability,
or certifies a bet. Only complete paired over/under snapshots for the SAME
event, player, stat, line, sportsbook and capture time can show repricing.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

from challenger_moneyline_market_baseline import (
    implied, MAX_OVERROUND, MAX_PAIR_TIMESTAMP_SKEW_SECONDS,
    MAX_PROVIDER_QUOTE_AGE_SECONDS,
)
from historical_outcomes import parse_time
from v8_sharp_archive import MAX_RESEARCH_WATCHLIST_AGE_MINUTES
from v8_sharp_probability_display import price_pair_probabilities

PROP_SPORTS = frozenset(("nba", "nfl", "ncaaf"))
# This gate admits only individually identified, two-sided player statistics.
# The provider's *_combo_ / *_either_ / *_each_ / *_h2h_* markets have
# different settlement semantics and must not be treated as single-player props.
PRIMARY_PLAYER_STATS = {
    "nba": frozenset((
        "player_points", "player_rebounds", "player_assists",
        "player_made_threes", "player_steals", "player_blocks",
        "player_turnovers", "player_points_+_rebounds",
        "player_points_+_assists", "player_rebounds_+_assists",
        "player_points_+_rebounds_+_assists",
    )),
    "ncaaf": frozenset((
        "player_passing_yards", "player_passing_touchdowns",
        "player_passing_attempts", "player_passing_completions",
        "player_rushing_yards", "player_rushing_attempts",
        "player_receiving_yards", "player_receiving_touchdowns",
        "player_receptions",
    )),
    "nfl": frozenset((
        "player_passing_yards", "player_passing_touchdowns",
        "player_passing_attempts", "player_passing_completions",
        "player_rushing_yards", "player_rushing_attempts",
        "player_receiving_yards", "player_receptions",
        "player_longest_reception", "player_longest_rush",
        "player_passing_+_rushing_yards",
        "player_rushing_+_receiving_yards",
        "player_interceptions", "player_extra_points_made",
        "player_field_goals_made", "player_kicking_points",
        "player_longest_passing_completion",
    )),
}
MAX_PROP_MOVEMENTS = 20000
NY = ZoneInfo("America/New_York")


def inspect_player_prop(row):
    """Validate provenance and exact two-sided market identity, NOT checkout."""
    if not isinstance(row, dict):
        return None, "invalid_row"
    if (row.get("source") != "sharpapi_rest"
            or row.get("sportsbook") != "draftkings"
            or row.get("record_type") != "pregame_odds_observation"
            or row.get("league") not in PROP_SPORTS
            or row.get("is_player_prop") is not True
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None):
        return None, "untrusted_or_unsupported_prop"
    if (row.get("is_main_line") is not True
            or row.get("is_alternate_line") is not False
            or row.get("selection_type") not in ("over", "under")):
        return None, "unconfirmed_primary_over_under_identity"
    eid, name, player, stat = (
        row.get("event_id"), row.get("player_name"),
        row.get("player_id"), row.get("market_type"))
    if (not isinstance(eid, str) or not eid.strip()
            or not isinstance(name, str) or len(name.strip()) < 3
            or type(player) not in (str, int, type(None))
            or (type(player) is str and player.strip() == "" and player != "")
            or not isinstance(row.get("home_team"), str)
            or not isinstance(row.get("away_team"), str)
            or not row["home_team"].strip() or not row["away_team"].strip()
            or row["home_team"].strip() == row["away_team"].strip()):
        return None, "missing_exact_event_player_stat_identity"
    if not isinstance(stat, str) or stat not in PRIMARY_PLAYER_STATS[row["league"]]:
        return None, "unsupported_or_ambiguous_prop_settlement_market"
    # A null/empty provider player ID is common in the real SharpAPI archives.
    # Match an EXACT provider-name spelling for *archived research only*, never
    # fabricate a player ID or independently assert that the athlete is active.
    player_id = str(player).strip() if player is not None else ""
    identity_basis = ("provider_id_plus_name_unverified" if player_id
                      else "provider_name_only_unverified")
    line = row.get("line")
    if (type(line) not in (int, float) or not math.isfinite(line)
            or line < 0):
        return None, "invalid_prop_line"
    odds = row.get("odds_american")
    if (type(odds) not in (int, float) or not math.isfinite(odds)
            or abs(odds) < 100):
        return None, "invalid_prop_odds"
    decimal = row.get("odds_decimal")
    expected = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
    if (type(decimal) not in (int, float) or not math.isfinite(decimal)
            or abs(decimal - expected) > 0.025):
        return None, "inconsistent_prop_decimal_price"
    try:
        start = parse_time(row["event_start_time"])
        received = parse_time(row["recorded_at"])
        quoted = parse_time(row["timestamp"])
        if not (0 <= (received - quoted).total_seconds()
                    <= MAX_PROVIDER_QUOTE_AGE_SECONDS
                and quoted < start and received < start):
            return None, "not_actual_pregame_prop_receipt"
        price_implied = implied(odds)
    except (TypeError, KeyError, ValueError, OverflowError):
        return None, "invalid_prop_timestamps"
    # Exact line is a mandatory part of the key: moving a 25.5 line to
    # 26.5 cannot be misrepresented as a same-line money movement.
    key = (
        row["league"], eid, player_id, name.strip(), stat,
        float(line), row["home_team"], row["away_team"], start,
        row["sportsbook"],
    )
    return {
        "raw": row, "key": key, "received": received,
        "quote": quoted, "start": start, "implied": price_implied,
        "identity_match_basis": identity_basis,
    }, None


def summarize_player_props(rows, *, now=None, archive_run_ids=()):
    if not isinstance(rows, list):
        raise ValueError("prop_quotes_must_be_list")
    clock = datetime.now(timezone.utc) if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("timezone_aware_prop_audit_clock_required")
    clock = clock.astimezone(timezone.utc)
    grouped = defaultdict(list)
    rejected = Counter()
    by_league = Counter()
    prop_observations = 0
    accepted = 0
    name_only_accepted = 0
    provider_id_accepted = 0
    for row in rows:
        if isinstance(row, dict) and row.get("is_player_prop") is True:
            prop_observations += 1
        item, reason = inspect_player_prop(row)
        if reason:
            if isinstance(row, dict) and row.get("is_player_prop") is True:
                rejected[reason] += 1
            continue
        if item["received"] > clock:
            rejected["archive_observed_in_future"] += 1
            continue
        grouped[item["key"]].append(item)

    # One vendor spelling within one exact event/stat/line must not be
    # stitched across missing, changing or contradictory provider player IDs.
    # Preserve valid name-only research when *every* row in that market lacks
    # an ID, but quarantine the entire conflicting family otherwise.
    identity_variants = defaultdict(set)
    for key in grouped:
        family = key[:2] + key[3:]
        identity_variants[family].add(key[2])
    conflicting = {k for k, values in identity_variants.items()
                   if len(values) > 1}

    movements = []
    paired_snapshots = 0
    current_prop_markets = []
    for key, group in sorted(grouped.items(), key=lambda x: (
            x[0][0], x[0][1], x[0][2], x[0][4], x[0][5])):
        if key[:2] + key[3:] in conflicting:
            rejected["ambiguous_or_mixed_provider_player_ids"] += len(group)
            continue
        accepted += len(group)
        by_league[key[0]] += len(group)
        if key[2]:
            provider_id_accepted += len(group)
        else:
            name_only_accepted += len(group)
        captures = defaultdict(list)
        for item in group:
            captures[item["received"]].append(item)
        snapshots = []
        for received, batch in sorted(captures.items()):
            overs = [x for x in batch if x["raw"]["selection_type"] == "over"]
            unders = [x for x in batch if x["raw"]["selection_type"] == "under"]
            if len(overs) != 1 or len(unders) != 1:
                rejected["unpaired_or_duplicate_exact_line"] += 1
                continue
            o, u = overs[0], unders[0]
            if (abs((o["quote"]-u["quote"]).total_seconds())
                    > MAX_PAIR_TIMESTAMP_SKEW_SECONDS):
                rejected["asynchronous_over_under_prices"] += 1
                continue
            vig = o["implied"]+u["implied"]
            if not 1 <= vig <= MAX_OVERROUND:
                rejected["implausible_prop_overround"] += 1
                continue
            snapshots.append((received, o, u))
            paired_snapshots += 1
        if snapshots:
            # Keep the latest exact player/stat/line two-sided pregame source
            # price. No movement is required to display market-price %
            # (important for NBA props when no two-capture repricing exists).
            last_time, over, under = snapshots[-1]
            start = key[8]
            age = (clock - last_time).total_seconds() / 60
            if (start > clock and start.astimezone(NY).date() ==
                    clock.astimezone(NY).date()
                    and 0 <= age <= MAX_RESEARCH_WATCHLIST_AGE_MINUTES):
                probabilities = price_pair_probabilities(
                    over["implied"], under["implied"])
                current_prop_markets.append({
                    "league": key[0], "provider_event_id": key[1],
                    "player_id": key[2] or None, "player_name": key[3],
                    "player_identity_match_basis": (
                        "provider_id_plus_name_unverified" if key[2]
                        else "provider_name_only_unverified"),
                    "player_identity_independently_verified": False,
                    "prop_stat": key[4], "line": key[5],
                    "home_team": key[6], "away_team": key[7],
                    "start_utc": start.isoformat(),
                    "last_capture_utc": last_time.isoformat(),
                    "source_age_minutes": round(age, 1),
                    "over_american_odds": over["raw"]["odds_american"],
                    "under_american_odds": under["raw"]["odds_american"],
                    **probabilities,
                    "active_player_independently_verified": False,
                    "bet_ready": False,
                    "decision": "HOLD_NO_VERIFIED_MODEL_PLAYER_OR_CHECKOUT",
                })
        for before, after in zip(snapshots, snapshots[1:]):
            t0, o0, u0 = before
            t1, o1, u1 = after
            if (t1 <= t0 or o1["quote"] < o0["quote"]
                    or u1["quote"] < u0["quote"]):
                rejected["nonmonotonic_prop_quote_updates"] += 1
                continue
            if (o0["quote"] == o1["quote"] and u0["quote"] == u1["quote"]):
                rejected["unchanged_prop_provider_quote"] += 1
                continue
            first = o0["implied"]/(o0["implied"]+u0["implied"])
            last = o1["implied"]/(o1["implied"]+u1["implied"])
            change = round((last-first)*100, 5)
            movements.append({
                "record_type": "v8_exact_player_prop_repricing_research_only",
                "league": key[0], "provider_event_id": key[1],
                "player_id": key[2] or None, "player_name": key[3],
                "player_identity_match_basis": (
                    "provider_id_plus_name_unverified" if key[2]
                    else "provider_name_only_unverified"),
                "player_identity_independently_verified": False,
                "prop_stat": key[4], "line": key[5],
                "home_team": key[6], "away_team": key[7],
                "start_utc": key[8].isoformat(),
                "first_capture_utc": t0.isoformat(),
                "last_capture_utc": t1.isoformat(),
                "over_odds_before": o0["raw"]["odds_american"],
                "over_odds_after": o1["raw"]["odds_american"],
                "under_odds_before": u0["raw"]["odds_american"],
                "under_odds_after": u1["raw"]["odds_american"],
                # These derive from the TWO price sides, not a model.
                **price_pair_probabilities(o1["implied"], u1["implied"]),
                "over_no_vig_market_change_pp": change,
                "absolute_repricing_pp": round(abs(change), 5),
                "direction": ("toward_over" if change > 0 else
                              "toward_under" if change < 0 else "unchanged"),
                "direct_draftkings_checkout_verified": False,
                "player_active_independently_verified": False,
                "player_prop_model_probability_verified": False,
                "sharp_money_flow_verified": False,
                "certified_prediction": False,
                "positive_ev_certified": False,
                "bet_ready": False, "stake_usd": 0,
                "champion_001_modified": False,
            })
            if len(movements) > MAX_PROP_MOVEMENTS:
                raise ValueError("prop_repricing_archive_budget_exceeded")
    upcoming, stale = [], 0
    for movement in movements:
        start = parse_time(movement["start_utc"])
        last = parse_time(movement["last_capture_utc"])
        if start <= clock or last > clock:
            continue
        minutes = (clock-last).total_seconds()/60
        if minutes > MAX_RESEARCH_WATCHLIST_AGE_MINUTES:
            stale += 1
            continue
        upcoming.append(dict(movement, signal_age_minutes=round(minutes,1),
                             decision="HOLD_UNVERIFIED_PROP_MODEL_PLAYER_AND_CHECKOUT"))
    upcoming.sort(key=lambda x: (-x["absolute_repricing_pp"], x["start_utc"],
                                  x["league"], x["player_name"],
                                  x["player_id"] or "", x["prop_stat"]))
    # Show each sport even if no historical movement could be established.
    # Price-derived percentages are never used as model inputs.
    current_prop_markets.sort(key=lambda x: (
        -parse_time(x["last_capture_utc"]).timestamp(),
        x["start_utc"], x["league"], x["player_name"], x["prop_stat"], x["line"]))
    probability_board = {
        sport: [item for item in current_prop_markets if item["league"] == sport][:8]
        for sport in ("nba", "nfl", "ncaaf")
    }
    report = {
        "report_type": "v8_nba_nfl_ncaaf_exact_player_props_archived_repricing_research_only",
        "status": "historical_prop_quotes_analyzed" if accepted
                  else "no_eligible_archived_player_prop_quotes",
        "raw_prop_quote_observations": prop_observations,
        "valid_exact_player_prop_quote_observations": accepted,
        "valid_provider_name_only_quote_observations_research_only":
            name_only_accepted,
        "valid_provider_id_plus_name_quote_observations_research_only":
            provider_id_accepted,
        "source_player_ids_missing_from_valid_research_quotes":
            name_only_accepted,
        "source_player_identity_independently_verified": False,
        "conflicting_provider_identity_market_groups_excluded": len(conflicting),
        "valid_prop_quotes_by_league": dict(sorted(by_league.items())),
        "two_sided_same_line_snapshots": paired_snapshots,
        "exact_player_stat_line_repricings_historical": len(movements),
        "upcoming_repricing_research_observations": len(upcoming),
        "stale_upcoming_repricing_excluded": stale,
        "excluded_prop_rows_or_snapshots": dict(sorted(rejected.items())),
        "ranked_prop_repricing_watchlist": upcoming[:10],
        "today_recent_two_sided_prop_markets": len(current_prop_markets),
        "today_player_prop_market_probability_board": probability_board,
        "probability_source": "normalized_two_sided_source_book_price_not_native_model",
        "model_probability_display": "UNAVAILABLE_NOT_MODEL_GENERATED",
        "sharp_bettor_probability_display": "UNAVAILABLE_NO_SHARP_HANDLE_OR_TICKETS",
        "research_watchlist_max_age_minutes": MAX_RESEARCH_WATCHLIST_AGE_MINUTES,
        "sharp_flow_verified": False,
        "player_active_verified": False,
        "model_probabilities_generated": 0,
        "direct_draftkings_checkout_prices_verified": 0,
        "certified_nba_player_props": 0,
        "certified_nfl_player_props": 0,
        "certified_ncaaf_player_props": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "archive_run_ids": list(archive_run_ids),
        "decision": "HOLD_RESEARCH_ONLY" if upcoming else "PASS_NO_VALIDATED_PROP_EDGE",
        "warning": (
            "Missing SharpAPI player IDs allow only exact provider-name research "
            "matching, not authenticated athlete identities. Exact over/under "
            "price repricing is not sharp flow, verified active status, a native "
            "player projection, calibrated EV, or executable DraftKings quote."
        ),
    }
    return report, movements
