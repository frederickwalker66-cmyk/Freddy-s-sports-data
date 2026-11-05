"""NCAAF and NCAAB NCAA.com-derived second-source score review (no training).

2026 NCAA scoreboards use GraphQL-backed data; this adapter consumes a
community-maintained NCAA.com-derived proxy's current JSON representation,
not the obsolete Casablanca 2026 endpoint. This is *not* NCAA-operated
adjudication, historical source publication proof or sportsbook settlement.
All outputs are strictly quarantined research.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_multisport_original_bytes_lineage import REVIEW_RECORD
from challenger_prospective_outcome_validation import instant

LEAGUES = ("ncaaf", "ncaab")
SOURCE_BASE = "https://ncaa-api.henrygd.me/scoreboard/"
SOURCE_CLASS = "third_party_ncaa_com_derived_scoreboard_proxy"
EASTERN = ZoneInfo("America/New_York")
MAX_DATES_PER_LEAGUE = 3
MAX_GAMES_PER_SOURCE = 400
MAX_EVENTS = 450
MAX_BYTES = 4_000_000
CLOCK_TOLERANCE_SECONDS = 30 * 60

# Deliberately narrow, explicitly reviewed display-name crosswalk. Unknown
# school/multiple-campus identities stay blocked rather than fuzzy matched.
ESPN_SCHOOLS = {
    "alabama crimson tide": "alabama",
    "auburn tigers": "auburn",
    "baylor bears": "baylor",
    "clemson tigers": "clemson",
    "duke blue devils": "duke",
    "florida gators": "florida",
    "florida state seminoles": "florida state",
    "georgia bulldogs": "georgia",
    "gonzaga bulldogs": "gonzaga",
    "houston cougars": "houston",
    "illinois fighting illini": "illinois",
    "iowa state cyclones": "iowa state",
    "kansas jayhawks": "kansas",
    "kentucky wildcats": "kentucky",
    "lsu tigers": "lsu",
    "michigan wolverines": "michigan",
    "michigan state spartans": "michigan state",
    "north carolina tar heels": "north carolina",
    "nc state wolfpack": "nc state",
    "north carolina state wolfpack": "nc state",
    "notre dame fighting irish": "notre dame",
    "ohio state buckeyes": "ohio state",
    "oregon ducks": "oregon",
    "penn state nittany lions": "penn state",
    "purdue boilermakers": "purdue",
    "south carolina gamecocks": "south carolina",
    "st john s red storm": "st johns",
    "tennessee volunteers": "tennessee",
    "texas longhorns": "texas",
    "texas a&m aggies": "texas a&m",
    "uconn huskies": "uconn",
    "usc trojans": "usc",
    "villanova wildcats": "villanova",
    "virginia cavaliers": "virginia",
    "wisconsin badgers": "wisconsin",
}
# Require an exact school identity, not a nickname substring. Source aliases
# are only explicitly bounded when the school is unambiguous.
SOURCE_ALIASES = {
    "alabama": "alabama", "auburn": "auburn", "baylor": "baylor",
    "clemson": "clemson", "duke": "duke", "florida": "florida",
    "florida st": "florida state", "florida state": "florida state",
    "georgia": "georgia", "gonzaga": "gonzaga", "houston": "houston",
    "illinois": "illinois", "iowa st": "iowa state", "iowa state": "iowa state",
    "kansas": "kansas", "kentucky": "kentucky", "lsu": "lsu",
    "michigan": "michigan", "michigan st": "michigan state",
    "michigan state": "michigan state", "north carolina": "north carolina",
    "n carolina": "north carolina", "nc state": "nc state",
    "notre dame": "notre dame", "ohio st": "ohio state",
    "ohio state": "ohio state", "oregon": "oregon",
    "penn state": "penn state", "penn st": "penn state",
    "purdue": "purdue", "south carolina": "south carolina",
    "st johns": "st johns", "st john s": "st johns", "tennessee": "tennessee",
    "texas": "texas", "texas a&m": "texas a&m",
    "connecticut": "uconn", "uconn": "uconn",
    "southern california": "usc", "usc": "usc",
    "villanova": "villanova", "virginia": "virginia",
    "wisconsin": "wisconsin",
}


def norm(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[^a-z0-9&]+", " ", value.lower())
    return " ".join(value.split())


def school_from_espn(value):
    school = ESPN_SCHOOLS.get(norm(value))
    if school is None:
        raise ValueError("unreviewed_espn_school_display_name")
    return school


def school_from_ncaa(value):
    if not isinstance(value, str):
        return None
    return SOURCE_ALIASES.get(norm(value))


def scoreboard_path(league, day=None, football_week=None, football_year=None):
    if league == "ncaab":
        if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("ncaa_basketball_requires_exact_calendar_date")
        parsed = datetime.strptime(day, "%Y-%m-%d").date()
        return f"basketball-men/d1/{parsed.year:04d}/{parsed.month:02d}/{parsed.day:02d}/all-conf"
    if league != "ncaaf":
        raise ValueError("unsupported_ncaa_league")
    if football_week is None and football_year is None:
        # Current NCAA week only: historical week MUST NOT be guessed from
        # an ISO calendar week or a game timestamp.
        return "football/fbs"
    if (type(football_week) is not int or not 1 <= football_week <= 25
            or type(football_year) is not int or not 2024 <= football_year <= 2100):
        raise ValueError("football_week_requires_explicit_valid_season_and_week")
    return f"football/fbs/{football_year:04d}/{football_week:02d}/all-conf"


def fetch_scoreboard(path):
    if not isinstance(path, str) or not (
            path.startswith("football/fbs") or path.startswith("basketball-men/d1/")):
        raise ValueError("unapproved_ncaa_scoreboard_path")
    # Every path part comes from scoreboard_path(), not from untrusted input.
    url = SOURCE_BASE + path
    req = Request(url, headers={"Accept": "application/json",
                                "User-Agent": "FreddysPicksResearchNCAA2026/1.0"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("ncaa_scoreboard_exceeds_size_limit")
    return raw


def parse_scoreboard(raw):
    """Validate proxy 2026 transformed games[] format; no old source fallback."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or not raw:
        raise ValueError("invalid_ncaa_scoreboard_source_bytes")
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or not isinstance(payload.get("games"), list)
            or len(payload["games"]) > MAX_GAMES_PER_SOURCE
            or isinstance(payload.get("errors"), list) and payload["errors"]):
        raise ValueError("unexpected_ncaa_proxy_scoreboard_schema")
    games, ids = [], set()
    for item in payload["games"]:
        if not isinstance(item, dict) or not isinstance(item.get("game"), dict):
            raise ValueError("unrecognized_ncaa_game_wrapper")
        g = item["game"]
        gid = str(g.get("gameID"))
        if not gid.isdecimal() or gid in ids:
            raise ValueError("invalid_or_duplicate_ncaa_contest_id")
        ids.add(gid)
        state = g.get("gameState")
        if state not in ("final", "pre", "live"):
            raise ValueError("unknown_ncaa_game_state")
        home, away = g.get("home"), g.get("away")
        if not isinstance(home, dict) or not isinstance(away, dict):
            raise ValueError("ncaa_game_missing_team")
        source_home = (home.get("names") or {}).get("short") if isinstance(home.get("names"), dict) else None
        source_away = (away.get("names") or {}).get("short") if isinstance(away.get("names"), dict) else None
        home_school, away_school = school_from_ncaa(source_home), school_from_ncaa(source_away)
        epoch = g.get("startTimeEpoch")
        if not isinstance(epoch, (int, str)) or not str(epoch).isdecimal():
            # No invented kickoff from ambiguous local time/date.
            start = None
        else:
            raw_timestamp = int(epoch)
            # NCAA proxy currently serializes a numeric Unix epoch. Accept only
            # seconds (10-digit) or milliseconds (13-digit) within 2024–2100.
            seconds = raw_timestamp / 1000 if len(str(epoch)) == 13 else raw_timestamp
            try:
                start = datetime.fromtimestamp(seconds, tz=timezone.utc)
                if not 2024 <= start.year <= 2100:
                    start = None
            except (ValueError, OverflowError, OSError):
                start = None
        day = g.get("startDate")
        if (not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
            source_day = None
        else:
            try:
                datetime.strptime(day, "%Y-%m-%d")
                source_day = day
            except ValueError:
                source_day = None
        score_home, score_away = home.get("score"), away.get("score")
        score_ok = (isinstance(score_home, str) and score_home.isdecimal()
                    and isinstance(score_away, str) and score_away.isdecimal()
                    and int(score_home) <= 250 and int(score_away) <= 250)
        # Don't assume a blank NCAA full-name field means missing teams:
        # proxy's 2026 converter normally supplies names.short and empty full.
        games.append({
            "ncaa_contest_id": gid, "state": state,
            "home_school": home_school, "away_school": away_school,
            "source_home_short": source_home, "source_away_short": source_away,
            "start": start, "source_date": source_day,
            "scores_valid": score_ok,
            "home_score": int(score_home) if score_ok else None,
            "away_score": int(score_away) if score_ok else None,
        })
    return games


def validate_packet(row, observed):
    if (not isinstance(row, dict) or row.get("record_type") != REVIEW_RECORD
            or row.get("league") not in LEAGUES
            or row.get("original_bytes_match_same_run_receipt") is not True
            or row.get("same_run_receipt_independently_authenticated") is not False
            or row.get("qualified_for_challenger_training") is not False
            or row.get("independent_outcome_review") is not False
            or row.get("market_settlement_rules_verified") is not False
            or row.get("model_probability") is not None
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("unquarantined_college_history_packet")
    eid = row.get("event_id")
    if not isinstance(eid, str) or not eid.isdecimal():
        raise ValueError("invalid_espn_college_event_id")
    start, captured = instant(row.get("event_start_utc")), instant(row.get("snapshot_completed_at_utc"))
    if not captured < start < observed:
        raise ValueError("college_pregame_capture_time_invalid")
    published = row.get("published_final_only")
    if published is not None:
        if not isinstance(published, dict):
            raise ValueError("invalid_espn_college_final")
        hs, as_ = published.get("home_score"), published.get("away_score")
        if (type(hs) is not int or type(as_) is not int or not 0 <= hs <= 250
                or not 0 <= as_ <= 250 or hs == as_):
            # Ties and unfinished results never become moneyline labels.
            raise ValueError("ambiguous_binary_college_final")
        if (published.get("published_result") != ("home" if hs > as_ else "away")
                or not start < instant(published.get("published_at_observation_utc")) <= observed):
            raise ValueError("college_final_label_or_retrieval_time_inconsistent")
    return start, published


def plan(packets, observed, max_dates=MAX_DATES_PER_LEAGUE, football_week=None, football_year=None):
    if (type(max_dates) is not int or not 1 <= max_dates <= MAX_DATES_PER_LEAGUE
            or not isinstance(observed, datetime) or observed.tzinfo is None
            or not isinstance(packets, list) or len(packets) > MAX_EVENTS):
        raise ValueError("invalid_college_source_plan")
    selected = defaultdict(set)
    for row in packets:
        start, published = validate_packet(row, observed.astimezone(timezone.utc))
        if published is None:
            continue
        if row["league"] == "ncaab":
            day = start.astimezone(EASTERN).date().isoformat()
            selected["ncaab"].add(day)
        else:
            selected["ncaaf"].add("current" if football_week is None else
                f"{football_year:04d}/{football_week:02d}")
    basketball_dates = sorted(selected["ncaab"], reverse=True)[:max_dates]
    reqs = {}
    if selected["ncaaf"]:
        reqs["ncaaf"] = scoreboard_path("ncaaf", football_week=football_week,
                                        football_year=football_year)
    for day in basketball_dates:
        reqs["ncaab:"+day] = scoreboard_path("ncaab", day=day)
    return reqs


def corroborate(packets, responses, observed, max_dates=MAX_DATES_PER_LEAGUE,
                football_week=None, football_year=None):
    reqs = plan(packets, observed, max_dates, football_week, football_year)
    parsed, errors, hashes = {}, {}, {}
    for key, route in reqs.items():
        if key not in responses:
            errors[key] = "source_unavailable"
            continue
        raw = responses[key]
        try:
            parsed[key] = parse_scoreboard(raw)
            hashes[key] = hashlib.sha256(raw).hexdigest()
        except (ValueError, TypeError, UnicodeError, OverflowError, json.JSONDecodeError) as exc:
            errors[key] = "invalid_source_" + type(exc).__name__
    seen, reviewed, counters = set(), [], Counter()
    for row in packets:
        start, published = validate_packet(row, observed.astimezone(timezone.utc))
        key = (row["league"], row["event_id"])
        if key in seen:
            raise ValueError("duplicate_espn_college_event_id")
        seen.add(key)
        day = start.astimezone(EASTERN).date().isoformat()
        source_key = "ncaaf" if row["league"] == "ncaaf" else "ncaab:"+day
        src_path = reqs.get(source_key)
        rec = {
            "record_type": "challenger_college_ncaa_proxy_score_crosscheck_research_only",
            "league": row["league"], "espn_event_id": row["event_id"],
            "ncaa_contest_id": None,
            "ncaa_proxy_source_class": SOURCE_CLASS,
            "ncaa_proxy_source_url": SOURCE_BASE+src_path if src_path else None,
            "ncaa_proxy_raw_sha256": hashes.get(source_key),
            "ncaa_proxy_observed_at_utc": observed.isoformat() if source_key in parsed else None,
            "ncaa_score": None,
            "espn_published_score": (
                {"home": published["home_score"], "away": published["away_score"]}
                if published else None),
            "source_original_pregame_publication_verified": False,
            "original_pregame_capture_independently_authenticated": False,
            "official_market_settlement_verified": False,
            "qualified_for_challenger_training": False,
            "certified_prediction": False,
            "bet_ready": False, "champion_001_modified": False,
        }
        if published is None:
            status = "awaiting_espn_published_final"
        elif source_key not in reqs:
            status = "outside_bounded_ncaa_basketball_dates"
        elif source_key in errors:
            status = errors[source_key]
        else:
            try:
                school_home = school_from_espn(row["home_team"])
                school_away = school_from_espn(row["away_team"])
            except ValueError:
                status = "unreviewed_college_school_identity"
            else:
                if school_home == school_away:
                    status = "duplicated_college_school_identity"
                else:
                    matches = [g for g in parsed[source_key]
                               if g["home_school"] == school_home
                               and g["away_school"] == school_away
                               and g["start"] is not None
                               and abs((g["start"] - start).total_seconds()) <= CLOCK_TOLERANCE_SECONDS
                               and (g["source_date"] is None
                                    or abs((g["start"].astimezone(EASTERN).date() -
                                            datetime.strptime(g["source_date"], "%Y-%m-%d").date()).days) <= 1)]
                    if not matches:
                        status = "no_exact_ncaa_match_in_checked_source"
                    elif len(matches) > 1:
                        status = "ambiguous_ncaa_contest_identity"
                    else:
                        game = matches[0]
                        rec["ncaa_contest_id"] = game["ncaa_contest_id"]
                        if game["state"] != "final" or not game["scores_valid"]:
                            status = "ncaa_event_not_final_or_incomplete_score"
                        elif game["home_score"] == game["away_score"]:
                            status = "ncaa_tie_not_two_way_moneyline"
                        else:
                            rec["ncaa_score"] = {
                                "home": game["home_score"], "away": game["away_score"]}
                            status = ("ncaa_derived_final_score_agrees_research_only"
                                      if (game["home_score"], game["away_score"]) ==
                                      (published["home_score"], published["away_score"])
                                      else "ncaa_derived_score_disagrees_with_espn")
        rec["crosscheck_status"] = status
        counters[(row["league"], status)] += 1
        reviewed.append(rec)
    by_league = {
        league: {state: n for (sport, state), n in sorted(counters.items()) if sport == league}
        for league in LEAGUES}
    report = {
        "stage": "challenger_college_ncaa_com_derived_score_review_only",
        "source_class": SOURCE_CLASS,
        "observed_at_utc": observed.astimezone(timezone.utc).isoformat(),
        "review_packet_count": len(reviewed),
        "by_league": by_league,
        "requested_routes": dict(sorted(reqs.items())),
        "source_errors": dict(sorted(errors.items())),
        "source_sha256": dict(sorted(hashes.items())),
        "ncaa_derived_score_agreements": {
            league: by_league[league].get("ncaa_derived_final_score_agrees_research_only", 0)
            for league in LEAGUES},
        "independently_qualified_training_games": 0,
        "verified_player_prop_settlements": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("henrygd's NCAA.com-derived JSON scoreboard is a separately published "
                    "proxy, not NCAA-operated adjudication or a verified historical "
                    "pregame feature archive. Unknown school aliases, missing source "
                    "dates and NCAA football weeks must not be inferred. No training."),
    }
    return reviewed, report


def run(packets, fetcher=fetch_scoreboard, now=None, max_dates=MAX_DATES_PER_LEAGUE,
        football_week=None, football_year=None):
    now = now or datetime.now(timezone.utc)
    reqs = plan(packets, now, max_dates, football_week, football_year)
    if len(reqs) > max_dates + 1:
        raise ValueError("college_source_request_budget_exceeded")
    data, failures = {}, {}
    for key, path in reqs.items():
        try:
            data[key] = fetcher(path)
        except (OSError, ValueError, TimeoutError, UnicodeError) as exc:
            failures[key] = type(exc).__name__
    records, report = corroborate(
        packets, data, now, max_dates=max_dates,
        football_week=football_week, football_year=football_year)
    report["network_failures"] = failures
    return records, report, {k: v for k, v in data.items() if k in report["source_sha256"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lineage", required=True)
    p.add_argument("--output-dir", default="prospective_validation")
    p.add_argument("--max-days", type=int, default=MAX_DATES_PER_LEAGUE)
    p.add_argument("--football-week", type=int)
    p.add_argument("--football-year", type=int)
    args = p.parse_args(argv)
    if (args.football_week is None) != (args.football_year is None):
        p.error("football-week and football-year must be supplied together")
    if not 1 <= args.max_days <= MAX_DATES_PER_LEAGUE:
        p.error("max-days must be 1..3")
    src = Path(args.lineage)
    if not src.is_file():
        raise FileNotFoundError("missing_original_byte_college_lineage")
    all_packets = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    college = [p for p in all_packets
               if isinstance(p, dict) and p.get("league") in LEAGUES]
    rows, report, sources = run(college, max_dates=args.max_days,
                                 football_week=args.football_week,
                                 football_year=args.football_year)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out/"college_ncaa_score_review.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True)+"\n" for r in rows), encoding="utf8")
    (out/"college_ncaa_score_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf8")
    if sources:
        original = out/"college_ncaa_proxy_original_bytes"
        original.mkdir(parents=True, exist_ok=True)
        for key, raw in sorted(sources.items()):
            # Fixed generated filenames, never path components from provider.
            label = re.sub(r"[^a-zA-Z0-9_-]+", "_", key)
            dest = original/(label+".json")
            if dest.exists():
                raise FileExistsError("refusing_to_replace_existing_ncaa_original_bytes")
            dest.write_bytes(raw)
    print(json.dumps({"reviewed": report["review_packet_count"],
                      "ncaa_derived_score_agreements": report["ncaa_derived_score_agreements"],
                      "qualified_training_games": 0, "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
