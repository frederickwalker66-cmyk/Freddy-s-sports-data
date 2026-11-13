"""One NBA/NFL research board for moneylines, spreads, totals and player props.

Combines already-screened archived SharpAPI two-sided snapshots. No model
probabilities are inferred from bookmaker prices, no sportsbook checkout is
authenticated here, and archived movement is NEVER true closing-line value.
"""
from __future__ import annotations

CATEGORIES = ("moneyline", "point_spread", "total_points", "player_prop")


def mixed_market_board(game_report, prop_report):
    if not isinstance(game_report, dict) or not isinstance(prop_report, dict):
        raise ValueError("mixed_market_reports_required")
    if (game_report.get("champion_001_modified") is not False
            or prop_report.get("champion_001_modified") is not False
            or game_report.get("certified_positive_ev_bets") != 0
            or prop_report.get("certified_positive_ev_bets") != 0):
        raise ValueError("upstream_mixed_market_certification_is_untrusted")
    games = game_report.get("today_game_market_board")
    props = prop_report.get("today_player_prop_market_probability_board")
    if not isinstance(games, list) or not isinstance(props, dict):
        raise ValueError("invalid_mixed_market_board_shape")
    if any(not isinstance(props.get(league), list) for league in ("nba", "nfl")):
        raise ValueError("invalid_mixed_player_prop_board_shape")
    counts = {market: 0 for market in CATEGORIES}
    markets = []
    for game in games:
        if not isinstance(game, dict) or game.get("league") not in ("nba", "nfl"):
            raise ValueError("untrusted_game_market_item")
        group = game.get("paired_primary_markets")
        if not isinstance(group, dict):
            raise ValueError("untrusted_game_market_group")
        for category, quote in sorted(group.items()):
            if category not in CATEGORIES[:3] or not isinstance(quote, dict):
                raise ValueError("unrecognized_mixed_game_market")
            if (quote.get("market") != category
                    or quote.get("bookmaker_checkout_price_verified") is not False
                    or quote.get("native_model_probability_verified") is not False):
                raise ValueError("untrusted_mixed_game_quote_promotion")
            counts[category] += 1
            markets.append({
                "league": game["league"],
                "event_id_unverified": game.get("provider_event_id"),
                "matchup": f"{game.get('away_team', 'unknown')} @ {game.get('home_team', 'unknown')}",
                "start_utc": game.get("start_utc"),
                "category": category,
                "selection_options": ("home", "away") if category != "total_points"
                                     else ("over", "under"),
                "first_side_line": quote.get("home_or_over_line"),
                "second_side_line": quote.get("away_or_under_line"),
                "first_side_american_odds": quote.get("home_or_over_odds"),
                "second_side_american_odds": quote.get("away_or_under_odds"),
                "source_quote_utc": quote.get("provider_quote_utc"),
                "model_probability": None, "indicative_ev_roi_percent": None,
                "verified_clv_percent": None,
                "direct_checkout_verified": False,
                "decision": "HOLD_NO_EXACT_MARKET_NATIVE_MODEL_AND_CHECKOUT",
            })
    for league in ("nba", "nfl"):
        for p in props[league]:
            if not isinstance(p, dict) or p.get("league") != league:
                raise ValueError("untrusted_mixed_player_prop_item")
            if (p.get("player_identity_independently_verified") is not False
                    or p.get("active_player_independently_verified") is not False):
                raise ValueError("unverified_player_cannot_be_promoted")
            counts["player_prop"] += 1
            markets.append({
                "league": league,
                "event_id_unverified": p.get("provider_event_id"),
                "matchup": f"{p.get('away_team', 'unknown')} @ {p.get('home_team', 'unknown')}",
                "start_utc": p.get("start_utc"),
                "category": "player_prop",
                "player_name_unverified": p.get("player_name"),
                "prop_stat": p.get("prop_stat"),
                "first_side_line": p.get("line"),
                "second_side_line": p.get("line"),
                "selection_options": ("over", "under"),
                "first_side_american_odds": p.get("over_american_odds"),
                "second_side_american_odds": p.get("under_american_odds"),
                "source_quote_utc": p.get("last_capture_utc"),
                "model_probability": None, "indicative_ev_roi_percent": None,
                "verified_clv_percent": None,
                "direct_checkout_verified": False,
                "decision": "HOLD_NO_EXACT_MARKET_NATIVE_MODEL_PLAYER_ID_AND_CHECKOUT",
            })
    markets.sort(key=lambda m: (
        m["start_utc"] or "", m["league"], m["event_id_unverified"] or "",
        CATEGORIES.index(m["category"]), m.get("player_name_unverified") or ""))
    return {
        "report_type": "V8_UNIFIED_GAME_AND_PLAYER_PROP_RESEARCH_ONLY",
        "supported_leagues": ["nba", "nfl"],
        "market_categories": list(CATEGORIES),
        "displayed_reference_counts_by_market": counts,
        "reference_quotes": markets,
        "total_visible_reference_markets": sum(counts.values()),
        "raw_observation_counts_not_candidates": {
            "game_by_league_and_market":
                game_report.get("validated_source_quote_observations_by_league_and_market", {}),
            "player_prop_by_league": prop_report.get("valid_prop_quotes_by_league", {}),
        },
        "model_derived_positive_ev_leaderboard": [],
        "joint_five_leg_win_probability": None,
        "five_leg_same_game_correlation_model_verified": False,
        "verified_closing_line_value": None,
        "independent_sharp_bettor_activity_verified": False,
        "confirmed_sportsbook_checkout_prices": 0,
        "certified_positive_ev_bets": 0, "bet_ready": False,
        "automated_wagers": 0, "champion_001_modified": False,
        "decision": "HOLD_NO_CERTIFIED_CROSS_MARKET_PROBABILITIES_OR_EXECUTABLE_ODDS",
        "warning": ("Visible archived reference quotes are NOT a complete live board, "
                    "certified picks, model edges, or actual parlay prices. Check "
                    "injuries, independent original exact-line models, player identity, "
                    "book checkout and joint correlation before any recommendation."),
    }
