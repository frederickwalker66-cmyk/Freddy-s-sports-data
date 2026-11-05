"""NFL second-source final-score cross-check using separately published nflverse games.

Research-only. nflverse is a community-maintained dataset, NOT an NFL-operated
official settlement source or evidence of pregame feature publication time.
Never train, certify EV, or change Champion-001 based on this cross-check.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_multisport_original_bytes_lineage import REVIEW_RECORD
from challenger_prospective_outcome_validation import instant

SOURCE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
MAX_BYTES = 15_000_000
MAX_EVENTS = 120
MAX_START_DIFFERENCE_SECONDS = 30 * 60
EASTERN = ZoneInfo("America/New_York")
REQUIRED_FIELDS = frozenset((
    "game_id", "season", "game_type", "gameday", "gametime",
    "home_team", "away_team", "home_score", "away_score", "espn",
))

# Full names only; no nickname or partial-string matching.
TEAMS = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL",
    "baltimore ravens": "BAL", "buffalo bills": "BUF",
    "carolina panthers": "CAR", "chicago bears": "CHI",
    "cincinnati bengals": "CIN", "cleveland browns": "CLE",
    "dallas cowboys": "DAL", "denver broncos": "DEN",
    "detroit lions": "DET", "green bay packers": "GB",
    "houston texans": "HOU", "indianapolis colts": "IND",
    "jacksonville jaguars": "JAX", "kansas city chiefs": "KC",
    "las vegas raiders": "LV", "los angeles chargers": "LAC",
    "los angeles rams": "LA", "miami dolphins": "MIA",
    "minnesota vikings": "MIN", "new england patriots": "NE",
    "new orleans saints": "NO", "new york giants": "NYG",
    "new york jets": "NYJ", "philadelphia eagles": "PHI",
    "pittsburgh steelers": "PIT", "san francisco 49ers": "SF",
    "seattle seahawks": "SEA", "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN", "washington commanders": "WAS",
    # Retrospective team name variants; never used for roster determination.
    "oakland raiders": "LV", "san diego chargers": "LAC",
    "st. louis rams": "LA", "washington football team": "WAS",
    "washington redskins": "WAS",
}
GAME_TYPES = frozenset(("REG", "WC", "DIV", "CON", "SB"))
CODES = frozenset(TEAMS.values())


def _team(value):
    key = " ".join(value.lower().split()) if isinstance(value, str) else ""
    if key not in TEAMS:
        raise ValueError("unknown_full_nfl_team_name")
    return TEAMS[key]


def _score(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}", value):
        raise ValueError("missing_or_invalid_completed_score")
    val = int(value)
    if val > 150:
        raise ValueError("implausible_completed_score")
    return val


def fetch_games_csv():
    req = Request(SOURCE_URL, headers={
        "Accept": "text/csv",
        "User-Agent": "FreddysPicksIndependentNFLResearch/1.0",
    })
    with urlopen(req, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("nflverse CSV exceeds bounded source size")
    return data


def parse_nflverse(raw):
    """Read a complete release with exact schema and exclude unplayed fixtures."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("invalid_raw_nflverse_bytes")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_csv_encoding") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
            or not REQUIRED_FIELDS.issubset(reader.fieldnames)):
        raise ValueError("missing_or_duplicate_nflverse_csv_fields")
    result = []
    game_ids = set()
    for row in reader:
        if not isinstance(row, dict) or None in row:
            raise ValueError("malformed_csv_row")
        gid = row.get("game_id", "")
        if not isinstance(gid, str) or not re.fullmatch(r"\d{4}_[0-9A-Za-z_]+", gid) or gid in game_ids:
            raise ValueError("missing_or_duplicate_nflverse_game_id")
        game_ids.add(gid)
        # This forward-research adapter targets recent seasons; legacy seasons
        # with incomplete historical clocks cannot invalidate the whole feed.
        season_label = row.get("season", "")
        if not isinstance(season_label, str) or not re.fullmatch(r"\d{4}", season_label):
            raise ValueError("invalid_nflverse_season")
        if int(season_label) < 2024:
            continue
        home_raw, away_raw = row.get("home_score"), row.get("away_score")
        # Future fixtures are not scored. One-sided scores are invalid.
        if home_raw in ("", None, "NA") and away_raw in ("", None, "NA"):
            continue
        if row.get("game_type") not in GAME_TYPES:
            raise ValueError("unsupported_nfl_game_market_type")
        season = row.get("season", "")
        if not isinstance(season, str) or not re.fullmatch(r"\d{4}", season):
            raise ValueError("invalid_nflverse_season")
        season_year = int(season)
        if not 1999 <= season_year <= 2100:
            raise ValueError("season_outside_supported_scope")
        home, away = row.get("home_team"), row.get("away_team")
        if home not in CODES or away not in CODES or home == away:
            raise ValueError("invalid_nflverse_teams")
        try:
            day = date.fromisoformat(row["gameday"])
            clock = datetime.strptime(row["gametime"], "%H:%M").time()
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_nflverse_kickoff_time") from exc
        if day.year not in (season_year, season_year + 1):
            raise ValueError("nfl_season_and_date_disagree")
        kickoff = datetime.combine(day, clock, tzinfo=EASTERN).astimezone(timezone.utc)
        e = str(row.get("espn") or "").strip()
        if e in ("NA", "nan", "None"):
            e = ""
        if e and not re.fullmatch(r"\d{6,12}(?:\.0)?", e):
            raise ValueError("invalid_nflverse_espn_crosswalk")
        if e.endswith(".0"):
            e = e[:-2]
        result.append({
            "nflverse_game_id": gid, "nflverse_espn_event_id": e or None,
            "home": home, "away": away,
            "kickoff_utc": kickoff, "home_score": _score(home_raw),
            "away_score": _score(away_raw), "game_type": row["game_type"],
            "season": season_year,
        })
    return result


