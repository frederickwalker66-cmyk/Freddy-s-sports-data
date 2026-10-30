"""Research-only paired full-game moneyline market baseline.

Computes the two-way no-vig market price reference (NOT a predictive model)
from archived DraftKings-labeled aggregator quotes. Provider prices, market
identity and lineup status remain unverified at actual DraftKings checkout.
Only complete, unambiguous, pregame two-way winner markets enter this report.
No trained models, certified picks, betting instructions, or wager placement.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from challenger_audit import parse_utc

BINARY_LEAGUES = {"nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "wnba"}
SOURCES = {"sharpapi_rest", "sportsgameodds_v2"}
MAX_PROVIDER_QUOTE_AGE_SECONDS = 900
MAX_PAIR_TIMESTAMP_SKEW_SECONDS = 120
MAX_OVERROUND = 1.30


def implied(american):
    if type(american) not in (int, float) or not math.isfinite(american) or abs(american) < 100:
        raise ValueError("invalid American odds")
    return (100 / (american + 100)) if american > 0 else (abs(american) / (abs(american) + 100))


def inspect_quote(row):
    if not isinstance(row, dict):
        return None, "invalid_row"
    if (row.get("source") not in SOURCES or row.get("sportsbook") != "draftkings"
            or row.get("record_type") != "pregame_odds_observation"
            or row.get("certified_prediction") is not False
            or row.get("model_probability") is not None
            or row.get("is_player_prop") is not False
            or row.get("market_type") != "moneyline"
            or row.get("league") not in BINARY_LEAGUES):
        return None, "unsupported_or_untrusted_market"
    if (row.get("is_alternate_line") is not False
            or row.get("is_main_line") not in (True, False)
            or row.get("line") is not None
            or row.get("selection_type") not in ("home", "away")):
        return None, "unconfirmed_market_identity"
    team = row.get("home_team") if row["selection_type"] == "home" else row.get("away_team")
    if (not isinstance(team, str) or not team.strip()
            or not isinstance(row.get("event_id"), str) or not row["event_id"].strip()
            or not isinstance(row.get("selection"), str)
            or row["selection"].strip() != team.strip()
            or row.get("home_team") == row.get("away_team")):
        return None, "team_or_event_mismatch"
    try:
        start = parse_utc(row["event_start_time"])
        quote = parse_utc(row["timestamp"])
        received = parse_utc(row["recorded_at"])
        age = (received - quote).total_seconds()
        if not (0 <= age <= MAX_PROVIDER_QUOTE_AGE_SECONDS
                and quote < start and received < start):
            return None, "not_timestamped_pregame_archive"
        p = implied(row["odds_american"])
    except (KeyError, ValueError, TypeError, OverflowError):
        return None, "bad_odds_or_timestamp"
    return {"raw": row, "start": start, "quote": quote,
            "received": received, "implied": p}, None


def compare_pairs(raw, validation):
    if not isinstance(raw, list) or not isinstance(validation, dict):
        raise ValueError("expected audited raw observations")
    if validation.get("observations") != len(raw):
        raise ValueError("validation count does not match source")
    if (validation.get("champion_001_modified") is not False
            or any(validation.get(k) != 0 for k in (
                "certified_champion_001_predictions", "certified_challenger_predictions",
                "bet_ready_selections", "automated_bets_placed",
                "independently_reverified_sportsbook_prices"))):
        raise ValueError("cannot analyze certified or promoted records")
    grouped = defaultdict(list)
    drops = Counter()
    for row in raw:
        item, reason = inspect_quote(row)
        if reason:
            drops[reason] += 1
            continue
        x = item["raw"]
        key = (x["source"], x["league"], x["event_id"], x["sportsbook"])
        grouped[key].append(item)
    pairs = []
    for (source, league, event_id, sportsbook), items in sorted(grouped.items()):
        sides = defaultdict(list)
        for item in items:
            sides[item["raw"]["selection_type"]].append(item)
        # Even if two alternate providers or duplicate odds IDs refer to the
        # same game, do NOT choose an arbitrary price for either side.
        if len(sides["home"]) != 1 or len(sides["away"]) != 1:
            drops["missing_or_duplicate_two_sides"] += 1
            continue
        h, a = sides["home"][0], sides["away"][0]
        if (h["start"] != a["start"]
                or h["raw"]["home_team"] != a["raw"]["home_team"]
                or h["raw"]["away_team"] != a["raw"]["away_team"]
                or abs((h["quote"] - a["quote"]).total_seconds()) > MAX_PAIR_TIMESTAMP_SKEW_SECONDS):
            drops["inconsistent_event_or_price_times"] += 1
            continue
        overround = h["implied"] + a["implied"]
        if not (1 <= overround <= MAX_OVERROUND):
            drops["implausible_market_overround"] += 1
            continue
        p_home = h["implied"] / overround
        pairs.append({
            "record_type": "paired_aggregator_moneyline_market_baseline_research_only",
            "source": source, "sportsbook_labeled_by_aggregator": sportsbook,
            "league": league, "provider_event_id": event_id,
            "home_team": h["raw"]["home_team"],
            "away_team": a["raw"]["away_team"],
            "event_start_utc": h["start"].isoformat(),
            "home_odds_american": h["raw"]["odds_american"],
            "away_odds_american": a["raw"]["odds_american"],
            "home_quote_updated_utc": h["quote"].isoformat(),
            "away_quote_updated_utc": a["quote"].isoformat(),
            "observations_received_by_utc": max(h["received"], a["received"]).isoformat(),
            "market_home_implied_probability": round(h["implied"], 6),
            "market_away_implied_probability": round(a["implied"], 6),
            "market_no_vig_home_probability_research_only": round(p_home, 6),
            "market_overround": round(overround, 6),
            "market_vig_percentage_points": round((overround - 1) * 100, 4),
            "provider_main_line_flag_for_both": (
                h["raw"]["is_main_line"] is True and a["raw"]["is_main_line"] is True),
            "market_probabilities_are_not_model_predictions": True,
            "draftkings_checkout_verified": False,
            "independently_verified_primary_line": False,
            "qualified_for_challenger_backtest": False,
            "certified_prediction": False,
            "bet_ready": False, "shadow_stake_usd": 0,
            "champion_001_modified": False,
        })
    report = {
        "report_type": "challenger_full_game_two_way_market_baseline_research_only",
        "source_rows_seen": len(raw),
        "moneyline_event_groups_seen": len(grouped),
        "two_way_research_market_pairs": len(pairs),
        "pairs_by_league": dict(sorted(Counter(x["league"] for x in pairs).items())),
        "excluded_rows_or_event_groups": dict(sorted(drops.items())),
        "market_implied_not_model_generated": True,
        "independently_verified_checkout_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "positive_ev_candidates_certified": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("No-vig probabilities only describe paired market prices, "
                    "NOT a model, value edge, or betting recommendation. "
                    "Unconfirmed market primary lines and old quotes remain quarantined."),
    }
    return pairs, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--odds", required=True)
    p.add_argument("--validation", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    rows = [json.loads(l) for l in Path(args.odds).read_text(encoding="utf8").splitlines() if l.strip()]
    validation = json.loads(Path(args.validation).read_text(encoding="utf8"))
    pairs, report = compare_pairs(rows, validation)
    dst = Path(args.output_dir)
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "moneyline_market_baselines.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in pairs), encoding="utf8")
    (dst / "moneyline_market_baseline_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
