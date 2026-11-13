"""One consistent, evidence-labelled percentage board for every V8 phone run.

Market no-vig shares and break-even rates are calculations from archived
sportsbook-LABELLED quotes, not genuine model forecasts or sharp action.
Native forward-model research forecasts are separate and uncalibrated.
None of these sources alone certifies expected value or a bet.
"""
from __future__ import annotations

import math

MARKETS = ("moneyline", "point_spread", "total_points", "player_prop")


def _pct(value, *, fraction=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    pct = 100 * value if fraction else value
    if not 0 <= pct <= 100:
        return None
    return round(pct, 2)


def _cell(value):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).replace("|", "/").replace("\n", " ")[:110]


def _base(league, matchup, market, selection, line=None, odds=None, source=None,
          at=None):
    return {
        "league": league,
        "matchup": matchup,
        "market": market,
        "selection": selection,
        "line": line,
        "american_odds": odds,
        "model_probability_percent": None,
        "no_vig_market_probability_percent": None,
        "break_even_probability_percent": None,
        "model_edge_percentage_points": None,
        "expected_roi_percent": None,
        "sharp_money_handle_percent": None,
        "public_ticket_percent": None,
        "market_price_movement_percentage_points": None,
        "source_timestamp_utc": at,
        "source_class": source,
        "decision": "HOLD",
    }


def _paired(rows, league, matchup, market, quote, line1, line2, labels, prices, at):
    """Add two opposite sides; never derive model p from the price pair."""
    if (not isinstance(quote, dict)
            or quote.get("native_model_probability_verified") is True
            or quote.get("bookmaker_checkout_price_verified") is True):
        raise ValueError("untrusted_archived_market_promotion")
    for index, (selection, line, price) in enumerate(zip(labels, (line1, line2), prices)):
        row = _base(league, matchup, market, selection, line, price,
                    "archived_provider_price_research_only", at)
        prefix = "first" if index == 0 else "second"
        row["no_vig_market_probability_percent"] = _pct(
            quote.get(prefix + "_side_no_vig_market_percent"))
        row["break_even_probability_percent"] = _pct(
            quote.get(prefix + "_side_break_even_percent"))
        rows.append(row)


