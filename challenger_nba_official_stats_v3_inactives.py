"""NBA-operated Stats BoxScoreSummaryV3 explicit inactive rows: pregame research ONLY.

Source: https://stats.nba.com/stats/boxscoresummaryv3?GameID=...
V3 homeTeam.inactives/awayTeam.inactives enumerate explicit INACTIVE
entries, not the complete NBA official Active List. Never treat an absent
player as ACTIVE, use a post-tipoff response as pregame, or infer bets.
Hosted clients may receive 403/timeouts; report missing evidence, no bypass.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from challenger_nba_schedule_clock import (
    nba_team_name, official_nba_events, NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL,
)
from challenger_nba_daily_scoreboard_fallback import (
    validate_same_day_scoreboard, source_game_records,
)
from challenger_nba_injury_pdf_player_rows import TEAM_CODES, TEAMS
from challenger_nba_player_two_source_review import canonical
from challenger_prospective_outcome_validation import instant

STATS_URL = "https://stats.nba.com/stats/boxscoresummaryv3?GameID={}"
MAX_GAMES = 4
MAX_BYTES = 4_000_000
MAX_SCHEDULE_BYTES = 18_000_000
CAPTURE_WINDOW_MINUTES = 120
OUTCOME_TYPE = "challenger_nba_stats_v3_explicit_pregame_inactive_research_only"
ZERO_KEYS = (
    "independently_confirmed_game_day_active_players",
    "independently_confirmed_game_day_inactive_players",
    "verified_nba_espn_draftkings_player_id_crosswalks",
    "qualified_player_prop_training_observations",
    "certified_champion_001_predictions",
    "certified_challenger_001_predictions",
    "certified_positive_ev_bets",
    "bet_ready_selections",
    "automated_bets_placed",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc(clock):
    at = clock()
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("naive_nba_stats_inactive_observation_clock")
    return at.astimezone(timezone.utc)


def stats_url(gid):
    if not isinstance(gid, str) or re.fullmatch(r"\d{10}", gid) is None:
        raise ValueError("invalid_nba_stats_inactive_game_id")
    return STATS_URL.format(gid)


def fetch_stats(url):
    if not url.startswith("https://stats.nba.com/stats/boxscoresummaryv3?GameID="):
        raise ValueError("unapproved_stats_inactive_source_host")
    game_id = url.rsplit("=", 1)[-1]
    if url != stats_url(game_id):
        raise ValueError("unapproved_stats_inactive_source_query")
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "FreddysPicksOfficialPregameInactiveResearch/1.0",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    })
    with urlopen(req, timeout=15) as resp:
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("nba_stats_inactive_source_exceeded_size_limit")
    return raw


def _decode(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("missing_or_oversized_nba_stats_inactive_source_bytes")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get("boxScoreSummary"), dict):
        raise ValueError("nba_stats_v3_summary_schema_unrecognized")
    return obj["boxScoreSummary"]


def verify_inputs(roster_dir, now=None):
    """Read actual archived NBA-owned season schedule and original receipts."""
    root = Path(roster_dir)
    report = json.loads((root / "nba_pregame_roster_identity_report.json").read_text())
    if not isinstance(report, dict) or report.get("stage") != (
        "challenger_nba_scheduled_roster_identity_review_only"
    ):
        raise ValueError("missing_unqualified_official_nba_roster_capture")
    for key in (
        "independently_confirmed_active_players",
        "verified_nba_to_espn_to_draftkings_player_id_crosswalks",
        "qualified_player_prop_training_observations",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_bets",
        "bet_ready_selections",
        "automated_bets_placed",
    ):
        if report.get(key) != 0:
            raise ValueError("promoted_nba_inactive_input_evidence")
    if report.get("champion_001_modified") is not False:
        raise ValueError("champion_001_changed_in_roster_archive")
    hashes = report.get("original_source_sha256")
    if not isinstance(hashes, dict) or report.get(
        "official_schedule_source_available"
    ) is not True:
        return None, report, []
    expected = hashes.get("nba_official_schedule.json")
    if (not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected)
        or report.get("official_nba_schedule_original_sha256") != expected):
        raise ValueError("original_nba_schedule_sha_manifest_missing")
    raw = (root / "nba_roster_original_source_bytes" /
           "nba_official_schedule.json").read_bytes()
    if (not 1 <= len(raw) <= MAX_SCHEDULE_BYTES or sha(raw) != expected):
        raise ValueError("altered_nba_original_schedule_bytes")
    schedule = json.loads(raw)
    source_url = report.get("official_nba_schedule_source_url")
    if source_url == NBA_TODAY_SCOREBOARD_URL:
        # Only actual capture-time same-day NBA board; no yesterday board
        # or a source replayed hours later masquerading as a new pregame quote.
        recorded=instant(report.get("official_nba_schedule_observed_at_utc"))
        if now is not None:
            if recorded>now or (now-recorded).total_seconds()>600:
                raise ValueError("stale_daily_scoreboard_receipt_for_inactive_review")
        validate_same_day_scoreboard(raw,recorded)
    elif source_url not in (None,NBA_SCHEDULE_URL):
        raise ValueError("untrusted_nba_official_schedule_source_url")
    games = official_nba_events(schedule)
    raw_by_id, source_kind = source_game_records(schedule)
    claimed_kind=report.get("official_nba_schedule_source_kind")
    if claimed_kind is not None and claimed_kind!=source_kind:
        raise ValueError("nba_schedule_source_kind_mismatch")
    results = []
    for g in games:
        gid = g["official_nba_game_id"]
        if gid not in raw_by_id or not re.fullmatch(r"\d{10}", gid):
            continue
        if (g["home"] not in TEAMS or g["away"] not in TEAMS):
            continue
        results.append(dict(g, ids=raw_by_id[gid]))
    return schedule, report, results


def plan(games, now, limit=MAX_GAMES):
    if type(limit) is not int or not 1 <= limit <= MAX_GAMES:
        raise ValueError("invalid_nba_stats_inactive_request_budget")
    selected = []
    for g in games:
        delta = (g["start"] - now).total_seconds()
        if 0 < delta <= CAPTURE_WINDOW_MINUTES * 60:
            selected.append(g)
    return sorted(selected, key=lambda g: (g["start"], g["official_nba_game_id"]))[:limit]


def parse_stats_v3(raw, game, observed):
    """Require NBA-operated scheduled state, exact game and team IDs."""
    data = _decode(raw)
    if str(data.get("gameId")) != game["official_nba_game_id"]:
        raise ValueError("nba_stats_v3_wrong_game")
    if data.get("gameStatus") not in (1, "1"):
        raise ValueError("nba_stats_v3_not_pregame_scheduled_state")
    source_start = instant(data.get("gameTimeUTC"))
    if (abs((source_start - game["start"]).total_seconds()) > 60 or
        not observed < game["start"]):
        raise ValueError("nba_stats_v3_invalid_pregame_game_clock")
    values = []
    seen_ids = set()
    for side in ("home", "away"):
        team = data.get(side + "Team")
        if not isinstance(team, dict):
            raise ValueError("nba_stats_v3_missing_team")
        club = nba_team_name((team.get("teamCity") or "") + " " +
                             (team.get("teamName") or ""))
        if (club != game[side] or str(team.get("teamId")) != game["ids"][side]
            or club not in TEAMS or team.get("teamTricode") != TEAMS[club]):
            raise ValueError("nba_stats_v3_game_team_identity_mismatch")
        inactives = team.get("inactives")
        if not isinstance(inactives, list) or len(inactives) > 35:
            raise ValueError("nba_stats_v3_explicit_inactives_unavailable")
        for p in inactives:
            if not isinstance(p, dict):
                raise ValueError("nba_stats_v3_bad_inactive_entry")
            person = p.get("personId")
            name = (str(p.get("firstName") or "") + " " +
                    str(p.get("familyName") or "")).strip()
            if (type(person) not in (int, str) or not str(person).isdigit()
                or not canonical(name) or str(person) in seen_ids):
                raise ValueError("duplicate_or_unidentified_nba_stats_inactive")
            seen_ids.add(str(person))
            values.append({
                "record_type": OUTCOME_TYPE,
                "league": "nba",
                "official_nba_game_id": game["official_nba_game_id"],
                "official_nba_person_id": str(person),
                "nba_team_id": game["ids"][side],
                "nba_team_name": game[side],
                "source_inactive_name": name,
                "source_explicit_inactive_pregame": True,
                "source_observed_at_utc": observed.isoformat(),
                "game_start_utc": game["start"].isoformat(),
                "source_club_side": side,
                "official_final_active_list_authenticated": False,
                "confirmed_final_game_inactive": False,
                "all_nonlisted_players_assumed_active": False,
                "player_participation_or_dnp_verified": False,
                "bookmaker_prop_eligibility_verified": False,
                "independent_pregame_minutes_verified": False,
                "qualified_for_prop_training": False,
                "model_probability": None,
                "certified_prediction": False,
                "bet_ready": False,
                "champion_001_modified": False,
            })
    return values


def run(roster_dir, now=None, fetcher=None, clock=None, max_games=MAX_GAMES):
    clock = clock or (lambda: datetime.now(timezone.utc))
    now = now or utc(clock)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("naive_nba_stats_inactive_start_time")
    now = now.astimezone(timezone.utc)
    fetcher = fetcher or fetch_stats
    _, upstream, games = verify_inputs(roster_dir, now)
    report = {
        "stage": "challenger_official_nba_stats_v3_inactive_pregame_review_only",
        "observed_at_utc": now.isoformat(),
        "nba_stats_v3_source": "https://stats.nba.com/stats/boxscoresummaryv3",
        "max_games_per_scan": MAX_GAMES,
        "upstream_nba_game_identity_source":
            upstream.get("official_nba_schedule_source_kind"),
        "upstream_nba_game_identity_source_url":
            upstream.get("official_nba_schedule_source_url"),
        "upstream_nba_game_identity_source_sha256":
            upstream.get("official_nba_schedule_original_sha256"),
        "eligible_scheduled_games": 0,
        "source_requests_attempted": 0,
        "source_responses_parsed": 0,
        "explicit_source_inactive_rows": 0,
        "source_failures": {},
        "observed_game_source_sha256": {},
        "official_final_active_list_authenticated": False,
        "complete_game_day_active_list_available": False,
        "no_inactive_rows_does_not_mean_everyone_active": True,
        "independently_confirmed_game_day_active_players": 0,
        "independently_confirmed_game_day_inactive_players": 0,
        "verified_nba_espn_draftkings_player_id_crosswalks": 0,
        "qualified_player_prop_training_observations": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("NBA-operated BoxScoreSummaryV3 provides explicit game inactives. "
                    "Access and availability before tipoff are not guaranteed. "
                    "Even a pregame inactive row is not authenticated full official "
                    "Active List or sportsbook settlement; absence implies nothing."),
    }
    if upstream.get("official_schedule_source_available") is not True:
        report["status"] = "original_nba_schedule_unavailable_no_requests"
        return [], report, {}
    selected = plan(games, now, max_games)
    report["eligible_scheduled_games"] = len(selected)
    if not selected:
        report["status"] = "no_upcoming_game_inside_120min_window"
        return [], report, {}
    results, raw_sources, failures = [], {}, Counter()
    for game in selected:
        gid = game["official_nba_game_id"]
        report["source_requests_attempted"] += 1
        try:
            source = fetcher(stats_url(gid))
            after = utc(clock)
            if not now <= after < game["start"]:
                raise ValueError("nba_stats_v3_fetch_completed_after_tipoff_or_before_run")
            rows = parse_stats_v3(source, game, after)
            if not isinstance(source, bytes):
                raise ValueError("nba_stats_v3_source_not_original_bytes")
            raw_sources[gid] = source
            report["observed_game_source_sha256"][gid] = sha(source)
            results.extend(rows)
            report["source_responses_parsed"] += 1
        except (OSError, ValueError, TypeError, TimeoutError, KeyError,
                UnicodeError, OverflowError) as exc:
            failures[type(exc).__name__] += 1
    report["source_failures"] = dict(sorted(failures.items()))
    report["explicit_source_inactive_rows"] = len(results)
    report["status"] = "nba_stats_v3_pregame_evidence_review_only" if raw_sources else "source_denied_or_not_ready"
    return results, report, raw_sources


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster-dir", required=True)
    p.add_argument("--output-dir", default="nba_stats_v3_inactive_research")
    p.add_argument("--max-games", type=int, default=MAX_GAMES)
    a = p.parse_args(argv)
    results, report, sources = run(a.roster_dir, max_games=a.max_games)
    root = Path(a.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "nba_stats_v3_inactive_review.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in results), encoding="utf8")
    (root / "nba_stats_v3_inactive_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    if sources:
        base = root / "nba_stats_v3_original_source_bytes"
        base.mkdir(parents=True, exist_ok=True)
        for gid, raw in sorted(sources.items()):
            path = base / (gid + ".json")
            if path.exists():
                raise FileExistsError("refuse_to_overwrite_nba_stats_v3_original_source")
            path.write_bytes(raw)
    print(json.dumps({"source": report["status"],
                      "explicit_inactives_observed": len(results),
                      "confirmed_active": 0,
                      "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
