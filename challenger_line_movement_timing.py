"""Research-only chronological moneyline movement; never produces bets or model edges."""
import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import timezone
from challenger_moneyline_market_baseline import inspect_quote, MAX_PAIR_TIMESTAMP_SKEW_SECONDS

def analyze_line_movement(rows):
    """Pair home/away snapshots at each capture, then compare chronological snapshots.

    Do not compare across source, provider event ID, teams, or market identity.
    Require strictly pregame timestamps, valid price ages, and paired snapshots.
    """
    groups, excluded = defaultdict(list), Counter()
    for row in rows:
        item, reason = inspect_quote(row)
        if reason:
            excluded[reason] += 1
            continue
        r = item["raw"]
        if r["is_main_line"] is not True:
            excluded["main_line_not_confirmed_by_provider"] += 1
            continue
        key = (r["source"], r["league"], r["event_id"], r["sportsbook"],
               r["home_team"], r["away_team"], item["start"])
        groups[key].append(item)
    movements = []
    for key, items in groups.items():
        # Group observations by actual capture time, not by provider quote time.
        captures = defaultdict(list)
        for item in items:
            captures[item["received"]].append(item)
        snapshots = []
        for captured, batch in sorted(captures.items()):
            home = [x for x in batch if x["raw"]["selection_type"] == "home"]
            away = [x for x in batch if x["raw"]["selection_type"] == "away"]
            if len(home) != 1 or len(away) != 1:
                excluded["incomplete_or_duplicate_snapshot"] += 1
                continue
            h, a = home[0], away[0]
            if abs((h["quote"] - a["quote"]).total_seconds()) > MAX_PAIR_TIMESTAMP_SKEW_SECONDS:
                excluded["asynchronous_two_side_quotes"] += 1
                continue
            snapshots.append((captured, h, a))
        if len(snapshots) < 2:
            excluded["insufficient_distinct_snapshots"] += 1
            continue
        for before, after in zip(snapshots, snapshots[1:]):
            t0, h0, a0 = before
            t1, h1, a1 = after
            if t1 <= t0 or h1["quote"] < h0["quote"] or a1["quote"] < a0["quote"]:
                excluded["nonmonotonic_quote_timestamps"] += 1
                continue
            # A new capture is not evidence of movement unless the provider
            # updated at least one of the two sides.
            if h1["quote"] == h0["quote"] and a1["quote"] == a0["quote"]:
                excluded["no_provider_quote_update"] += 1
                continue
            start = key[6]
            p0 = h0["implied"] / (h0["implied"] + a0["implied"])
            p1 = h1["implied"] / (h1["implied"] + a1["implied"])
            movements.append({
                "record_type": "challenger_moneyline_movement_research_only",
                "source": key[0], "league": key[1], "provider_event_id": key[2],
                "sportsbook_labeled_by_aggregator": key[3],
                "home_team": key[4], "away_team": key[5],
                "event_start_utc": start.isoformat(),
                "first_capture_utc": t0.isoformat(), "last_capture_utc": t1.isoformat(),
                "first_provider_quote_utc": max(h0["quote"], a0["quote"]).isoformat(),
                "last_provider_quote_utc": max(h1["quote"], a1["quote"]).isoformat(),
                "minutes_between_captures": round((t1-t0).total_seconds()/60, 3),
                "minutes_before_start_at_last_capture": round((start-t1).total_seconds()/60, 3),
                "home_american_odds_before": h0["raw"]["odds_american"],
                "home_american_odds_after": h1["raw"]["odds_american"],
                "away_american_odds_before": a0["raw"]["odds_american"],
                "away_american_odds_after": a1["raw"]["odds_american"],
                "home_no_vig_probability_change_percentage_points": round((p1-p0)*100, 4),
                "direction": "toward_home" if p1 > p0 else "toward_away" if p1 < p0 else "unchanged",
                "market_data_independently_verified": False,
                "sharp_action_inferred": False, "positive_ev_certified": False,
                "bet_ready": False, "certified_prediction": False,
                "champion_001_modified": False,
            })
    return movements, {
        "report_type": "challenger_line_movement_timing_research_only",
        "movements": len(movements),
        "excluded": dict(sorted(excluded.items())),
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "Aggregator observations only; no independent DraftKings checkout or model edge."
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odds", required=True, nargs="+")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    rows = []
    for filename in args.odds:
        rows.extend(json.loads(line) for line in Path(filename).read_text(encoding="utf8").splitlines() if line.strip())
    movements, report = analyze_line_movement(rows)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "line_movement_timing.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in movements), encoding="utf8")
    (output / "line_movement_timing_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