def validate_packet(row, observed):
    if (not isinstance(row, dict)
            or row.get("record_type") != REVIEW_RECORD or row.get("league") != "nfl"
            or row.get("original_bytes_match_same_run_receipt") is not True
            or row.get("same_run_receipt_independently_authenticated") is not False
            or row.get("qualified_for_challenger_training") is not False
            or row.get("independent_outcome_review") is not False
            or row.get("market_settlement_rules_verified") is not False
            or row.get("model_probability") is not None
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("unquarantined_or_malformed_nfl_lineage_review")
    event_id = row.get("event_id")
    if not isinstance(event_id, str) or not event_id.isdecimal():
        raise ValueError("invalid_espn_event_id")
    home, away = _team(row.get("home_team")), _team(row.get("away_team"))
    if home == away:
        raise ValueError("duplicated_nfl_team")
    start = instant(row.get("event_start_utc"))
    capture = instant(row.get("snapshot_completed_at_utc"))
    if not capture < start < observed:
        raise ValueError("invalid_pregame_capture_or_event_clock")
    published = row.get("published_final_only")
    if published is not None:
        if not isinstance(published, dict):
            raise ValueError("invalid_published_final_object")
        hs, away_score = published.get("home_score"), published.get("away_score")
        if (type(hs) is not int or type(away_score) is not int
                or not 0 <= hs <= 150 or not 0 <= away_score <= 150):
            raise ValueError("invalid_espn_published_score")
        winner = "home" if hs > away_score else "away" if hs < away_score else "draw"
        if (winner != published.get("published_result")
                or not start < instant(published.get("published_at_observation_utc")) <= observed):
            raise ValueError("incorrect_or_early_published_outcome")
    return start, home, away, published


def review(packets, csv_bytes, observed):
    if (not isinstance(packets, list)
            or not isinstance(observed, datetime) or observed.tzinfo is None):
        raise ValueError("invalid_nfl_score_review_inputs")
    observed = observed.astimezone(timezone.utc)
    checked = []
    seen = set()
    for row in packets:
        event = validate_packet(row, observed)
        if row["event_id"] in seen:
            raise ValueError("duplicate_espn_event_in_nfl_review")
        seen.add(row["event_id"])
        checked.append((row, *event))
    error, scores = None, None
    source_hash = hashlib.sha256(csv_bytes).hexdigest() if csv_bytes is not None else None
    if csv_bytes is not None:
        try:
            scores = parse_nflverse(csv_bytes)
        except (ValueError, TypeError, OverflowError, csv.Error) as exc:
            error = "invalid_nflverse_source_" + type(exc).__name__
    counts, out = Counter(), []
    for row, start, home, away, published in checked:
        receipt = {
            "record_type": "challenger_nfl_second_source_research_only",
            "league": "nfl", "espn_event_id": row["event_id"],
            "espn_published_score": ({"home": published["home_score"],
                                     "away": published["away_score"]} if published else None),
            "nflverse_game_id": None, "nflverse_score": None,
            "nflverse_source_url": SOURCE_URL,
            "nflverse_source_sha256": source_hash if scores is not None else None,
            "nflverse_observed_at_utc": observed.isoformat() if scores is not None else None,
            "nflverse_source_class": "third_party_community_published_schedule",
            "source_data_asof_original_pregame_verified": False,
            "independently_authenticated_original_capture": False,
            "bookmaker_market_settlement_verified": False,
            "qualified_for_challenger_training": False,
            "certified_prediction": False, "bet_ready": False,
            "champion_001_modified": False,
        }
        if published is None:
            status = "awaiting_espn_published_final"
        elif scores is None:
            status = error or "nflverse_source_unavailable"
        else:
            candidates = [g for g in scores
                          if (g["home"], g["away"]) == (home, away)
                          and abs((g["kickoff_utc"] - start).total_seconds()) <= MAX_START_DIFFERENCE_SECONDS
                          and (g["nflverse_espn_event_id"] is None
                               or g["nflverse_espn_event_id"] == row["event_id"])]
            if not candidates:
                status = "nflverse_unmatched_identity_or_clock"
            elif len(candidates) > 1:
                status = "nflverse_ambiguous_game_identity"
            else:
                g = candidates[0]
                receipt["nflverse_game_id"] = g["nflverse_game_id"]
                receipt["nflverse_score"] = {"home": g["home_score"], "away": g["away_score"]}
                if g["home_score"] == g["away_score"] or published["home_score"] == published["away_score"]:
                    status = "tie_requires_book_specific_settlement_review"
                elif (g["home_score"], g["away_score"]) == (
                        published["home_score"], published["away_score"]):
                    status = "nflverse_second_source_final_score_agrees_research_only"
                else:
                    status = "nflverse_published_score_disagrees_with_espn"
        receipt["crosscheck_status"] = status
        counts[status] += 1
        out.append(receipt)
    report = {
        "stage": "challenger_nfl_secondary_published_results_research_only",
        "observed_at_utc": observed.isoformat(),
        "candidate_nfl_games": len(out),
        "nflverse_historical_scored_rows": len(scores) if scores is not None else 0,
        "nflverse_source_valid": scores is not None,
        "nflverse_source_error": error,
        "by_status": dict(sorted(counts.items())),
        "second_source_final_score_agreements": counts["nflverse_second_source_final_score_agrees_research_only"],
        "independently_qualified_training_games": 0,
        "independently_verified_prop_settlements": 0,
        "certified_champion_001_predictions": 0, "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("nflverse is a separate third-party published result source, NOT "
                    "NFL-operated official results, historical as-of pregame evidence, "
                    "an authenticated independent settlement, or an eligible training label."),
    }
    return out, report


