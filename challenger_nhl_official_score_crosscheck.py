"""NHL-operated final-score corroboration for archived Challenger pregame events.

Research-only. NHL's published scoreboard is a distinct retrospective score
source, not proof that historical features were available pregame, official
sportsbook market settlement, independently authenticated provenance, or EV.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_multisport_original_bytes_lineage import REVIEW_RECORD
from challenger_prospective_outcome_validation import instant

SOURCE_HOST = "https://api-web.nhle.com/v1/score/"
EASTERN = ZoneInfo("America/New_York")
MAX_SOURCE_DAYS = 3
MAX_BYTES = 3_000_000
MAX_CLOCK_DIFFERENCE_SECONDS = 30 * 60

# Exact full-name mapping, never nickname-only or fuzzy joins. Historical teams
# are included solely for retrospective identity, not for current roster proof.
FULL_TO_ABBREV = {
    "anaheim ducks": "ANA", "arizona coyotes": "ARI",
    "boston bruins": "BOS", "buffalo sabres": "BUF",
    "calgary flames": "CGY", "carolina hurricanes": "CAR",
    "chicago blackhawks": "CHI", "colorado avalanche": "COL",
    "columbus blue jackets": "CBJ", "dallas stars": "DAL",
    "detroit red wings": "DET", "edmonton oilers": "EDM",
    "florida panthers": "FLA", "los angeles kings": "LAK",
    "minnesota wild": "MIN", "montreal canadiens": "MTL",
    "nashville predators": "NSH", "new jersey devils": "NJD",
    "new york islanders": "NYI", "new york rangers": "NYR",
    "ottawa senators": "OTT", "philadelphia flyers": "PHI",
    "phoenix coyotes": "PHX", "pittsburgh penguins": "PIT",
    "san jose sharks": "SJS", "seattle kraken": "SEA",
    "st. louis blues": "STL", "tampa bay lightning": "TBL",
    "toronto maple leafs": "TOR", "utah hockey club": "UTA",
    "utah mammoth": "UTA", "vancouver canucks": "VAN",
    "vegas golden knights": "VGK", "washington capitals": "WSH",
    "winnipeg jets": "WPG",
}


def normalized_name(value):
    return " ".join(value.lower().split()) if isinstance(value, str) else ""


def day_url(day):
    # The date is derived from a datetime.date.isoformat, not external input.
    return SOURCE_HOST + day


def fetch_scoreboard(day):
    req = Request(day_url(day), headers={
        "Accept": "application/json",
        "User-Agent": "FreddysPicksChallengerNhlResultResearch/1.0",
    })
    with urlopen(req, timeout=15) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("NHL scoreboard response exceeds maximum bytes")
    return body


def parse_scoreboard(raw, requested_day):
    """Parse only the requested date; malformed or duplicated games fail closed."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("invalid NHL original-source bytes")
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or payload.get("currentDate") != requested_day
            or not isinstance(payload.get("games"), list)
            or len(payload["games"]) > 50):
        raise ValueError("NHL scoreboard date, schema or size mismatch")
    games = []
    ids = set()
    for game in payload["games"]:
        if not isinstance(game, dict):
            raise ValueError("non-object NHL game")
        gid = str(game.get("id"))
        if not gid.isdigit() or gid in ids:
            raise ValueError("missing or duplicate NHL official event ID")
        ids.add(gid)
        h, a = game.get("homeTeam"), game.get("awayTeam")
        if not isinstance(h, dict) or not isinstance(a, dict):
            raise ValueError("NHL game missing full matchup")
        home, away = h.get("abbrev"), a.get("abbrev")
        if (not isinstance(home, str) or not isinstance(away, str)
                or len(home) not in (2, 3) or len(away) not in (2, 3)
                or home == away):
            raise ValueError("invalid NHL team abbreviation identities")
        start = instant(game.get("startTimeUTC"))
        if start.astimezone(EASTERN).date().isoformat() != requested_day:
            raise ValueError("NHL official start does not match queried Eastern day")
        if game.get("gameDate") not in (None, requested_day):
            raise ValueError("NHL game date contradicts requested source date")
        state = game.get("gameState")
        final = state in ("OFF", "FINAL")
        hs, as_ = h.get("score"), a.get("score")
        valid_score = (type(hs) is int and type(as_) is int
                       and 0 <= hs <= 30 and 0 <= as_ <= 30 and hs != as_)
        outcome = game.get("gameOutcome")
        period = outcome.get("lastPeriodType") if isinstance(outcome, dict) else None
        if period not in (None, "REG", "OT", "SO"):
            raise ValueError("NHL unexpected final period classification")
        games.append({
            "nhl_game_id": gid, "start": start, "home_abbrev": home,
            "away_abbrev": away, "game_state": state,
            "final_score_valid": bool(final and valid_score),
            "home_score": hs if valid_score else None,
            "away_score": as_ if valid_score else None,
            "last_period_type": period, "game_type": game.get("gameType"),
        })
    return games


