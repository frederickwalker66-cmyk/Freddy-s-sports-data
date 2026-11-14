"""NBA as-observed scoreboard updates for Freddy's Picks AI V8.

A public ESPN scoreboard observation can show scores and published game states.
It is NOT an authenticated sportsbook, final injury/active roster, bet or
model probability. This module performs NO paid-provider calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from v8_nba_slate_best_bets import read_today_schedule
from v8_sharp_archive import read_archive
from v8_quote_freshness import quote_freshness

NY = ZoneInfo("America/New_York")
MAX_SCOREBOARD_BYTES = 5_000_000
TIMEOUT_SECONDS = 12
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def _utc(now=None):
    at = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("timezone_aware_observation_required")
    return at.astimezone(timezone.utc)


def _stamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid_source_timestamp")
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _utc(at)


def _score(value):
    if type(value) is int:
        n = value
    elif isinstance(value, str) and re.fullmatch(r"\d{1,3}", value):
        n = int(value)
    else:
        return None
    return n if 0 <= n <= 300 else None


def _short(value):
    return re.sub(r"[\n\r|]", " ", str(value or "")).strip()[:90]


def parse_scoreboard(original_bytes, *, now=None):
    """Parse only source-published NBA current-day states from original bytes."""
    clock = _utc(now)
    if not isinstance(original_bytes, bytes) or not 0 < len(original_bytes) <= MAX_SCOREBOARD_BYTES:
        raise ValueError("invalid_bounded_scoreboard_response")
    payload = json.loads(original_bytes)
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("invalid_scoreboard_schema")
    date_et = clock.astimezone(NY).date()
    url = SOURCE + "?dates=" + date_et.strftime("%Y%m%d")
    scheduled = read_today_schedule(original_bytes, date_et, received_at=clock, url=url)
    lookup = {str(ev.get("id")): ev for ev in payload["events"] if isinstance(ev, dict)}
    games = []
    for game in scheduled:
        event = lookup.get(game["espn_event_id"], {})
        status = event.get("status") if isinstance(event.get("status"), dict) else {}
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") if isinstance(competition, dict) else None
        sides = {}
        if isinstance(competitors, list):
            for c in competitors:
                if isinstance(c, dict) and c.get("homeAway") in ("home", "away"):
                    sides[c["homeAway"]] = c
        state = game["source_event_state"]
        start = _stamp(game["start_utc"])
        before_tip = state == "pre" and start > clock
        scores = {
            side: _score(sides.get(side, {}).get("score")) if state in ("in", "post") else None
            for side in ("home", "away")
        }
        period = status.get("period")
        period = period if type(period) is int and 0 <= period <= 10 else None
        games.append({
            "espn_event_id": game["espn_event_id"],
            "matchup": game["away_team"] + " @ " + game["home_team"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "scheduled_start_et": game["start_et"],
            "source_event_state": state,
            "score_away": scores["away"],
            "score_home": scores["home"],
            "period": period if state in ("in", "post") else None,
            "clock": _short(status.get("displayClock")) if state == "in" else None,
            "source_status_detail": _short((status.get("type") or {}).get("shortDetail")
                                           if isinstance(status.get("type"), dict) else ""),
            "pregame_research_eligible_by_clock_only": before_tip,
            "bet_decision": "HOLD_NO_CERTIFIED_EDGE",
            "in_play_betting_covered": False,
            "verified_sportsbook_price": None,
            "verified_player_active_status": None,
        })
    return {
        "source_status": "ESPN_SCOREBOARD_OBSERVED",
        "scoreboard_original_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "date_et": date_et.isoformat(),
        "games": games,
        "published_game_count": len(games),
        "source_reported_in_progress": sum(g["source_event_state"] == "in" for g in games),
        "source_reported_final": sum(g["source_event_state"] == "post" for g in games),
    }


def _injury_reference(meta_path, clock):
    result = {
        "reference_status": "NO_COMPLETED_INJURY_WORKFLOW_METADATA",
        "workflow_run_id": None,
        "last_successful_workflow_update_utc": None,
        "reference_age_minutes": None,
        "actual_player_injury_designations_retrieved_here": False,
        "official_final_active_roster_confirmed": False,
    }
    if meta_path is None or not Path(meta_path).is_file():
        return result
    try:
        records = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            return result
        latest = records[0]
        run_id = latest.get("databaseId")
        at = _stamp(latest.get("updatedAt"))
        if type(run_id) is not int or run_id <= 0 or at > clock:
            return result
        result.update(
            reference_status="LATEST_SUCCESSFUL_INJURY_WORKFLOW_METADATA_ONLY",
            workflow_run_id=run_id,
            last_successful_workflow_update_utc=at.isoformat(),
            reference_age_minutes=round((clock-at).total_seconds()/60, 1),
        )
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        result["reference_status"] = "INJURY_WORKFLOW_METADATA_UNREADABLE"
    return result


def create_report(*, scoreboard_bytes=None, now=None, injury_metadata=None,
                  sharp_archive_dir=None, source_error=None):
    clock = _utc(now)
    result = {
        "report_type": "FREDDY_V8_NBA_AS_OBSERVED_LIVE_UPDATES_V1",
        "observed_at_utc": clock.isoformat(),
        "observed_at_et": clock.astimezone(NY).isoformat(),
        "source_url": SOURCE + "?dates=" + clock.astimezone(NY).strftime("%Y%m%d"),
        "source_status": "SOURCE_UNAVAILABLE_NOT_ZERO_GAMES",
        "source_error": str(source_error)[:180] if source_error else None,
        "date_et": clock.astimezone(NY).date().isoformat(),
        "published_game_count": None,
        "games": [],
        "injury_workflow_reference": _injury_reference(injury_metadata, clock),
        "market_quote_status": "NO_ARCHIVED_MARKET_EVIDENCE",
        "latest_archived_nba_quote_utc": None,
        "latest_archived_nba_quote_age_minutes": None,
        "today_unstarted_nba_price_rows_within_120m": 0,
        "archive_run_ids": [],
        "live_draftkings_checkout_verified": False,
        "live_player_props_verified": False,
        "official_final_active_lineups_verified": False,
        "native_calibrated_prop_probabilities_verified": False,
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
        "champion_001_modified": False,
        "decision": "HOLD_NO_CERTIFIED_EDGE",
        "not_a_continuous_stream": True,
    }
    if scoreboard_bytes is not None:
        try:
            result.update(parse_scoreboard(scoreboard_bytes, now=clock))
            result["source_error"] = None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            result["source_error"] = type(exc).__name__
            result["source_status"] = "UNREADABLE_ESPN_SOURCE_NOT_ZERO_GAMES"
    if sharp_archive_dir is not None:
        try:
            rows, run_ids, _ = read_archive(sharp_archive_dir)
            freshness = quote_freshness(rows, leagues=("nba",), now=clock, archive_run_ids=run_ids)
            nba = freshness["by_league"]["nba"]
            # This scoreboard-only check evaluates receipt age, not exact-line
            # pairing. The full Sharp Edge bundle owns game/prop pair matching.
            # Missing paired counts must not be reported as observed zero pairs.
            source_status = nba["source_readiness"]
            if source_status == "RECENT_RAW_QUOTES_BUT_NO_EXACT_PAIRED_MARKETS":
                source_status = "RECENT_RAW_QUOTES_PAIR_MATCHING_NOT_RUN_IN_SCOREBOARD_LAYER"
            result.update(
                market_quote_status=source_status,
                latest_archived_nba_quote_utc=nba["latest_valid_source_received_utc"],
                latest_archived_nba_quote_age_minutes=nba["latest_valid_archive_receipt_age_minutes"],
                today_unstarted_nba_price_rows_within_120m=nba[
                    "today_upcoming_quote_rows_within_120m"],
                archive_run_ids=run_ids,
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            result["market_quote_status"] = "ODDS_ARCHIVE_UNREADABLE_NO_PROMOTION"
    return result


def render(report):
    lines = [
        "# Freddy's Picks AI — NBA live source check",
        "**Observed:** " + report["observed_at_et"] + " (actual receipt; not a live stream)",
        "**Public scoreboard:** " + report["source_status"],
        "**Date (Eastern):** " + report["date_et"],
        "**Source:** " + report["source_url"],
        "",
        "| Matchup | NBA state | Reported score (away-home) | Period / clock | Pregame? | Bet |",
        "|---|---|---|---|---|---|",
    ]
    for game in report["games"]:
        scores = (f"{game['score_away']}-{game['score_home']}"
                  if game["score_away"] is not None and game["score_home"] is not None
                  else "N/A")
        period = (str(game["period"]) if game["period"] is not None else "N/A")
        if game["clock"]:
            period += " / " + game["clock"]
        lines.append(f"| {_short(game['matchup'])} | {game['source_event_state']} | "
                     f"{scores} | {period} | "
                     f"{'Yes, by clock only' if game['pregame_research_eligible_by_clock_only'] else 'No'} | HOLD |")
    if not report["games"]:
        lines.append("| N/A — source unavailable or no published regular/postseason games | "
                     "N/A | N/A | N/A | N/A | HOLD |")
    injury = report["injury_workflow_reference"]
    lines.extend([
        "",
        "**Injury archive:** " + injury["reference_status"],
        "**Most recent successful injury workflow:** " +
        str(injury["workflow_run_id"] or "N/A") +
        "; age " + str(injury["reference_age_minutes"] if injury["reference_age_minutes"] is not None else "N/A") + " min.",
        "**Odds receipt:** " + report["market_quote_status"],
        "**Latest archived NBA market receipt:** " +
        str(report["latest_archived_nba_quote_utc"] or "N/A") +
        "; age " + str(report["latest_archived_nba_quote_age_minutes"]
                       if report["latest_archived_nba_quote_age_minutes"] is not None else "N/A") + " min.",
        "**Upcoming NBA research price rows from last 120 min:** " +
        str(report["today_unstarted_nba_price_rows_within_120m"]),
        "**Bookmaker checkout / confirmed active roster / player prop EV:** UNVERIFIED.",
        "**Betting action:** HOLD. Certified +EV: 0. Stakes: $0. Champion-001 frozen.",
        "Scoreboard states and scores are public observations as of the timestamp, not bookmaker markets,",
        "proof of professional sharp action, certified player availability, or a wagering recommendation.",
    ])
    return "\n".join(lines) + "\n"


def run(*, output_dir, scoreboard_file=None, injury_metadata=None,
        sharp_archive_dir=None, now=None, fetcher=None):
    clock = _utc(now)
    error = None
    if scoreboard_file is not None:
        try:
            source = Path(scoreboard_file).read_bytes()
        except OSError:
            source = None
            error = "LOCAL_SCOREBOARD_FILE_UNAVAILABLE"
    else:
        url = SOURCE + "?dates=" + clock.astimezone(NY).strftime("%Y%m%d")
        try:
            if fetcher is None:
                request = Request(url, headers={
                    "Accept": "application/json",
                    "User-Agent": "FreddysPicksAI-research/1.0",
                })
                with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    source = response.read(MAX_SCOREBOARD_BYTES + 1)
            else:
                source = fetcher(url)
        except (OSError, ValueError, TimeoutError):
            source = None
            error = "PUBLIC_SCOREBOARD_NETWORK_OR_HTTP_UNAVAILABLE"
    report = create_report(scoreboard_bytes=source, now=clock, source_error=error,
                           injury_metadata=injury_metadata, sharp_archive_dir=sharp_archive_dir)
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "NBA_LIVE_UPDATES.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (path / "NBA_LIVE_UPDATES.md").write_text(render(report), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scoreboard-file")
    parser.add_argument("--injury-metadata")
    parser.add_argument("--sharp-archive-dir")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = run(output_dir=args.output_dir, scoreboard_file=args.scoreboard_file,
                 injury_metadata=args.injury_metadata, sharp_archive_dir=args.sharp_archive_dir)
    print(json.dumps({
        "source_status": result["source_status"],
        "games_reported": result["published_game_count"],
        "market_quote_status": result["market_quote_status"],
        "certified_bets": result["certified_positive_ev_bets"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