def run(packets, fetcher=fetch_games_csv, observed=None):
    observed = observed or datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ValueError("review_clock_must_have_timezone")
    if len(packets) > MAX_EVENTS:
        raise ValueError("nfl_review_is_bounded_to_120_events")
    for p in packets:
        validate_packet(p, observed.astimezone(timezone.utc))
    needs_source = any(p["published_final_only"] is not None for p in packets)
    raw, network_failure = None, None
    if needs_source:
        try:
            raw = fetcher()
        except (OSError, ValueError, TimeoutError, UnicodeError) as exc:
            network_failure = type(exc).__name__
    rows, report = review(packets, raw, observed)
    report["network_source_failure"] = network_failure
    report["original_nflverse_csv_preserved"] = bool(raw is not None and report["nflverse_source_valid"])
    return rows, report, raw if report["nflverse_source_valid"] else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lineage", required=True)
    p.add_argument("--output-dir", default="prospective_validation")
    a = p.parse_args(argv)
    path = Path(a.lineage)
    if not path.is_file():
        raise FileNotFoundError("missing_lineage_file")
    all_rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    packets = [r for r in all_rows if isinstance(r, dict) and r.get("league") == "nfl"]
    rows, report, raw = run(packets)
    dest = Path(a.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "nfl_second_source_score_review.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True)+"\n" for r in rows), encoding="utf8")
    (dest / "nfl_second_source_score_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf8")
    if raw is not None:
        file = dest / "nflverse_original_games.csv"
        if file.exists():
            raise FileExistsError("refusing_to_overwrite_nflverse_original_source")
        file.write_bytes(raw)
    print(json.dumps({"nfl_games_checked": report["candidate_nfl_games"],
                      "nflverse_score_agreements": report["second_source_final_score_agreements"],
                      "qualified_training_games": 0,
                      "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