def build_dashboard(report):
    """Summarize AVAILABLE evidence; missing fields must remain None, not zero."""
    if (not isinstance(report, dict)
            or report.get("champion_001_modified") is not False
            or report.get("certified_positive_ev_bets") != 0):
        raise ValueError("invalid_betting_certification_input")

    rows = []
    for item in report.get("research_edge_candidates") or []:
        # This lane accepts independently authored pregame probabilities but
        # cannot authenticate the receipts or executable checkout prices.
        if not isinstance(item, dict) or item.get("certified_prediction") is not False:
            raise ValueError("untrusted_research_edge_promotion")
        row = _base(item.get("league"), item.get("event_id"), item.get("market"),
                    item.get("selection"), item.get("line"),
                    item.get("american_odds"), "indicative_native_research_only",
                    item.get("price_recorded_utc"))
        row["model_probability_percent"] = _pct(
            item.get("indicative_model_probability"), fraction=True)
        row["break_even_probability_percent"] = _pct(
            item.get("break_even_probability"), fraction=True)
        row["model_edge_percentage_points"] = item.get(
            "indicative_edge_percentage_points")
        row["expected_roi_percent"] = item.get("indicative_ev_roi_percent")
        row["player_name"] = item.get("player_name")
        row["decision"] = "RESEARCH_ONLY_HOLD"
        rows.append(row)

    # Clock-time forward Elo forecasts are original RESEARCH forecasts,
    # not Champion-001, and cannot be priced without matching exact markets.
    for forecast in report.get("research_forward_probability_rows") or []:
        if not isinstance(forecast, dict) or forecast.get("certified_prediction") is not False:
            raise ValueError("untrusted_forward_model_promotion")
        league = forecast.get("league")
        matchup = f"{forecast.get('away_team', '?')} @ {forecast.get('home_team', '?')}"
        for selection, prob_key in (
            ("home", "model_probability_home_win_research_only"),
            ("away", "model_probability_away_win_research_only"),
        ):
            p_value = forecast.get(prob_key)
            if selection == "away" and p_value is None and league == "nba":
                p_value = forecast.get("estimated_away_win_probability_research_only")
            p = _pct(p_value, fraction=True)
            if p is None:
                continue
            row = _base(league, matchup, "research_win_forecast", selection,
                        source="uncalibrated_original_forward_model_research_only",
                        at=forecast.get("forecast_recorded_utc"))
            row["model_probability_percent"] = p
            row["decision"] = "RESEARCH_ONLY_HOLD"
            rows.append(row)

    # Include NBA player-prop Over/Under prices directly in the universal
    # Sharp Edge dashboard, even when there are no fresh SharpAPI props. This
    # remains a labeled SGO archive display, NOT a player/model forecast.
    nba_slate = report.get("nba_slate_best_bets") or {}
    nba_prop_board = nba_slate.get("nba_player_props") or {}
    preview = nba_prop_board.get("preview_unranked_research_only") or []
    if not isinstance(preview, list):
        raise ValueError("invalid_NBA_prop_preview")
    # One sample per stat family maximizes coverage alongside 9 game
    # probabilities in the 40-row mobile preview; full props have own files.
    selected_families = set()
    for reference in preview:
        if not isinstance(reference, dict):
            raise ValueError("untrusted_NBA_prop_preview")
        family = reference.get("stat_family")
        if family in selected_families or len(selected_families) >= 10:
            continue
        if (reference.get("provider_player_team_assignment_verified") is not False
                or reference.get("player_active_today_verified") is not False
                or reference.get("bookmaker_checkout_verified") is not False
                or reference.get("independently_generated_prop_over_probability_percent") is not None
                or reference.get("independently_generated_prop_under_probability_percent") is not None
                or reference.get("independently_certified_prop_edge_pp") is not None
                or reference.get("independently_certified_prop_roi_percent") is not None):
            raise ValueError("untrusted_NBA_player_prop_promotion")
        selected_families.add(family)
        for side in ("over", "under"):
            row = _base(
                "nba",
                reference.get("source_labeled_matchup_unverified") + " (provider event label; player/team unverified)",
                "player_prop",
                side,
                reference.get("line"),
                reference.get(f"{side}_odds_american"),
                "archived_sgo_player_prop_provider_only_not_checkout",
                reference.get(f"{side}_source_quote_utc"),
            )
            row["player_name"] = reference.get("source_player_name_unverified")
            row["stat_family"] = family
            row["no_vig_market_probability_percent"] = _pct(
                reference.get(f"{side}_no_vig_market_percent"))
            row["break_even_probability_percent"] = _pct(
                reference.get(f"{side}_break_even_percent"))
            row["decision"] = "HOLD_UNVERIFIED_PLAYER_TEAM_AND_MODEL"
            rows.append(row)

    game = report.get("sharp_full_game_markets") or {}
    for match in (game.get("today_game_market_board") or [])[:15]:
        if not isinstance(match, dict):
            raise ValueError("untrusted_market_group")
        name = f"{match.get('away_team', '?')} @ {match.get('home_team', '?')}"
        for market, q in (match.get("paired_primary_markets") or {}).items():
            if market not in MARKETS[:3]:
                continue
            labels = ("over", "under") if market == "total_points" else ("home", "away")
            _paired(rows, match.get("league"), name, market, q,
                    q.get("home_or_over_line"), q.get("away_or_under_line"),
                    labels, (q.get("home_or_over_odds"), q.get("away_or_under_odds")),
                    q.get("provider_quote_utc"))

    props = report.get("sharp_player_props") or {}
    by_league = props.get("today_player_prop_market_probability_board") or {}
    for league in ("nba", "nfl"):
        for q in (by_league.get(league) or [])[:12]:
            if not isinstance(q, dict):
                raise ValueError("untrusted_prop_market")
            if (q.get("player_identity_independently_verified") is True
                    or q.get("active_player_independently_verified") is True):
                raise ValueError("untrusted_prop_identity_promotion")
            name = f"{q.get('player_name', '?')} — {q.get('prop_stat', '?')}"
            _paired(rows, league, name, "player_prop", q,
                    q.get("line"), q.get("line"), ("over", "under"),
                    (q.get("over_american_odds"), q.get("under_american_odds")),
                    q.get("last_capture_utc"))

    # This is a market-price MOVEMENT, not % of professional money. Only the
    # existing same-line, pre-start, age-qualified watchlist is shown.
    moves = []
    archive = report.get("sharp_archive") or {}
    for q in (archive.get("ranked_market_movement_watchlist") or [])[:8]:
        moves.append({
            "league": q.get("league"),
            "market": "moneyline",
            "matchup": f"{q.get('away_team', '?')} @ {q.get('home_team', '?')}",
            "market_price_movement_percentage_points":
                q.get("home_no_vig_change_percentage_points"),
            "sharp_money_handle_percent": None,
            "professional_bettor_identity_verified": False,
            "decision": "WATCH_RESEARCH_ONLY",
        })
    for q in (props.get("ranked_prop_repricing_watchlist") or [])[:8]:
        moves.append({
            "league": q.get("league"), "market": "player_prop",
            "matchup": f"{q.get('player_name', '?')} — {q.get('prop_stat', '?')}",
            "market_price_movement_percentage_points":
                q.get("over_no_vig_market_change_pp"),
            "sharp_money_handle_percent": None,
            "professional_bettor_identity_verified": False,
            "decision": "WATCH_RESEARCH_ONLY",
        })
    for q in (game.get("today_recent_market_repricing_watchlist") or [])[:8]:
        if q.get("changed_line_cannot_compare_probability"):
            continue
        moves.append({
            "league": q.get("league"), "market": q.get("market"),
            "matchup": f"{q.get('away_team', '?')} @ {q.get('home_team', '?')}",
            "market_price_movement_percentage_points":
                q.get("same_line_no_vig_market_price_change_pp"),
            "sharp_money_handle_percent": None,
            "professional_bettor_identity_verified": False,
            "decision": "WATCH_RESEARCH_ONLY",
        })
    return {
        "report_type": "FREDDYS_UNIVERSAL_PROBABILITY_SHARP_EDGE_RESEARCH_VIEW",
        "command": report.get("command"),
        "market_types_supported": list(MARKETS),
        "market_side_rows_total": len(rows),
        "market_side_rows": rows[:40],
        "market_movement_watchlist": moves[:15],
        "last_sharpapi_archived_quote_utc":
            archive.get("latest_eligible_capture_utc"),
        "nba_player_prop_archived_paired_markets":
            nba_prop_board.get("paired_source_prop_market_count", 0),
        "nba_player_prop_preview_stat_families": sorted(selected_families),
        "nba_player_prop_identity_verified": False,
        "native_model_probability_is_not_no_vig_market_probability": True,
        "sharp_bettor_handle_percentage_verified": False,
        "sharp_bettor_handle_percentage": None,
        "certified_positive_ev_bets": 0,
        "champion_001_modified": False,
        "decision": "RESEARCH_ONLY_HOLD" if rows or moves else "PASS_NO_QUALIFIED_EDGE",
        "notes": [
            "Model p% means original model forecast only when actually supplied.",
            "No-vig market p% and break-even p% come from quoted bookmaker prices, not model predictions.",
            "Model edge (pp) = model p% minus break-even p%. EV ROI% uses decimal payout and model p.",
            "Line movement in percentage points is not verified sharp money or bettor handle.",
            "No betting recommendation without exact-market independently calibrated model, fresh authenticated price, player/game identity and pregame receipt.",
            "N/A denotes unavailable evidence; it never means a zero-probability event or zero edge.",
        ],
    }


