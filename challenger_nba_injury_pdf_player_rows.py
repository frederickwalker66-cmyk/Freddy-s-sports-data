"""NBA official injury PDF table extraction and pregame linkage: REVIEW ONLY.

Only original PDF bytes captured by the preceding as-observed NBA injury stage
are accepted. Publisher printed player/status rows can be parsed, but no player
is declared active, sportsbook-settled, roster-ID verified or trainable.

Column-aware PDF word positions are required; plain text/OCR reconstruction is
not accepted because it can silently assign statuses to the wrong player.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from challenger_nba_pregame_injury_pdf import (
    INDEX_URL, MAX_PDF_BYTES, report_label_from_url)
from challenger_nba_schedule_clock import nba_team_name
from challenger_prospective_outcome_validation import instant

ET = ZoneInfo("America/New_York")
MAX_PAGES = 30
MAX_WORDS_PER_PAGE = 14000
MAX_LINES_PER_PAGE = 1100
MAX_EVENTS = 100
EXPECTED_COLUMNS = ("date", "time", "matchup", "team", "player", "status", "reason")
BORDERS = (0, 0.123, 0.221, 0.310, 0.500, 0.690, 0.792, 1.01)
STATUSES = frozenset({"Out", "Doubtful", "Questionable", "Probable", "Available"})
TEAM_CODES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets",
    "IND": "Indiana Pacers", "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}
TEAMS = {nba_team_name(v): k for k, v in TEAM_CODES.items()}
MATCH = re.compile(r"^([A-Z]{2,3})@([A-Z]{2,3})$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
PAGE_DATE = re.compile(r"Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+(AM|PM)", re.I)
PERSON = re.compile(r"^[\wÀ-ÿ.'\-\s]+,\s*[\wÀ-ÿ.'\-\s]+$", re.UNICODE)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _cells(line):
    if not isinstance(line, dict):
        raise ValueError("not_pdf_coordinate_row")
    return {name: str(line.get(name) or "").strip() for name in EXPECTED_COLUMNS}


def word_lines(words, width):
    """Group real PDF words into visual rows, with conservative column bounds."""
    if (not isinstance(words, list) or len(words) > MAX_WORDS_PER_PAGE
            or type(width) not in (float, int) or width < 400):
        raise ValueError("invalid_pdf_word_geometry")
    ordered = []
    for w in words:
        if not isinstance(w, dict):
            raise ValueError("malformed_pdf_word")
        x, top, text = w.get("x0"), w.get("top"), w.get("text")
        if (type(x) not in (int, float) or type(top) not in (int, float)
                or not 0 <= x <= width or not 0 <= top <= 1500
                or not isinstance(text, str) or not text.strip()):
            raise ValueError("invalid_pdf_word_coordinates")
        ordered.append((float(top), float(x), text.strip()))
    ordered.sort()
    groups = []
    for top, x, text in ordered:
        if not groups or abs(groups[-1][0] - top) > 2.8:
            groups.append([top, [(x, text)]])
        else:
            groups[-1][1].append((x, text))
    if len(groups) > MAX_LINES_PER_PAGE:
        raise ValueError("too_many_pdf_visual_lines")
    result = []
    for _, items in groups:
        row = {k: [] for k in EXPECTED_COLUMNS}
        for x, text in sorted(items):
            ratio = x / width
            for n, label in enumerate(EXPECTED_COLUMNS):
                if BORDERS[n] <= ratio < BORDERS[n+1]:
                    row[label].append(text)
                    break
        result.append({k: " ".join(v) for k, v in row.items()})
    return result


def parsed_pdf_report_time(first_page_text):
    if not isinstance(first_page_text, str):
        raise ValueError("missing_pdf_printed_report_header")
    m = PAGE_DATE.search(first_page_text)
    if not m:
        raise ValueError("missing_pdf_printed_report_header")
    naive = datetime.strptime(" ".join(m.groups()), "%m/%d/%y %I:%M %p")
    first = naive.replace(tzinfo=ET, fold=0)
    second = naive.replace(tzinfo=ET, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError("ambiguous_pdf_printed_fall_dst_time")
    return first.astimezone(timezone.utc)


def parse_table(rows_by_page, printed_at, report_labeled_at):
    """Parse only explicit PDF cells. Carry last game/team across wrapped rows."""
    if (not isinstance(rows_by_page, list) or not 1 <= len(rows_by_page) <= MAX_PAGES
            or printed_at != report_labeled_at):
        raise ValueError("printed_pdf_time_disagrees_with_source_filename")
    source, filed, seen, counters = [], [], set(), Counter()
    date_text, matchup, team_code, last = None, None, None, None
    for page_index, lines in enumerate(rows_by_page):
        if not isinstance(lines, list):
            raise ValueError("invalid_pdf_page_lines")
        last = None  # Reason text never flows implicitly between pages.
        for line in lines:
            c = _cells(line)
            # Explicit date is required at least once in the table. This may
            # persist across later pages of the same unbroken original PDF.
            if DATE.fullmatch(c["date"]):
                try:
                    date_text = datetime.strptime(c["date"], "%m/%d/%Y").date().isoformat()
                except ValueError as exc:
                    raise ValueError("invalid_pdf_game_date") from exc
            elif c["date"] and "Game Date" not in c["date"]:
                # A title or page number in the date column is not a game row.
                continue
            m = MATCH.fullmatch(c["matchup"])
            if m:
                away_code, home_code = m.groups()
                if away_code not in TEAM_CODES or home_code not in TEAM_CODES or away_code == home_code:
                    raise ValueError("unknown_or_duplicate_pdf_matchup_club")
                matchup = (away_code, home_code)
                team_code = None
                last = None
            elif c["matchup"] and c["matchup"] != "Matchup":
                continue
            if not date_text or not matchup:
                continue
            if c["team"]:
                candidate = TEAMS.get(nba_team_name(c["team"]))
                if not candidate:
                    if c["team"] not in ("Team",):
                        counters["unknown_pdf_team_name"] += 1
                        team_code = None
                    continue
                if candidate not in matchup:
                    raise ValueError("pdf_team_does_not_belong_to_matchup")
                team_code = candidate
                last = None
            if not team_code:
                continue
            game_key = (date_text, matchup[0], matchup[1], team_code)
            filing_note = " ".join((c["status"]+" "+c["reason"]).split())
            if c["player"]:
                if not PERSON.fullmatch(c["player"]):
                    # Unexpected player text must not be silently mapped to a
                    # different row or interpreted as an actual individual.
                    counters["unparsed_player_name_cell"] += 1
                    last = None
                    continue
                if c["status"] not in STATUSES:
                    counters["unparsed_player_status_cell"] += 1
                    last = None
                    continue
                lastname, firstname = (x.strip() for x in c["player"].split(",", 1))
                if not lastname or not firstname:
                    counters["unparsed_player_name_cell"] += 1
                    last = None
                    continue
                name = firstname + " " + lastname
                identity = game_key + (name.casefold(),)
                if identity in seen:
                    raise ValueError("duplicate_player_in_same_pdf_matchup")
                seen.add(identity)
                item = {
                    "record_type": "nba_official_pdf_player_status_extracted_for_review_only",
                    "game_date_et": date_text, "matchup": matchup[0] + "@" + matchup[1],
                    "team_name": TEAM_CODES[team_code], "nba_team_abbreviation": team_code,
                    "source_player_name_last_first": c["player"],
                    "source_player_name_display": name,
                    "nba_person_id": None, "espn_athlete_id": None,
                    "source_injury_designation": c["status"],
                    "source_reason": c["reason"], "pdf_page_number": page_index+1,
                    "team_filing_not_submitted": False,
                    "player_current_game_active_status_verified": False,
                    "roster_player_id_crosswalk_verified": False,
                    "official_report_status_not_official_active_list": True,
                    "market_eligibility_verified": False,
                    "qualified_for_prop_training": False,
                    "certified_prediction": False,
                    "bet_ready": False, "champion_001_modified": False,
                }
                source.append(item)
                last = item
                counters["explicit_player_rows"] += 1
            elif "NOT YET SUBMITTED" in filing_note.upper():
                record_key = game_key
                if record_key not in seen:
                    seen.add(record_key)
                    filed.append({
                        "record_type": "nba_official_pdf_team_report_not_submitted_research_only",
                        "game_date_et": date_text,
                        "matchup": matchup[0] + "@" + matchup[1],
                        "team_name": TEAM_CODES[team_code], "team_abbreviation": team_code,
                        "filing_status": "not_yet_submitted",
                        "confirmed_all_players_available": False,
                        "player_clearance_count": 0,
                        "bet_ready": False, "champion_001_modified": False,
                    })
                    counters["team_filings_missing"] += 1
                last = None
            elif (last and c["reason"] and not
                  any(c[k] for k in ("date", "time", "matchup", "team", "player", "status"))):
                # A wrapped reason carries no newly assigned player/status.
                new_reason = (last["source_reason"]+" "+c["reason"]).strip()
                if len(new_reason) > 500:
                    raise ValueError("pdf_reason_too_long_or_misaligned")
                last["source_reason"] = new_reason
    return source, filed, dict(sorted(counters.items()))


def parse_pdf_bytes(raw, url):
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_PDF_BYTES:
        raise ValueError("invalid_original_injury_pdf_bytes")
    if not raw.startswith(b"%PDF-") or not raw.rstrip().endswith(b"%%EOF"):
        raise ValueError("truncated_or_non_pdf_original")
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber_dependency_unavailable") from exc
    label_at = report_label_from_url(url)
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if not 1 <= len(pdf.pages) <= MAX_PAGES:
            raise ValueError("nba_injury_pdf_page_limit")
        first_text = pdf.pages[0].extract_text() or ""
        printed_at = parsed_pdf_report_time(first_text)
        if printed_at != label_at:
            raise ValueError("pdf_printed_time_disagrees_with_filename")
        pages = []
        for page in pdf.pages:
            if not (400 <= page.width <= 1400 and 400 <= page.height <= 1400):
                raise ValueError("nba_pdf_unexpected_page_geometry")
            words = page.extract_words(x_tolerance=1.6, y_tolerance=2.5,
                                       keep_blank_chars=False)
            pages.append(word_lines(words, page.width))
    return parse_table(pages, printed_at, label_at)


def _events(events, observed):
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("invalid_pregame_injury_event_list")
    result, seen = [], set()
    for event in events:
        if not isinstance(event, dict) or event.get("league") != "nba":
            continue
        if (event.get("record_type") != "prospective_evidence_snapshot_research_only"
                or event.get("player_level_status_parsed_and_verified") is not False
                or event.get("qualified_for_challenger_backtest") is not False
                or event.get("certified_prediction") is not False
                or event.get("model_probability") is not None
                or event.get("bet_ready") is not False
                or event.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nba_pregame_event_for_injury_linkage")
        eid = event.get("espn_schedule_event_id")
        if not isinstance(eid, str) or not eid.isdecimal() or eid in seen:
            raise ValueError("missing_or_duplicated_espn_upcoming_game_id")
        seen.add(eid)
        start, snap = instant(event["event_start_utc"]), instant(event["snapshot_completed_at_utc"])
        if not snap <= observed < start:
            # No retroactive source evidence attached to an already-started
            # match or time-invalid prospective game.
            continue
        home, away = nba_team_name(event.get("home_team")), nba_team_name(event.get("away_team"))
        if home not in TEAMS or away not in TEAMS or home == away:
            continue
        result.append({"id": eid, "day": start.astimezone(ET).date().isoformat(),
                       "home_code": TEAMS[home], "away_code": TEAMS[away]})
    return result


def link_players(rows, unsubmitted, events, observed):
    checked = _events(events, observed)
    statuses = Counter()
    output = []
    for item in rows:
        want = (item["game_date_et"], item["matchup"])
        matching = [game for game in checked
                    if (game["day"], game["away_code"]+"@"+game["home_code"]) == want
                    and item["nba_team_abbreviation"] in (game["away_code"],game["home_code"])]
        row = dict(item)
        if len(matching) == 1:
            row["espn_event_id_research_match"] = matching[0]["id"]
            row["game_match_status"] = "exact_date_clubs_research_only"
        elif len(matching) > 1:
            row["espn_event_id_research_match"] = None
            row["game_match_status"] = "ambiguous_multiple_upcoming_game_ids"
        else:
            row["espn_event_id_research_match"] = None
            row["game_match_status"] = "no_future_matching_pregame_event"
        # A listed "Available" is not automatically lineup-confirmed or safe
        # as a prop bet, especially with frequent later injury report changes.
        row["player_current_game_active_status_verified"] = False
        row["qualified_for_prop_training"] = False
        row["bet_ready"] = False
        output.append(row)
        statuses[row["game_match_status"]] += 1
    return output, unsubmitted, dict(sorted(statuses.items()))


def run(capture_dir, events, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("source_review_requires_aware_observation_time")
    root = Path(capture_dir)
    report_path = root / "nba_injury_original_report.json"
    if not report_path.is_file():
        raise FileNotFoundError("missing_original_nba_injury_report_metadata")
    receipt = json.loads(report_path.read_text(encoding="utf8"))
    if not isinstance(receipt, dict) or receipt.get("stage") != "challenger_original_nba_pregame_injury_pdf_archive_research_only":
        raise ValueError("invalid_nba_injury_archive_report")
    state = receipt.get("source_status")
    results, unsubmitted, coverage = [], [], {}
    failure = None
    if state == "captured_original_index_and_pdf":
        if (receipt.get("original_pdf_authorship_cryptographically_verified") is not False
                or receipt.get("report_filename_label_externally_authenticated") is not False
                or receipt.get("nba_players_confirmed_active") != 0
                or receipt.get("qualified_player_prop_training_observations") != 0
                or receipt.get("certified_positive_ev_bets") != 0
                or receipt.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nba_original_injury_report_flags")
        observed = instant(receipt["capture_observed_at_utc"])
        if observed > now.astimezone(timezone.utc):
            raise ValueError("injury_pdf_observed_in_future")
        raw = (root/"nba_injury_original_report.pdf").read_bytes()
        html = (root/"nba_injury_original_index.html").read_bytes()
        if (_sha(raw) != receipt.get("original_pdf_sha256")
                or _sha(html) != receipt.get("official_nba_index_sha256")
                or receipt.get("official_nba_index_url") != INDEX_URL):
            raise ValueError("original_nba_injury_report_bytes_changed_since_capture")
        try:
            source, unsubmitted, extracted = parse_pdf_bytes(raw, receipt["official_nba_report_url"])
            results, unsubmitted, coverage = link_players(source, unsubmitted, events, observed)
        except (ValueError, TypeError, OverflowError, RuntimeError) as exc:
            failure = "pdf_player_extraction_blocked_"+type(exc).__name__
            extracted = {}
            results, unsubmitted, coverage = [], [], {}
    else:
        extracted = {}
        failure = "original_nba_pdf_not_captured"
    summary = {
        "stage": "challenger_nba_official_pregame_pdf_player_rows_review_only",
        "original_pdf_source_status": state,
        "pdf_extraction_error": failure,
        "report_source_url": receipt.get("official_nba_report_url"),
        "actual_original_pdf_observed_utc": receipt.get("capture_observed_at_utc"),
        "original_pdf_sha256": receipt.get("original_pdf_sha256"),
        "player_rows_extracted_from_official_pdf": len(results),
        "teams_report_not_yet_submitted": len(unsubmitted),
        "raw_column_parse_diagnostics": extracted,
        "matched_pregame_game_statuses": coverage,
        "source_row_observation_is_pregame_certified": False,
        "active_player_roster_verified": 0,
        "individual_player_id_crosswalk_verified": 0,
        "injury_report_status_is_final_lineup_verified": False,
        "qualified_prop_training_observations": 0,
        "trained_player_prop_models": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("PDF layout-derived player rows are review evidence. "
                    "Unsubmitted team filings, absent names and even Available "
                    "PDF designations cannot verify active-game participation. "
                    "No external player ID, independent original publication time, "
                    "bookmaker market settlement, pregame minutes or training."),
    }
    return results, unsubmitted, summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir", required=True)
    p.add_argument("--events")
    p.add_argument("--output-dir", default="nba_injury_player_rows_review")
    args = p.parse_args(argv)
    events = []
    if args.events:
        path = Path(args.events)
        if not path.is_file():
            raise FileNotFoundError("missing_injury_pregame_event_snapshots")
        events = [json.loads(x) for x in path.read_text(encoding="utf8").splitlines() if x.strip()]
    rows, filings, report = run(args.capture_dir, events)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest/"nba_injury_pdf_player_review.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf8")
    (dest/"nba_injury_pdf_team_filings.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in filings),encoding="utf8")
    (dest/"nba_injury_pdf_player_report.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"player_rows_parsed_research_only":report["player_rows_extracted_from_official_pdf"],
                      "teams_unsubmitted":report["teams_report_not_yet_submitted"],
                      "extraction_error":report["pdf_extraction_error"],
                      "bet_ready_selections":0},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
