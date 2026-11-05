"""Read-only live all-eight-sport ESPN schedule preflight with original bytes.

A completed preflight is source-access diagnostic evidence, not a model pick.
No credentials, sportsbook requests, backdating, odds, or wagers are used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from independent_schedule_review import (
    SOURCES, ingest_schedule, download_json_original,
)
from challenger_prospective_pregame import build
from challenger_all_sports_schedule_coverage import audit

EASTERN = ZoneInfo("America/New_York")
LEAGUES = tuple(SOURCES)


def run(output_dir, fetch=None, clock=None, lookahead_days=7):
    """Capture and then independently revalidate original prospective receipts.

    For production use, fetch=None resolves the native original-byte HTTP
    fetcher and clock=None resolves real wall time. Fake test data may inject
    both, but never yields certified betting selections.
    """
    if type(lookahead_days) is not int or not 0 <= lookahead_days <= 7:
        raise ValueError("preflight_lookahead_outside_bounded_window")
    fetch = download_json_original if fetch is None else fetch
    clock = (lambda: datetime.now(timezone.utc)) if clock is None else clock
    first = clock()
    if not isinstance(first, datetime) or first.tzinfo is None:
        raise ValueError("preflight_start_clock_must_be_aware")
    first = first.astimezone(timezone.utc)
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError("preflight_requires_fresh_empty_capture_directory")
    root.mkdir(parents=True, exist_ok=True)
    source = ingest_schedule(
        first.astimezone(EASTERN).date().isoformat(),
        fetch=fetch, now=first, lookahead_days=lookahead_days,
        clock=clock, original_dir=root / "espn_original_schedule_bytes",
    )
    end = clock()
    if not isinstance(end, datetime) or end.tzinfo is None:
        raise ValueError("preflight_end_clock_must_be_aware")
    end = end.astimezone(timezone.utc)
    if end < first:
        raise ValueError("preflight_wall_clock_regressed")
    # The same true live timestamp is used by snapshot and source checks;
    # there are NO non-current bookmaker quotes or retrospective outcomes.
    records, report = build(source, [], [], None, end)
    coverage = audit(
        source, report, records,
        original_dir=root / "espn_original_schedule_bytes",
    )
    if (set(coverage["by_league"]) != set(LEAGUES)
        or coverage["totals"]["pregame_events_archived"] != len(records)
        or coverage["archived_games_matching_exact_original_event_fields"] != len(records)
        or coverage["original_espn_source_responses_verified"] != sum(
            v["source_days_succeeded"] for v in coverage["by_league"].values()
        )):
        raise ValueError("unreconciled_eight_sport_original_source_preflight")
    for k in (
        "qualified_chronological_training_games",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_bets",
        "bet_ready_selections",
        "automated_bets_placed",
    ):
        if coverage[k] != 0:
            raise ValueError("preflight_attempted_training_or_bet_certification")
    if (coverage["champion_001_modified"] is not False
        or coverage["original_source_hashes_independently_publisher_signed"] is not False
        or coverage["independent_league_schedule_verified"] is not False
        or coverage["historical_feature_publication_authenticated"] is not False):
        raise ValueError("preflight_promoted_unauthenticated_source")
    for filename, payload in (
        ("espn_schedule_capture.json", source),
        ("prospective_report.json", report),
        ("eight_sport_schedule_coverage.json", coverage),
    ):
        (root / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf8",
        )
    (root / "prospective_event_evidence.jsonl").write_text(
        "".join(json.dumps(v, sort_keys=True) + "\n" for v in records),
        encoding="utf8",
    )
    by_league = {}
    for league in LEAGUES:
        v = coverage["by_league"][league]
        future = [e for e in source["events"] if e["league"] == league]
        first_game = min(
            (e["requested_date_et"] for e in future), default=None,
        )
        by_league[league] = {
            "source_days_attempted": v["source_days_attempted"],
            "source_days_succeeded": v["source_days_succeeded"],
            "source_days_failed": v["source_days_failed"],
            "games_listed_in_checked_dates": v["source_game_listings"],
            "future_games_discovered": v["source_future_games_discovered"],
            "future_games_archived": v["archived_pregame_games"],
            "first_upcoming_slate_date_et": first_game,
            "coverage_class": v["coverage_class"],
        }
    summary = {
        "stage": "challenger_eight_sport_original_schedule_live_preflight_research_only",
        "started_at_utc": first.isoformat(),
        "completed_at_utc": end.isoformat(),
        "lookahead_days": lookahead_days,
        "leagues_checked": list(LEAGUES),
        "by_league": by_league,
        "totals": coverage["totals"],
        "original_response_bytes_verified":
            coverage["original_espn_source_responses_verified"],
        "archived_game_fields_verified":
            coverage["archived_games_matching_exact_original_event_fields"],
        "source_independently_authenticated": False,
        "official_league_schedule_independently_verified": False,
        "qualified_chronological_training_games": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "note": (
            "Original ESPN HTTP bytes and game identities corroborate this "
            "research capture only. No original publisher-signed timestamp, "
            "independent official league schedule, player status, "
            "verified sportsbook odds, or positive EV has been established."
        ),
    }
    (root / "preflight_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf8",
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", default="seven_day_source_preflight",
    )
    parser.add_argument("--lookahead-days", type=int, default=7)
    args = parser.parse_args(argv)
    report = run(args.output_dir, lookahead_days=args.lookahead_days)
    print(json.dumps({
        "stage": report["stage"],
        "totals": report["totals"],
        "by_league": {
            league: {
                "future_games_archived": r["future_games_archived"],
                "source_days_failed": r["source_days_failed"],
                "coverage_class": r["coverage_class"],
            } for league, r in report["by_league"].items()
        },
        "certified_positive_ev_bets": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