def render_dashboard(board):
    lines = [
        "## Probabilities and Sharp Edge — Every Run",
        f"**Command:** {_cell(board.get('command'))} · **Betting decision:** {_cell(board.get('decision'))}",
        "**Certified Champion-001 positive-EV bets: 0; stakes: $0.**",
        "Model p% (research only) is distinct from no-vig market p%, break-even p%, and genuine sharp-money handle.",
        "Edge is measured in **percentage points (pp)**; EV ROI is a separate return percentage.",
        "| Sport / matchup | Market / side | Line | Odds | Model p% | No-vig market p% | Break-even p% | Model edge (pp) | EV ROI% | Action |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in board.get("market_side_rows") or []:
        title = f"{_cell(r.get('league')).upper()} {_cell(r.get('matchup'))}"
        market = f"{_cell(r.get('market'))} / {_cell(r.get('selection'))}"
        if r.get("player_name"):
            title += f" / {_cell(r['player_name'])}"
        cols = [title, market, _cell(r.get("line")), _cell(r.get("american_odds")),
                _cell(r.get("model_probability_percent")),
                _cell(r.get("no_vig_market_probability_percent")),
                _cell(r.get("break_even_probability_percent")),
                _cell(r.get("model_edge_percentage_points")),
                _cell(r.get("expected_roi_percent")), _cell(r.get("decision"))]
        lines.append("| " + " | ".join(cols) + " |")
    if not board.get("market_side_rows"):
        for market in MARKETS:
            lines.append(f"| N/A | {market} | N/A | N/A | N/A | N/A | N/A | N/A | N/A | HOLD |")
    lines.extend([
        "",
        "**Price-movement watchlist (research only; never inferred professional sharp bets):**",
        "| Market | Matchup | Same-line market movement (pp) | Verified sharp handle % |",
        "|---|---|---:|---:|",
    ])
    for m in board.get("market_movement_watchlist") or []:
        lines.append(f"| {_cell(m.get('market'))} | {_cell(m.get('matchup'))} | "
                     f"{_cell(m.get('market_price_movement_percentage_points'))} | N/A |")
    if not board.get("market_movement_watchlist"):
        lines.append("| N/A | No age-qualified movement | N/A | N/A |")
    lines.extend([
        "",
        f"**Archived NBA two-sided player-prop market pairs:** "
        f"{_cell(board.get('nba_player_prop_archived_paired_markets'))}"
        " (player/team identities and prices UNVERIFIED).",
        "Full available player props: NBA_PLAYER_PROPS_ALL_MARKETS.md / .json in the run artifact.",
        f"**Last archived SharpAPI quote:** {_cell(board.get('last_sharpapi_archived_quote_utc'))} (not a live sportsbook checkout).",
        "**Professional sharp-bettor handle % / ticket %:** N/A / N/A (not supplied or independently verified).",
        "**Model edge / expected ROI:** N/A when no independently authored matching market forecast is available; never substitute market implied probability.",
        "**N/A is missing evidence, NOT 0%. All displayed markets remain HOLD until independently certified.**",
        "Download PROBABILITY_SHARP_EDGE_DASHBOARD.json for complete typed values, source timestamps and limitations.",
    ])
    return "\n".join(lines) + "\n"
