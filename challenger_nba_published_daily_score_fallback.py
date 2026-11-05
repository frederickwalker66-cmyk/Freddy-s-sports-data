"""#97–99: bounded NBA-operated historical ScoreboardV3 finals crosscheck.

The main NBA season JSON often fails (HTTP 403/other). This fetches at most
four date-scoped NBA-owned original JSON scoreboards and corroborates final
scores for EXISTING ESPN pregame research candidates. Never infers historical
source-publication timestamps, permits training, or prices a sportsbook.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_backtest import timestamp
from challenger_nba_schedule_clock import (
    nba_team_name, stats_scoreboard_url,
)
from challenger_nba_official_pregame_schedule import CANONICAL_IDS
from challenger_nba_official_final_crosscheck import (
    RESEARCH_STATUS, MAX_TIME_DIFFERENCE_SECONDS,
)

ET = ZoneInfo("America/New_York")
MAX_DAYS = 4
MAX_SOURCE_BYTES = 12_000_000
SOURCE_STATUS = "nba_date_scoped_original_scoreboard_final_agreement_research_only"


def source_failure_label(exc):
    if isinstance(exc, HTTPError):
        return "HTTP_" + str(exc.code)
    if isinstance(exc, (URLError, TimeoutError)):
        return type(exc).__name__
    return type(exc).__name__


def download_original_scoreboard(url):
    """NBA-owned canonical URL only. One bounded request, no access bypass."""
    if not isinstance(url, str) or not url.startswith(
            "https://stats.nba.com/stats/scoreboardv3?GameDate="):
        raise ValueError("unapproved_source_url")
    day = url.split("GameDate=", 1)[1].split("&", 1)[0]
    if url != stats_scoreboard_url(day):
        raise ValueError("noncanonical_nba_scoreboard_url")
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
    })
    with urlopen(req, timeout=8) as resp:
        raw = resp.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("oversized_nba_original_response")
    return raw


def parse_original_finals(raw, required_day):
    """Validate raw NBA Stats V3 game final identities, teams and scores."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise ValueError("missing_bounded_original_scoreboard_bytes")
    if not isinstance(required_day, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", required_day):
        raise ValueError("invalid_requested_nba_date")
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("scoreboard"), dict):
        raise ValueError("invalid_nba_stats_v3_document")
    board = doc["scoreboard"]
    if board.get("leagueId") != "00" or board.get("gameDate") != required_day:
        raise ValueError("not_original_nba_scoreboard_for_requested_date")
    games = board.get("games")
    if not isinstance(games, list) or len(games) > 25:
        raise ValueError("invalid_nba_game_count")
    seen = set()
    result = []
    for game in games:
        if not isinstance(game, dict):
            raise ValueError("invalid_nba_game")
        gid = str(game.get("gameId"))
        if not re.fullmatch(r"\d{10}", gid) or gid in seen:
            raise ValueError("duplicate_or_invalid_nba_game_id")
        seen.add(gid)
        if game.get("gameStatus") not in (1, 2, 3, "1", "2", "3"):
            raise ValueError("unknown_nba_game_status")
        names = []
        scores = []
        for side in ("homeTeam", "awayTeam"):
            t = game.get(side)
            if not isinstance(t, dict):
                raise ValueError("missing_nba_official_team")
            name = nba_team_name(str(t.get("teamCity") or "") + " " +
                                 str(t.get("teamName") or ""))
            team_id = t.get("teamId")
            if (name not in CANONICAL_IDS
                    or type(team_id) not in (int, str)
                    or str(team_id) != CANONICAL_IDS[name]):
                raise ValueError("nba_official_team_id_name_disagreement")
            names.append(name)
            scores.append(t.get("score"))
        if names[0] == names[1]:
            raise ValueError("same_nba_team_on_both_sides")
        tipoff = timestamp(game.get("gameTimeUTC"))
        if tipoff.astimezone(ET).date().isoformat() != required_day:
            raise ValueError("nba_official_game_calendar_date_mismatch")
        is_final = game["gameStatus"] in (3, "3")
        if is_final and (any(type(s) is not int or not 0 <= s <= 999
                             for s in scores) or scores[0] == scores[1]):
            raise ValueError("invalid_nba_final_score")
        result.append({
            "official_nba_game_id": gid,
            "start_utc": tipoff,
            "home_team": names[0],
            "away_team": names[1],
            "home_score": scores[0] if is_final else None,
            "away_score": scores[1] if is_final else None,
            "status": "official_final" if is_final else "not_final",
        })
    return result


