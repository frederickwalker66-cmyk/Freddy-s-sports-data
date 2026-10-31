"""Eight-league, point-in-time Challenger evidence review queue (no model training).

Consumes the existing prospective pregame and published-outcome linkage outputs.
The queue is NOT a historical training file, independently audited final result,
sportsbook market settlement, calibrated probability, or bet recommendation.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from challenger_prospective_outcome_validation import instant, norm, validate_snapshot

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls",
           "uefa_champions_league")
BINARY_RESEARCH = frozenset(LEAGUES[:6])
THREE_WAY_RESEARCH = frozenset(LEAGUES[6:])
ESPN_HOST = "site.api.espn.com"


def _serialize(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _digest(obj):
    return hashlib.sha256(_serialize(obj).encode("utf-8")).hexdigest()


def _espn(url):
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    return p.scheme == "https" and p.hostname == ESPN_HOST


def _validate_form(form, snapshot_time):
    if not isinstance(form, dict):
        return False
    count = form.get("last_games")
    ids, urls = form.get("prior_espn_event_ids"), form.get("source_urls")
    if (type(count) is not int or not 3 <= count <= 5
            or not isinstance(ids, list) or len(ids) != count
            or any(not isinstance(x, str) or not x.isdigit() for x in ids)
            or len(set(ids)) != count
            or not isinstance(urls, list) or len(urls) != count
            or any(not _espn(url) for url in urls)):
        return False
    win_rate, margin = form.get("win_rate"), form.get("margin_average")
    if (type(win_rate) not in (int, float) or not math.isfinite(win_rate)
            or not 0 <= win_rate <= 1
            or type(margin) not in (int, float) or not math.isfinite(margin)
            or abs(margin) > 500
            or form.get("result_start_embargo_hours") != 48
            or form.get("historical_original_publication_times_verified") is not False):
        return False
    try:
        return instant(form["retrieval_asof_utc"]) <= snapshot_time
    except (KeyError, TypeError, OverflowError, ValueError):
        return False


def _linked_final_ok(link, snap, captured, now):
    if (link.get("status") != "linked_to_espn_published_final_only"
            or link.get("independent_league_outcome_verified") is not False
            or link.get("qualified_for_challenger_backtest") is not False
            or link.get("model_prediction_at_capture") is not None
            or link.get("bet_ready") is not False
            or link.get("champion_001_modified") is not False):
        return False
    final = link.get("published_outcome")
    if not isinstance(final, dict) or not _espn(final.get("source_url")):
        return False
    home, away = final.get("home"), final.get("away")
    if (type(home) is not int or type(away) is not int
            or not 0 <= home <= 999 or not 0 <= away <= 999):
        return False
    outcome = "home" if home > away else "away" if away > home else "draw"
    if final.get("result") != outcome:
        return False
    if (link.get("home_team") != snap.get("home_team")
            or link.get("away_team") != snap.get("away_team")
            or link.get("event_start_utc") != snap.get("event_start_utc")
            or link.get("both_teams_form_available_at_capture") is not
                snap.get("team_form_available_for_both_teams")):
        return False
    try:
        linked_capture = instant(link["snapshot_completed_at_utc"])
        start = instant(snap["event_start_utc"])
        final_seen = instant(final["published_retrieved_at_utc"])
    except (KeyError, ValueError, TypeError, OverflowError):
        return False
    return linked_capture == captured and captured < start < final_seen <= now


def build_review_queue(snapshots, linked, now):
    """Keep only deterministic earliest captures, reject ambiguous or revised finals."""
    if not isinstance(snapshots, list) or not isinstance(linked, list):
        raise ValueError("snapshots and linked results must be lists")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must include timezone")
    now = now.astimezone(timezone.utc)
    per_league = {league: Counter() for league in LEAGUES}
    rejected = Counter()
    snapshots_by_event = defaultdict(list)
    for row in snapshots:
        if not isinstance(row, dict):
            rejected["invalid_snapshot"] += 1
            continue
        league = row.get("league")
        if league not in LEAGUES:
            rejected["unsupported_sport"] += 1
            continue
        try:
            (src_league, eid), captured = validate_snapshot(row, now)
            assert src_league == league
        except (ValueError, KeyError, TypeError, OverflowError, AssertionError):
            per_league[league]["invalid_capture"] += 1
            continue
        snapshots_by_event[(league, eid)].append((captured, row))
    earliest = {}
    for key, group in snapshots_by_event.items():
        at = min(x[0] for x in group)
        first = [row for when, row in group if when == at]
        if len({_digest(x) for x in first}) != 1:
            per_league[key[0]]["conflicting_same_time_capture"] += 1
            continue
        earliest[key] = (at, first[0])
        per_league[key[0]]["valid_earliest_capture"] += 1

    linked_by_event = defaultdict(list)
    for link in linked:
        if not isinstance(link, dict) or link.get("league") not in LEAGUES:
            rejected["invalid_link"] += 1
            continue
        linked_by_event[(link["league"], str(link.get("espn_event_id")))].append(link)

    results = []
    for (league, eid), (captured, snap) in sorted(earliest.items()):
        items = linked_by_event.get((league, eid), [])
        if len(items) != 1:
            per_league[league]["missing_or_duplicate_linked_result"] += 1
            continue
        link = items[0]
        if not _linked_final_ok(link, snap, captured, now):
            per_league[league]["not_linked_or_untrusted_final"] += 1
            continue
        form_home, form_away = snap.get("home_team_form"), snap.get("away_team_form")
        form_good = (_validate_form(form_home, captured) and
                     _validate_form(form_away, captured) and
                     snap.get("team_form_available_for_both_teams") is True)
        if not form_good:
            per_league[league]["missing_or_unverified_form"] += 1
            # Do not manufacture 0.0 form values or create partial training rows.
            continue
        published = link["published_outcome"]
        result = published["result"]
        if league in BINARY_RESEARCH and result == "draw":
            per_league[league]["unexpected_draw_no_binary_moneyline_label"] += 1
            continue
        research_market = ("published_score_winner_binary_research"
                           if league in BINARY_RESEARCH
                           else "published_regulation_three_way_research")
        # Do not pretend a published score establishes a sportsbook's overtime,
        # tie, draw-no-bet, settlement or sport-specific market definitions.
        status = ("needs_league_rule_and_independent_outcome_review"
                  if league in BINARY_RESEARCH else
                  "needs_three_way_market_settlement_review")
        features = {
            "pregame_home_prior_win_rate": float(form_home["win_rate"]),
            "pregame_away_prior_win_rate": float(form_away["win_rate"]),
            "pregame_home_prior_margin_avg": float(form_home["margin_average"]),
            "pregame_away_prior_margin_avg": float(form_away["margin_average"]),
        }
        event = {
            "record_type": "challenger_eight_sport_evidence_review_queue_only",
            "league": league, "event_id": eid,
            "home_team": snap["home_team"], "away_team": snap["away_team"],
            "snapshot_utc": captured.isoformat(),
            "features_asof_utc": captured.isoformat(),
            "start_utc": snap["event_start_utc"],
            "published_outcome_seen_utc": published["published_retrieved_at_utc"],
            "features": features,
            "published_score_only": {"home": published["home"],
                                     "away": published["away"]},
            "published_result_research_label": result,
            "research_target": research_market,
            "review_status": status,
            "source_receipt_sha256_not_independently_verified": _digest(snap),
            "linked_receipt_sha256_not_independently_verified": _digest(link),
            "schedule_source_url": snap["schedule_source_url"],
            "published_result_url": published["source_url"],
            "independent_feature_asof_review": False,
            "independent_outcome_adjudication": False,
            "market_settlement_rules_verified": False,
            "qualified_for_challenger_backtest": False,
            "eligible_to_train_probability_model": False,
            "certified_prediction": False,
            "model_probability": None,
            "bet_ready": False, "champion_001_modified": False,
        }
        results.append(event)
        per_league[league]["research_review_queue"] += 1
    report = {
        "stage": "challenger_eight_sport_evidence_bridge_research_only",
        "generated_at_utc": now.isoformat(),
        "supported_leagues": list(LEAGUES),
        "binary_published_winner_research": sorted(BINARY_RESEARCH),
        "three_way_published_result_research": sorted(THREE_WAY_RESEARCH),
        "by_league": {k: dict(sorted(v.items())) for k,v in per_league.items()},
        "rejected": dict(sorted(rejected.items())),
        "review_queue_records": len(results),
        "independently_verified_training_records": 0,
        "trained_models_created": 0,
        "verified_draftkings_checkout_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": (
            "Published scores, capture timestamps and on-the-fly hashes alone "
            "do not prove independent as-of features or official settlement. "
            "Review queue is NOT historical_results.jsonl. Do not train on it."
        )
    }
    return results, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--linked-results", required=True)
    parser.add_argument("--output-dir", default="prospective_validation")
    args = parser.parse_args(argv)
    root = Path(args.snapshot_root)
    files = sorted(root.rglob("prospective_event_evidence.jsonl"))
    if not files:
        raise SystemExit("Missing archived original prospective snapshot data")
    snapshots = []
    for f in files:
        snapshots.extend(json.loads(s) for s in f.read_text(encoding="utf-8").splitlines()
                         if s.strip())
    links = Path(args.linked_results)
    if not links.is_file():
        raise FileNotFoundError("Missing outcome linkage report")
    linked = [json.loads(s) for s in links.read_text(encoding="utf-8").splitlines()
              if s.strip()]
    rows, summary = build_review_queue(snapshots, linked, datetime.now(timezone.utc))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output/"all_sports_evidence_review_queue.jsonl").write_text(
        "".join(_serialize(row) + "\n" for row in rows), encoding="utf-8")
    (output/"all_sports_evidence_report.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
