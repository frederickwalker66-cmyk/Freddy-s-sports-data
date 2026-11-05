"""Upgrade #83: genuinely observed third-party nflverse future NFL schedule receipts.

NFLverse/nfldata is independent of ESPN, but NOT NFL-operated nor an
authenticated pregame feature publication log. This module never upgrades the
strict league-owned identity count, native models, sportsbook odds, or bets.
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

from challenger_nfl_secondary_score import TEAMS, CODES
from challenger_prospective_outcome_validation import instant

SOURCE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
MAX_BYTES = 15_000_000
ET = ZoneInfo("America/New_York")
MAX_SKEW_SECONDS = 60
REQUIRED = frozenset(("game_id", "season", "game_type", "gameday",
                      "gametime", "away_team", "home_team", "espn",
                      "away_score", "home_score"))
GAME_TYPES = frozenset(("REG", "WC", "DIV", "CON", "SB"))


def fetch_original():
    req = Request(SOURCE_URL, headers={
        "Accept": "text/csv",
        "User-Agent": "FreddysPicksPregameSourceAudit/1.0",
    })
    with urlopen(req, timeout=20) as response:
        original = response.read(MAX_BYTES + 1)
    if len(original) > MAX_BYTES:
        raise ValueError("nflverse_original_response_oversized")
    return original


def parse_future(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("nflverse_original_csv_missing_or_oversized")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        fields = reader.fieldnames
        if (not fields or len(set(fields)) != len(fields)
                or not REQUIRED.issubset(fields)):
            raise ValueError("nflverse_schedule_csv_schema_missing_or_duplicate")
        rows = []
        seen = set()
        for r in reader:
            if not isinstance(r, dict) or None in r:
                raise ValueError("invalid_nflverse_csv_row")
            season = r.get("season") or ""
            if not re.fullmatch(r"\d{4}", season):
                raise ValueError("invalid_nflverse_season")
            # Older historical schemas are irrelevant for upcoming 2026 games.
            if int(season) < 2024:
                continue
            gid = r.get("game_id") or ""
            if (not re.fullmatch(r"\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}", gid)
                    or gid in seen):
                raise ValueError("duplicate_or_invalid_nflverse_game_id")
            seen.add(gid)
            if r.get("game_type") not in GAME_TYPES:
                continue
            home, away = r.get("home_team"), r.get("away_team")
            if (home not in CODES or away not in CODES or home == away):
                raise ValueError("invalid_nflverse_future_full_team_identity")
            # nflverse contains completed matches too. Require both scores
            # absent; a one-sided partial score is an invalid record.
            hs, aw = (r.get("home_score") or "").strip(), (r.get("away_score") or "").strip()
            if (hs in ("", "NA") and aw in ("", "NA")):
                pass
            elif hs not in ("", "NA") and aw not in ("", "NA"):
                continue
            else:
                raise ValueError("partially_scored_nflverse_upcoming_game")
            try:
                d = date.fromisoformat(r["gameday"])
                t = datetime.strptime(r["gametime"], "%H:%M").time()
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_nflverse_eastern_kickoff") from exc
            if d.year not in (int(season), int(season)+1):
                raise ValueError("nflverse_game_outside_season")
            start = datetime.combine(d, t, tzinfo=ET).astimezone(timezone.utc)
            e = str(r.get("espn") or "").strip()
            if e in ("NA", "nan", "None"):
                e = ""
            if e.endswith(".0"):
                e = e[:-2]
            if e and not re.fullmatch(r"\d{6,12}", e):
                raise ValueError("untrusted_nflverse_espn_crosswalk")
            rows.append({
                "nflverse_game_id": gid, "espn_id": e or None,
                "home": home, "away": away, "start": start,
            })
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("invalid_nflverse_original_csv_encoding") from exc


def audit(records, receipt=None):
    if not isinstance(records, list):
        raise ValueError("nflverse_review_requires_espn_game_list")
    parsed, parse_error, observed, checksum = None, None, None, None
    if receipt is not None:
        try:
            if (not isinstance(receipt, dict)
                    or receipt.get("source_url") != SOURCE_URL):
                raise ValueError("untrusted_nflverse_source_url")
            observed = instant(receipt["observed_at_utc"])
            raw = receipt["raw"]
            parsed = parse_future(raw)
            checksum = hashlib.sha256(raw).hexdigest()
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            parse_error = type(exc).__name__ + ":" + str(exc)[:96]
    result, counts, used, seen_espn = [], Counter(), set(), set()
    for r in records:
        if (not isinstance(r, dict) or r.get("league") != "nfl"
                or r.get("record_type") != "prospective_evidence_snapshot_research_only"
                or r.get("model_probability") is not None
                or r.get("certified_prediction") is not False
                or r.get("qualified_for_challenger_backtest") is not False
                or r.get("bet_ready") is not False
                or r.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nfl_original_pregame_archive")
        event_id = r.get("espn_schedule_event_id")
        if (not isinstance(event_id, str) or not event_id.isdecimal()
                or event_id in seen_espn):
            raise ValueError("duplicate_or_missing_nfl_espn_event")
        seen_espn.add(event_id)
        home, away = (TEAMS.get(" ".join(str(r.get(k) or "").casefold().split()))
                      for k in ("home_team", "away_team"))
        if not home or not away or home == away:
            raise ValueError("nfl_full_espn_team_identity_unrecognized")
        start = instant(r["event_start_utc"])
        snapshot = instant(r["snapshot_completed_at_utc"])
        first = instant(r["schedule_observed_at_utc"])
        if not first <= snapshot < start:
            raise ValueError("nfl_source_was_not_pregame")
        row = {
            "league": "nfl", "espn_event_id": event_id,
            "source_class": "independent_third_party_community_schedule_not_nfl_operated",
            "nflverse_game_id": None,
            "nflverse_source_url": SOURCE_URL,
            "nflverse_original_sha256": checksum,
            "nflverse_observed_at_utc": observed.isoformat() if parsed is not None else None,
            "independent_third_party_pregame_match_research_only": False,
            "independent_official_league_verified": False,
            "source_publication_timestamp_authenticated": False,
            "independent_training_feature_verified": False,
            "bookmaker_market_verified": False,
            "native_model_probability_verified": False,
            "certified_prediction": False, "bet_ready": False,
            "champion_001_modified": False,
        }
        if receipt is None:
            status = "nflverse_original_response_not_captured"
        elif parsed is None:
            status = "nflverse_invalid_original_response"
        elif not snapshot <= observed < start:
            status = "nflverse_response_not_observed_pregame"
        else:
            # nflverse matchup and advertised ESPN ID must both agree.
            possible = [g for g in parsed if (g["home"], g["away"]) == (home, away)
                        and (g["espn_id"] is None or g["espn_id"] == event_id)]
            aligned = [g for g in possible if abs((g["start"]-start).total_seconds())
                       <= MAX_SKEW_SECONDS]
            if len(aligned) != 1:
                status = ("nflverse_kickoff_disagrees" if possible and not aligned
                          else "nflverse_missing_ambiguous_or_conflicting_espn_id")
            else:
                gid = aligned[0]["nflverse_game_id"]
                if gid in used:
                    raise ValueError("nflverse_game_id_reused_by_two_espn_games")
                used.add(gid)
                row["nflverse_game_id"] = gid
                row["independent_third_party_pregame_match_research_only"] = True
                status = "nflverse_exact_pregame_third_party_identity_research_only"
        row["identity_status"] = status
        counts[status] += 1
        result.append(row)
    return result, {
        "stage": "challenger_83_nflverse_third_party_pregame_identity_research_only",
        "nfl_games_reviewed": len(result),
        "independent_third_party_pregame_identity_matches_research_only":
            counts["nflverse_exact_pregame_third_party_identity_research_only"],
        "official_nfl_operated_identity_matches_verified": 0,
        "nflverse_original_response_sha256": checksum,
        "source_status": "valid" if parsed is not None else (
            "not_captured" if receipt is None else "invalid"),
        "original_source_error": parse_error,
        "by_status": dict(sorted(counts.items())),
        "qualified_training_games": 0,
        "verified_bookmaker_quotes": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("nflverse is independently published third-party community "
                    "data, not an NFL-operated schedule, author-signed original "
                    "time receipt, historical as-of pregame features, or bookmaker odds."),
    }


def run(capture_dir, output_dir, fetcher=fetch_original, clock=None):
    root = Path(capture_dir)
    records = [json.loads(line) for line in
               (root / "prospective_event_evidence.jsonl").read_text().splitlines()
               if line.strip()]
    nfl = [r for r in records if r.get("league") == "nfl"]
    clock = (lambda: datetime.now(timezone.utc)) if clock is None else clock
    out = Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("nfl_third_party_output_directory_must_be_empty")
    out.mkdir(parents=True, exist_ok=True)
    packet, network_error = None, None
    if nfl:
        started = instant(clock().isoformat())
        try:
            raw = fetcher()
            observed = instant(clock().isoformat())
            if (observed < started or not isinstance(raw, bytes)
                    or not 1 <= len(raw) <= MAX_BYTES):
                raise ValueError("nflverse_original_wire_capture_invalid")
            # Preserve true bytes even if later parsing fails.
            with (out / "nflverse_games_original.csv").open("xb") as f:
                f.write(raw)
            packet = {"raw": raw, "source_url": SOURCE_URL,
                      "observed_at_utc": observed.isoformat()}
        except (OSError, ValueError, TimeoutError, UnicodeError, OverflowError) as exc:
            network_error = type(exc).__name__
    rows, report = audit(nfl, packet)
    report["network_source_failure"] = network_error
    (out / "nfl_third_party_game_identity.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True)+"\n" for row in rows),
        encoding="utf8")
    (out / "nfl_third_party_identity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    report = run(args.capture_dir, args.output_dir)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