def review(candidates, primary, now, fetcher=None,
           max_days=MAX_DAYS):
    if (not isinstance(now, datetime) or now.tzinfo is None
            or not isinstance(candidates, list) or not isinstance(primary, list)
            or type(max_days) is not int or not 1 <= max_days <= 6):
        raise ValueError("invalid_nba_daily_review_inputs")
    now = now.astimezone(timezone.utc)
    if fetcher is None:
        fetcher = download_original_scoreboard
    primary_ids = {}
    for p in primary:
        if (not isinstance(p, dict)
                or not str(p.get("espn_research_event_id", "")).isdigit()
                or p.get("training_row_qualified") is not False
                or p.get("champion_001_modified") is not False
                or p.get("bet_ready") is not False
                or p.get("certified_prediction") is not False
                or p["espn_research_event_id"] in primary_ids):
            raise ValueError("missing_or_unsafe_primary_nba_score_crosscheck")
        primary_ids[p["espn_research_event_id"]] = p

    groups = defaultdict(list)
    seen = set()
    for c in candidates:
        if (not isinstance(c,dict)
                or c.get("record_type") !=
                    "challenger_nba_history_candidate_review_only"
                or c.get("league") != "nba"
                or c.get("market_type") != "moneyline"
                or c.get("selection_type") != "home"
                or c.get("qualified_for_challenger_backtest") is not False
                or c.get("eligible_to_train_probability_model") is not False
                or c.get("independent_asof_review") is not False
                or c.get("independent_outcome_review") is not False
                or c.get("model_probability") is not None
                or c.get("champion_001_modified") is not False
                or c.get("bet_ready") is not False
                or c.get("certified_prediction") is not False
                or not isinstance(c.get("event_id"), str)
                or not c["event_id"].isdigit()
                or c["event_id"] in seen
                or c["event_id"] not in primary_ids):
            raise ValueError("unsafe_nba_history_candidate_or_unmatched_primary")
        seen.add(c["event_id"])
        start = timestamp(c["start_utc"])
        snap = timestamp(c["snapshot_utc"])
        result_at = timestamp(c["outcome_verified_at_utc"])
        if not snap < start < result_at <= now:
            raise ValueError("historical_result_time_not_really_past")
        day = start.astimezone(ET).date().isoformat()
        groups[day].append(c)
    if seen != set(primary_ids):
        raise ValueError("primary_nba_result_candidate_count_mismatch")
    days = sorted(groups, reverse=True)[:max_days]
    originals = {}
    errors = {}
    games_by_day = {}
    for day in days:
        url = stats_scoreboard_url(day)
        try:
            raw = fetcher(url)
            games = parse_original_finals(raw, day)
            originals[day] = {
                "raw": raw,
                "url": url,
                "observed_at_utc": now.isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "game_count": len(games),
            }
            games_by_day[day] = games
        except (OSError, ValueError, TypeError, KeyError, OverflowError,
                json.JSONDecodeError) as exc:
            errors[day] = source_failure_label(exc)
            games_by_day[day] = []

    rows = []
    counts = Counter()
    for day in sorted(groups):
        for c in groups[day]:
            event = c["event_id"]
            original = dict(primary_ids[event])
            if (original.get("home_team") != c["home_team"]
                    or original.get("away_team") != c["away_team"]
                    or original.get("espn_published_score") != c["published_score_only"]):
                raise ValueError("primary_nba_result_source_identity_disagrees")
            revised = dict(original)
            matches = []
            if day in originals:
                for g in games_by_day[day]:
                    if (g["home_team"] == nba_team_name(c["home_team"])
                            and g["away_team"] == nba_team_name(c["away_team"])
                            and abs((g["start_utc"] - timestamp(c["start_utc"])).total_seconds())
                                <= MAX_TIME_DIFFERENCE_SECONDS):
                        matches.append(g)
            previous = original.get("crosscheck_status")
            if len(matches) > 1:
                revised["crosscheck_status"] = "nba_daily_duplicate_game_identity_quarantined"
            elif len(matches) == 1:
                g = matches[0]
                if g["status"] != "official_final":
                    revised["crosscheck_status"] = "nba_daily_game_not_final_or_score_missing"
                else:
                    verified_score = {"home":g["home_score"],"away":g["away_score"]}
                    if verified_score != c["published_score_only"]:
                        revised["crosscheck_status"] = "nba_daily_official_final_disagrees_with_espn"
                        revised["official_nba_score"] = verified_score
                    elif previous in (
                            "nba_official_source_unavailable",
                            "official_nba_game_not_found_or_clock_mismatch"):
                        revised.update({
                            "official_nba_game_id":g["official_nba_game_id"],
                            "official_nba_start_utc":g["start_utc"].isoformat(),
                            "official_nba_score":verified_score,
                            "official_nba_source_url":originals[day]["url"],
                            "official_nba_original_json_sha256_self_attested":
                                originals[day]["sha256"],
                            "crosscheck_status":RESEARCH_STATUS,
                            "daily_score_fallback_used":True,
                        })
                    elif previous == RESEARCH_STATUS:
                        if original.get("official_nba_score") != verified_score:
                            revised["crosscheck_status"] = (
                                "nba_operated_sources_conflict_quarantined")
                    # Prior explicit official discrepancy remains a discrepancy,
                    # even if a different NBA-operated response later agrees.
            if revised.get("crosscheck_status") == RESEARCH_STATUS:
                counts["second_source_published_score_agreement"] += 1
            if revised.get("daily_score_fallback_used") is True:
                counts["daily_original_source_agreement"] += 1
            counts[revised["crosscheck_status"]] += 1
            # Never let an ordinary NBA source become a signed third-party review.
            for flag in ("training_row_qualified",
                         "independent_feature_asof_verified",
                         "independent_source_receipt_authenticated",
                         "independent_bookmaker_settlement_verified",
                         "certified_prediction","bet_ready",
                         "champion_001_modified"):
                if revised.get(flag) is not False:
                    raise ValueError("nba_crosscheck_attempted_qualification_promotion")
            rows.append(revised)
    report = {
        "stage":"challenger_97_nba_date_scoped_original_finals_research_only",
        "review_candidates":len(candidates),
        "nba_daily_source_days_attempted":len(days),
        "nba_daily_source_days_succeeded":len(originals),
        "source_failure_types_by_day":dict(sorted(errors.items())),
        "candidate_days_not_requested_due_bounded_budget":max(0,len(groups)-len(days)),
        "original_source_sha256_by_day":{
            d:x["sha256"] for d,x in sorted(originals.items())},
        "combined_second_source_score_agreements_research_only":
            counts["second_source_published_score_agreement"],
        "new_nba_original_daily_score_agreements_research_only":
            counts["daily_original_source_agreement"],
        "crosscheck_statuses":dict(sorted(
            (k,v) for k,v in counts.items()
            if k not in ("second_source_published_score_agreement",
                         "daily_original_source_agreement"))),
        "qualified_training_games":0,
        "qualified_holdout_games":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("NBA official game score corroboration is research only. "
                   "A self-hashed later source response does NOT prove past "
                   "pregame feature publication, original timestamp custody, "
                   "independent game settlement or approved native training."),
    }
    return rows, report, originals


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates",required=True)
    p.add_argument("--primary-comparisons",required=True)
    p.add_argument("--output-dir",default="prospective_validation")
    p.add_argument("--max-days",type=int,default=MAX_DAYS)
    args=p.parse_args(argv)
    def lines(filename):
        file=Path(filename)
        if not file.is_file():
            raise FileNotFoundError(file)
        return [json.loads(line) for line in file.read_text(encoding="utf8").splitlines()
                if line.strip()]
    rows,report,originals=review(lines(args.candidates),
        lines(args.primary_comparisons),datetime.now(timezone.utc),
        max_days=args.max_days)
    root=Path(args.output_dir)
    original_dir=root/"nba_date_scoped_original_final_scoreboards"
    original_dir.mkdir(parents=True,exist_ok=True)
    for day,item in originals.items():
        raw=original_dir/(day+".json")
        raw.write_bytes(item["raw"])
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("NBA_original_archive_write_integrity_mismatch")
    (root/"nba_original_daily_score_fallback_review.jsonl").write_text(
        "".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),
        encoding="utf8")
    (root/"nba_original_daily_score_fallback_report.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "original_daily_score_agreements":
            report["new_nba_original_daily_score_agreements_research_only"],
        "qualified_training_games":0,
        "certified_predictions":0,
        "champion_001_modified":False},sort_keys=True))


if __name__=="__main__":
    main()