def validate_review_packet(row, observed):
    if (not isinstance(row, dict) or row.get("record_type") != REVIEW_RECORD
            or row.get("league") != "nhl"
            or row.get("original_bytes_match_same_run_receipt") is not True
            or row.get("same_run_receipt_independently_authenticated") is not False
            or row.get("qualified_for_challenger_training") is not False
            or row.get("independent_outcome_review") is not False
            or row.get("market_settlement_rules_verified") is not False
            or row.get("model_probability") is not None
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("unquarantined or malformed NHL lineage review")
    event = row.get("event_id")
    if not isinstance(event, str) or not event.isdigit():
        raise ValueError("invalid ESPN NHL event ID")
    home = FULL_TO_ABBREV.get(normalized_name(row.get("home_team")))
    away = FULL_TO_ABBREV.get(normalized_name(row.get("away_team")))
    if home is None or away is None or home == away:
        raise ValueError("missing exact NHL team-name crosswalk")
    start = instant(row.get("event_start_utc"))
    captured = instant(row.get("snapshot_completed_at_utc"))
    if not captured < start < observed:
        raise ValueError("invalid NHL original capture or event time")
    published = row.get("published_final_only")
    if published is not None:
        if not isinstance(published, dict):
            raise ValueError("invalid ESPN final review object")
        hs, as_ = published.get("home_score"), published.get("away_score")
        result = "home" if (type(hs) is int and type(as_) is int and hs > as_) else "away"
        if (type(hs) is not int or type(as_) is not int
                or not 0 <= hs <= 30 or not 0 <= as_ <= 30
                or hs == as_ or published.get("published_result") != result
                or not start < instant(published.get("published_at_observation_utc")) <= observed):
            raise ValueError("invalid ESPN published NHL final and timestamp")
    return start, home, away, published


def corroborate(rows, source_bytes, observed, max_days=MAX_SOURCE_DAYS):
    """Offline comparison against separately fetched original NHL scoreboard bytes."""
    if (not isinstance(rows, list) or not isinstance(source_bytes, dict)
            or not isinstance(observed, datetime) or observed.tzinfo is None
            or type(max_days) is not int or not 1 <= max_days <= MAX_SOURCE_DAYS):
        raise ValueError("invalid NHL corroboration input")
    observed = observed.astimezone(timezone.utc)
    verified, seen = [], set()
    for row in rows:
        start, home, away, published = validate_review_packet(row, observed)
        key = row["event_id"]
        if key in seen:
            raise ValueError("duplicate ESPN NHL research event")
        seen.add(key)
        verified.append((row, start, home, away, published))
    eligible_days = {start.astimezone(EASTERN).date().isoformat()
                     for _, start, _, _, p in verified if p is not None}
    selected = sorted(eligible_days, reverse=True)[:max_days]
    parsed, source_errors, source_hashes = {}, {}, {}
    for day in selected:
        raw = source_bytes.get(day)
        if raw is None:
            source_errors[day] = "source_unavailable"
        else:
            try:
                parsed[day] = parse_scoreboard(raw, day)
                source_hashes[day] = hashlib.sha256(raw).hexdigest()
            except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, OverflowError) as exc:
                source_errors[day] = "invalid_source_" + type(exc).__name__
    output, statuses = [], Counter()
    for row, start, home, away, published in verified:
        day = start.astimezone(EASTERN).date().isoformat()
        rec = {
            "record_type": "challenger_nhl_second_source_research_review_only",
            "league": "nhl", "espn_event_id": row["event_id"],
            "nhl_official_event_id": None,
            "espn_pregame_capture_utc": row["snapshot_completed_at_utc"],
            "espn_published_score": ({"home": published["home_score"],
                                    "away": published["away_score"]} if published else None),
            "nhl_official_score": None,
            "nhl_last_period_type_research": None,
            "nhl_official_scoreboard_url": day_url(day) if day in selected else None,
            "nhl_original_source_sha256": source_hashes.get(day),
            "nhl_source_observed_at_utc": observed.isoformat() if day in parsed else None,
            "source_independently_published": day in parsed,
            "source_publication_time_at_original_pregame_verified": False,
            "independent_feature_asof_verified": False,
            "official_bookmaker_settlement_verified": False,
            "qualified_for_challenger_training": False,
            "certified_prediction": False, "bet_ready": False,
            "champion_001_modified": False,
        }
        if published is None:
            status = "awaiting_primary_published_final"
        elif day not in selected:
            status = "outside_bounded_recent_source_dates"
        elif day in source_errors:
            status = source_errors[day]
        else:
            possible = [g for g in parsed[day]
                        if g["home_abbrev"] == home and g["away_abbrev"] == away
                        and abs((g["start"] - start).total_seconds()) <= MAX_CLOCK_DIFFERENCE_SECONDS]
            if not possible:
                status = "official_nhl_event_not_matched"
            elif len(possible) > 1:
                status = "ambiguous_official_nhl_game_identity"
            else:
                match = possible[0]
                rec["nhl_official_event_id"] = match["nhl_game_id"]
                rec["nhl_last_period_type_research"] = match["last_period_type"]
                if not match["final_score_valid"]:
                    status = "official_nhl_game_not_final_or_score_invalid"
                else:
                    rec["nhl_official_score"] = {"home": match["home_score"],
                                                 "away": match["away_score"]}
                    status = ("nhl_second_source_final_score_agrees_research_only"
                              if (match["home_score"], match["away_score"]) ==
                              (published["home_score"], published["away_score"])
                              else "nhl_official_final_disagrees_with_espn")
        rec["crosscheck_status"] = status
        statuses[status] += 1
        output.append(rec)
    report = {
        "stage": "challenger_nhl_league_owned_second_source_results_research_only",
        "observed_at_utc": observed.isoformat(),
        "nhl_events_reviewed": len(output),
        "source_dates_requested_maximum": max_days,
        "source_dates_selected": selected,
        "source_dates_successfully_parsed": sorted(parsed),
        "source_date_errors": source_errors,
        "by_status": dict(sorted(statuses.items())),
        "published_final_score_agreements": statuses["nhl_second_source_final_score_agrees_research_only"],
        "independently_verified_training_games": 0,
        "independently_verified_prop_settlements": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("A league-operated retrospective score agrees or disagrees with "
                    "a distinct ESPN-published result; neither source proves original "
                    "pregame feature publication, independently authenticated "
                    "historical predictions, or bookmaker settlement."),
    }
    return output, report, parsed


