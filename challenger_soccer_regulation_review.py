"""MLS/UCL 90-minute outcome review from an independent published source.

Research only. API Ninjas is an unaffiliated, separately published source,
not MLS/UEFA-operated adjudication or pregame feature proof. Its distinct
period_scores (two regulation halves, optional two extra-time halves) are
never conflated with penalty shootouts or a knockout qualification winner.
Absent API credentials produce explicit blocked research, not false zeros.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_multisport_original_bytes_lineage import REVIEW_RECORD
from challenger_prospective_outcome_validation import instant

LEAGUE_CODES = {"mls": "mls", "uefa_champions_league": "ucl"}
LEAGUE_TZ = {"mls": ZoneInfo("America/New_York"),
             "uefa_champions_league": ZoneInfo("Europe/Berlin")}
SOURCE = "https://api.api-ninjas.com/v1/soccermatches"
MAX_DATES_PER_LEAGUE = 3
MAX_EVENTS = 300
MAX_GAMES_PER_DAY = 150
MAX_BYTES = 3_000_000
MAX_KICKOFF_DISAGREEMENT = 30 * 60
STATUSES = {"scheduled", "in_progress", "final", "postponed", "cancelled"}
FINISH = {"regulation", "extra_time", "penalties"}

# Explicit identity aliases, only after confirming which exact clubs they mean.
# Never remove 'City', 'United', 'FC' or school/team suffixes generically.
EXACT_NAMES = {
    "inter miami cf": "inter miami",
    "atlanta united fc": "atlanta united",
    "new york city fc": "new york city fc",
    "new york red bulls": "new york red bulls",
    "los angeles fc": "lafc",
    "lafc": "lafc",
    "la galaxy": "la galaxy",
    "sporting kansas city": "sporting kansas city",
    "philadelphia union": "philadelphia union",
    "real salt lake": "real salt lake",
    "seattle sounders fc": "seattle sounders",
    "vancouver whitecaps": "vancouver whitecaps",
    "vancouver whitecaps fc": "vancouver whitecaps",
    "portland timbers": "portland timbers",
    "fc cincinnati": "fc cincinnati",
    "fc dallas": "fc dallas",
}


def name(value):
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())
    return EXACT_NAMES.get(cleaned, cleaned)


def request_url(league, day):
    if league not in LEAGUE_CODES or not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("invalid_soccer_league_or_day")
    datetime.strptime(day, "%Y-%m-%d")
    return SOURCE + "?" + urlencode({"league": LEAGUE_CODES[league], "date": day})


def fetch_source(league, day, api_key):
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("soccer_second_source_api_key_not_connected")
    req = Request(request_url(league, day), headers={"Accept": "application/json",
                           "X-Api-Key": api_key,
                           "User-Agent": "FreddysPicksSoccerResearch/1.0"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("soccer_provider_response_exceeds_limit")
    return raw


def goals(value):
    return type(value) is int and 0 <= value <= 25


def read_source(raw, league, day, observed):
    """Parse raw actual source bytes; return full match and 90-min separately."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("bad_soccer_original_source_bytes")
    response = json.loads(raw)
    if not isinstance(response, list) or len(response) > MAX_GAMES_PER_DAY:
        raise ValueError("unexpected_soccer_source_schema_or_count")
    rows, seen = [], set()
    for row in response:
        if not isinstance(row, dict) or row.get("league") != LEAGUE_CODES[league]:
            raise ValueError("soccer_source_wrong_league")
        event_id = row.get("game_id")
        if not isinstance(event_id, str) or not event_id.startswith(LEAGUE_CODES[league] + "-") or event_id in seen:
            raise ValueError("duplicate_or_invalid_soccer_source_id")
        seen.add(event_id)
        if row.get("status") not in STATUSES:
            raise ValueError("unknown_soccer_game_status")
        try:
            start = instant(row["start_time"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("missing_soccer_kickoff") from exc
        if start.astimezone(LEAGUE_TZ[league]).date().isoformat() != day or row.get("date") != day:
            raise ValueError("soccer_source_date_mismatch")
        h, a = row.get("home_team"), row.get("away_team")
        if not isinstance(h, dict) or not isinstance(a, dict):
            raise ValueError("missing_soccer_clubs")
        for team in (h, a):
            if (not isinstance(team.get("name"), str) or not team["name"].strip()
                    or not isinstance(team.get("team_id"), str) or not team["team_id"].startswith("soccer-")):
                raise ValueError("untrusted_soccer_club_identity")
        if not name(h["name"]) or not name(a["name"]) or name(h["name"]) == name(a["name"]) or h["team_id"] == a["team_id"]:
            raise ValueError("duplicate_soccer_club_identity")
        result = {"game_id": event_id, "start": start, "home": name(h["name"]),
                  "away": name(a["name"]), "home_id": h["team_id"], "away_id": a["team_id"],
                  "state": row["status"], "updated_at": None, "decided_in": None,
                  "regulation_score": None, "full_match_score": None, "regulation_result": None}
        if row["status"] == "final":
            try:
                revised = instant(row["updated_at"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError("missing_soccer_final_observation_time") from exc
            if not start < revised <= observed:
                raise ValueError("soccer_final_update_time_inconsistent")
            decided = row.get("decided_in")
            ps = row.get("period_scores")
            if decided not in FINISH or not isinstance(ps, dict):
                raise ValueError("soccer_final_has_no_known_regulation_periods")
            hg, ag = ps.get("home"), ps.get("away")
            required_periods = 2 if decided == "regulation" else 4
            if (not isinstance(hg, list) or not isinstance(ag, list)
                    or len(hg) != required_periods or len(ag) != required_periods
                    or not all(goals(x) for x in hg + ag)):
                raise ValueError("soccer_regulation_periods_incomplete_or_mixed")
            if (not goals(row.get("home_score")) or not goals(row.get("away_score"))
                    or row["home_score"] != sum(hg) or row["away_score"] != sum(ag)):
                raise ValueError("soccer_full_match_score_disagrees_with_periods")
            penalty = row.get("penalty_scores")
            if decided == "penalties":
                if (not isinstance(penalty, dict) or not goals(penalty.get("home"))
                        or not goals(penalty.get("away")) or penalty["home"] == penalty["away"]):
                    raise ValueError("soccer_shootout_score_missing_or_invalid")
            elif penalty is not None:
                raise ValueError("soccer_penalty_goals_outside_shootout")
            reg_h, reg_a = sum(hg[:2]), sum(ag[:2])
            result.update({"updated_at": revised.isoformat(), "decided_in": decided,
                           "regulation_score": {"home": reg_h, "away": reg_a},
                           "full_match_score": {"home": row["home_score"], "away": row["away_score"]},
                           "regulation_result": "home" if reg_h > reg_a else "away" if reg_a > reg_h else "draw"})
        rows.append(result)
    return rows


def validate_packet(packet, now):
    if (not isinstance(packet, dict) or packet.get("record_type") != REVIEW_RECORD
            or packet.get("league") not in LEAGUE_CODES
            or packet.get("original_bytes_match_same_run_receipt") is not True
            or packet.get("same_run_receipt_independently_authenticated") is not False
            or packet.get("qualified_for_challenger_training") is not False
            or packet.get("independent_outcome_review") is not False
            or packet.get("market_settlement_rules_verified") is not False
            or packet.get("certified_prediction") is not False
            or packet.get("bet_ready") is not False or packet.get("model_probability") is not None
            or packet.get("champion_001_modified") is not False):
        raise ValueError("unsafe_soccer_original_pregame_lineage")
    if not isinstance(packet.get("event_id"), str) or not packet["event_id"].isdigit():
        raise ValueError("missing_espn_soccer_event_id")
    start, pregame = instant(packet["event_start_utc"]), instant(packet["snapshot_completed_at_utc"])
    if not pregame < start < now:
        raise ValueError("soccer_event_not_after_pregame_and_before_review")
    final = packet.get("published_final_only")
    if final is not None:
        if not isinstance(final, dict) or not goals(final.get("home_score")) or not goals(final.get("away_score")):
            raise ValueError("invalid_espn_soccer_published_final")
        result = "home" if final["home_score"] > final["away_score"] else "away" if final["away_score"] > final["home_score"] else "draw"
        if result != final.get("published_result") or not start < instant(final["published_at_observation_utc"]) <= now:
            raise ValueError("espn_published_soccer_result_not_consistent")
    return start, final


def plan(packets, now, max_dates=MAX_DATES_PER_LEAGUE):
    if (not isinstance(packets, list) or len(packets) > MAX_EVENTS
            or not isinstance(now, datetime) or now.tzinfo is None
            or type(max_dates) is not int or not 1 <= max_dates <= MAX_DATES_PER_LEAGUE):
        raise ValueError("invalid_soccer_source_request_plan")
    seen = set()
    by_league = {league: set() for league in LEAGUE_CODES}
    for p in packets:
        start, final = validate_packet(p, now.astimezone(timezone.utc))
        key = (p["league"], p["event_id"])
        if key in seen:
            raise ValueError("duplicated_soccer_espn_event_id")
        seen.add(key)
        if final is not None:
            by_league[p["league"]].add(start.astimezone(LEAGUE_TZ[p["league"]]).date().isoformat())
    result = {}
    for league, days in by_league.items():
        for day in sorted(days, reverse=True)[:max_dates]:
            result[league + ":" + day] = (league, day)
    return result


def review(packets, raw_by_request, observed, max_dates=MAX_DATES_PER_LEAGUE, no_key=False):
    planned = plan(packets, observed, max_dates)
    parsed, errors, digests = {}, {}, {}
    for key, (league, day) in planned.items():
        raw = raw_by_request.get(key)
        if raw is None:
            errors[key] = "external_api_key_not_configured" if no_key else "external_source_unavailable"
        else:
            try:
                parsed[key] = read_source(raw, league, day, observed.astimezone(timezone.utc))
                digests[key] = hashlib.sha256(raw).hexdigest()
            except (TypeError, ValueError, OverflowError, UnicodeError, json.JSONDecodeError) as exc:
                errors[key] = "invalid_soccer_source_" + type(exc).__name__
    matches = {}
    for i, p in enumerate(packets):
        start, final = validate_packet(p, observed.astimezone(timezone.utc))
        day = start.astimezone(LEAGUE_TZ[p["league"]]).date().isoformat()
        key = p["league"] + ":" + day
        poss = []
        if final is not None and key in parsed:
            poss = [x for x in parsed[key] if x["home"] == name(p.get("home_team"))
                    and x["away"] == name(p.get("away_team"))
                    and name(p.get("home_team")) != name(p.get("away_team"))
                    and abs((x["start"] - start).total_seconds()) <= MAX_KICKOFF_DISAGREEMENT]
        matches[i] = (key, final, poss)
    # One provider game can never be matched to two distinct ESPN event IDs.
    overlaps = Counter((key, x["game_id"]) for key, final, poss in matches.values()
                       for x in poss if len(poss) == 1)
    out, status_counts = [], Counter()
    for i, p in enumerate(packets):
        key, final, possible = matches[i]
        league, day = p["league"], key.split(":", 1)[1]
        row = {"record_type": "challenger_soccer_ninety_minute_second_source_review_only",
               "league": league, "espn_event_id": p["event_id"],
               "provider_event_id": None, "provider_url": request_url(league, day) if key in planned else None,
               "provider_source_class": "api_ninjas_independently_published_unaffiliated",
               "provider_original_bytes_sha256": digests.get(key),
               "provider_observed_at_utc": observed.astimezone(timezone.utc).isoformat() if key in parsed else None,
               "provider_decided_in": None, "source_regulation_90min_score": None,
               "source_regulation_90min_result": None, "source_final_including_extra_time": None,
               "espn_published_full_match_score": {"home": final["home_score"], "away": final["away_score"]} if final else None,
               "original_pregame_feature_publication_independently_verified": False,
               "independent_league_official_regulation_result_authenticated": False,
               "bookmaker_three_way_settlement_verified": False,
               "qualified_for_challenger_training": False,
               "certified_prediction": False, "model_probability": None,
               "bet_ready": False, "champion_001_modified": False}
        if final is None:
            status = "missing_espn_published_final"
        elif key not in planned:
            status = "outside_bounded_provider_date_scope"
        elif key in errors:
            status = errors[key]
        elif len(possible) == 0:
            status = "no_exact_team_and_kickoff_match"
        elif len(possible) != 1:
            status = "ambiguous_publisher_event_match"
        elif overlaps[(key, possible[0]["game_id"])] != 1:
            status = "publisher_game_linked_to_multiple_espn_ids"
        else:
            match = possible[0]
            row["provider_event_id"] = match["game_id"]
            if match["state"] != "final":
                status = "publisher_event_not_final"
            else:
                row["provider_decided_in"] = match["decided_in"]
                row["source_regulation_90min_score"] = match["regulation_score"]
                row["source_regulation_90min_result"] = match["regulation_result"]
                row["source_final_including_extra_time"] = match["full_match_score"]
                comparison = match["full_match_score"] if match["decided_in"] != "regulation" else match["regulation_score"]
                if comparison != row["espn_published_full_match_score"]:
                    status = "separate_published_full_match_scores_disagree"
                elif match["decided_in"] != "regulation":
                    status = "ninety_minute_score_secondary_only_after_extra_time_or_penalties"
                else:
                    status = "regulation_score_agrees_with_espn_published_score_research_only"
        row["crosscheck_status"] = status
        status_counts[(league, status)] += 1
        out.append(row)
    by_league = {league: {s: v for (ll, s), v in sorted(status_counts.items()) if ll == league}
                 for league in LEAGUE_CODES}
    report = {"stage": "challenger_soccer_90_minute_outcome_second_source_review_only",
              "provider": "API Ninjas (not MLS or UEFA)",
              "reviewed_event_count": len(out), "requested_routes": {k: request_url(*x) for k, x in planned.items()},
              "provider_responses_valid": sorted(parsed), "source_errors": dict(sorted(errors.items())),
              "source_raw_sha256": dict(sorted(digests.items())), "by_league": by_league,
              "regulation_score_published_agreements": {l: by_league[l].get("regulation_score_agrees_with_espn_published_score_research_only", 0)
                                                        for l in LEAGUE_CODES},
              "independently_authenticated_training_games": 0,
              "certified_champion_001_predictions": 0, "certified_challenger_001_predictions": 0,
              "certified_positive_ev_bets": 0, "bet_ready_selections": 0, "automated_bets_placed": 0,
              "champion_001_modified": False,
              "warning": ("Two independently published scores do not authenticate historical pregame features or "
                          "settle DraftKings 90-minute three-way markets. Source-only 90-min period scores "
                          "during extra-time or shootout matches are NOT mislabeled as agreement with ESPN full match.")}
    return out, report


def run(packets, key=None, fetcher=fetch_source, now=None, max_dates=MAX_DATES_PER_LEAGUE):
    now = now or datetime.now(timezone.utc)
    reqs = plan(packets, now, max_dates)
    no_key = not isinstance(key, str) or not key.strip()
    raw, failures = {}, {}
    if not no_key:
        for name_key, (league, day) in reqs.items():
            try:
                raw[name_key] = fetcher(league, day, key)
            except (OSError, ValueError, TimeoutError, UnicodeError) as exc:
                failures[name_key] = type(exc).__name__
    rows, report = review(packets, raw, now, max_dates, no_key=no_key)
    report["source_requests_attempted"] = 0 if no_key else len(reqs)
    report["source_fetch_failures"] = failures
    report["api_key_configured"] = not no_key
    return rows, report, {k: v for k, v in raw.items() if k in report["source_raw_sha256"]}


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--lineage", required=True)
    a.add_argument("--output-dir", default="prospective_validation")
    a.add_argument("--max-days", type=int, default=MAX_DATES_PER_LEAGUE)
    args = a.parse_args(argv)
    if not 1 <= args.max_days <= MAX_DATES_PER_LEAGUE:
        a.error("max-days must be between 1 and 3")
    rows = [json.loads(line) for line in Path(args.lineage).read_text(encoding="utf8").splitlines() if line.strip()]
    packets = [r for r in rows if isinstance(r, dict) and r.get("league") in LEAGUE_CODES]
    checked, report, original = run(packets, key=os.environ.get("API_NINJAS_KEY"), max_dates=args.max_days)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "soccer_90min_second_source_review.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in checked), encoding="utf8")
    (dest / "soccer_90min_second_source_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    if original:
        folder = dest / "soccer_second_source_original_bytes"
        folder.mkdir(parents=True, exist_ok=True)
        for key, value in original.items():
            name_part = re.sub("[^a-zA-Z0-9_-]+", "_", key)
            target = folder / (name_part + ".json")
            if target.exists():
                raise FileExistsError("refusing_to_replace_soccer_source_bytes")
            target.write_bytes(value)
    print(json.dumps({"events_reviewed": report["reviewed_event_count"],
                      "api_key_configured": report["api_key_configured"],
                      "certified_positive_ev_bets": 0, "qualified_training_games": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