def run(packets, fetcher=fetch_scoreboard, now=None, max_days=MAX_SOURCE_DAYS):
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    # Validate before network calls to avoid spending requests on unsafe inputs.
    for item in packets:
        validate_review_packet(item, clock.astimezone(timezone.utc))
    days = sorted({instant(p["event_start_utc"]).astimezone(EASTERN).date().isoformat()
                   for p in packets if p["published_final_only"] is not None},
                  reverse=True)[:max_days]
    responses, failures = {}, {}
    for day in days:
        try:
            responses[day] = fetcher(day)
        except (OSError, ValueError, TimeoutError, UnicodeError) as exc:
            failures[day] = type(exc).__name__
    rows, report, parsed = corroborate(packets, responses, clock, max_days)
    report["network_source_failures_by_day"] = failures
    return rows, report, {d: responses[d] for d in parsed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--output-dir", default="prospective_validation")
    parser.add_argument("--max-days", type=int, default=MAX_SOURCE_DAYS)
    args = parser.parse_args(argv)
    if not 1 <= args.max_days <= MAX_SOURCE_DAYS:
        parser.error("max-days must be 1 to 3")
    data = Path(args.lineage)
    if not data.is_file():
        raise FileNotFoundError("missing original-byte lineage file")
    all_rows = [json.loads(s) for s in data.read_text(encoding="utf-8").splitlines() if s.strip()]
    packets = [x for x in all_rows if isinstance(x, dict) and x.get("league") == "nhl"]
    rows, report, sources = run(packets, max_days=args.max_days)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"nhl_official_score_crosscheck.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True)+"\n" for x in rows), encoding="utf-8")
    (folder/"nhl_official_score_crosscheck_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    original = folder/"nhl_original_source_responses"
    if sources:
        original.mkdir(parents=True, exist_ok=True)
        for day, raw in sources.items():
            path = original/(day+".json")
            if path.exists():
                raise FileExistsError("refusing to overwrite original NHL source bytes")
            path.write_bytes(raw)
    print(json.dumps({"nhl_published_score_agreements": report["published_final_score_agreements"],
                      "official_source_days": report["source_dates_successfully_parsed"],
                      "independently_verified_training_games": 0,
                      "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
