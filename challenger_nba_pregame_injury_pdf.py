"""Preserve real, original NBA injury-report PDF evidence in prospectively timed archives.

The official NBA injury-report index lists frequent PDF updates. Capture the
latest report actually observed before the research cutoff, preserve exact
index/PDF bytes, and link ONLY eligible future games by capture time.
No automatic PDF-to-player parsing, no active-roster clearance, no model odds,
no artificial historic timestamps, and no wager certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_prospective_outcome_validation import instant

INDEX_URL = "https://official.nba.com/nba-injury-report-2026-27-season/"
PDF_ROOT = "https://ak-static.cms.nba.com/referee/injury/"
ET = ZoneInfo("America/New_York")
PDF_RE = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf")
MAX_INDEX_BYTES = 2_000_000
MAX_PDF_BYTES = 12_000_000
MAX_EVENTS = 100
MAX_INDEX_AGE_SECONDS = 24 * 60 * 60
MAX_EXISTING_SNAPSHOT_AGE_SECONDS = 6 * 60 * 60


def sha(data):
    return hashlib.sha256(data).hexdigest()


class LinkReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for key, value in attrs:
                if key.lower() == "href" and isinstance(value, str):
                    self.hrefs.append(value)


def report_label_from_url(candidate):
    """Require NBA-owned PDF host, known directory, strict filename and EDT/EST clock."""
    if not isinstance(candidate, str):
        raise ValueError("invalid_nba_injury_report_link")
    u = urlsplit(candidate)
    if (u.scheme != "https" or u.hostname != "ak-static.cms.nba.com" or
            u.port is not None or u.username is not None or u.password is not None or
            u.query or u.fragment or not u.path.startswith("/referee/injury/")):
        raise ValueError("unapproved_nba_pdf_host_or_path")
    filename = u.path.rsplit("/", 1)[-1]
    m = PDF_RE.fullmatch(filename)
    if not m or candidate != PDF_ROOT + filename:
        raise ValueError("invalid_nba_pdf_report_filename")
    day, hh, mm, ampm = m.groups()
    # Exact local time label, not cryptographically authenticated publication time.
    day = datetime.strptime(day, "%Y-%m-%d").date()
    h, minute = int(hh), int(mm)
    if not (1 <= h <= 12 and 0 <= minute <= 59):
        raise ValueError("invalid_nba_pdf_clock_label")
    hour24 = h % 12 + (12 if ampm == "PM" else 0)
    naive = datetime(day.year, day.month, day.day, hour24, minute)
    first = naive.replace(tzinfo=ET, fold=0)
    second = naive.replace(tzinfo=ET, fold=1)
    # Ambiguous fall-back hour cannot be ordered without externally signed time.
    if first.utcoffset() != second.utcoffset():
        raise ValueError("ambiguous_nba_injury_report_dst_clock")
    return first.astimezone(timezone.utc)


def pick_index_report(index_raw, now):
    if not isinstance(index_raw, bytes) or not 1 <= len(index_raw) <= MAX_INDEX_BYTES:
        raise ValueError("missing_or_oversized_nba_official_injury_index")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("need_timezone_aware_capture_clock")
    try:
        html = index_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_nba_injury_index_encoding") from exc
    parser = LinkReader()
    parser.feed(html)
    found = []
    for href in parser.hrefs:
        url = urljoin(INDEX_URL, href)
        try:
            claimed_at = report_label_from_url(url)
        except (TypeError, ValueError, OverflowError):
            continue
        age = (now.astimezone(timezone.utc) - claimed_at).total_seconds()
        if 0 <= age <= MAX_INDEX_AGE_SECONDS:
            found.append((claimed_at, url))
    if not found:
        return None
    found.sort(key=lambda x: (x[0], x[1]))
    latest = found[-1]
    if len({x[1] for x in found if x[0] == latest[0]}) != 1:
        raise ValueError("conflicting_nba_report_links_same_label_time")
    return latest


def _pdf_signature(raw):
    # Integrity check only. PDF signature does not parse player names or verify
    # NBA authorship, and a forged signature is not authenticated document proof.
    return (isinstance(raw, bytes) and 100 <= len(raw) <= MAX_PDF_BYTES
            and raw.startswith(b"%PDF-") and raw.rstrip().endswith(b"%%EOF"))


def _future_events(events, now, label_at):
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("invalid_nba_pregame_event_batch")
    seen, rows, rejected = set(), [], Counter()
    for row in events:
        if not isinstance(row, dict) or row.get("league") != "nba":
            continue
        if (row.get("record_type") != "prospective_evidence_snapshot_research_only"
                or row.get("qualified_for_challenger_backtest") is not False
                or row.get("certified_prediction") is not False
                or row.get("bet_ready") is not False
                or row.get("champion_001_modified") is not False
                or row.get("model_probability") is not None
                or row.get("player_level_status_parsed_and_verified") is not False):
            raise ValueError("unquarantined_nba_event_snapshot")
        eid = row.get("espn_schedule_event_id")
        if not isinstance(eid, str) or not eid.isdecimal() or eid in seen:
            raise ValueError("duplicate_or_missing_future_nba_game_identity")
        seen.add(eid)
        start = instant(row.get("event_start_utc"))
        schedule_seen = instant(row.get("snapshot_completed_at_utc"))
        if not schedule_seen <= now or not schedule_seen < start:
            raise ValueError("nba_schedule_snapshot_clock_invalid")
        if start <= now or label_at >= start:
            rejected["game_started_before_capture_or_pdf_label"] += 1
            continue
        if (now - schedule_seen).total_seconds() > MAX_EXISTING_SNAPSHOT_AGE_SECONDS:
            rejected["pregame_event_snapshot_older_than_six_hours"] += 1
            continue
        rows.append({
            "record_type": "nba_official_injury_pdf_event_attachment_research_only",
            "league": "nba", "espn_schedule_event_id": eid,
            "home_team": row["home_team"], "away_team": row["away_team"],
            "game_start_utc": start.isoformat(),
            "schedule_snapshot_utc": schedule_seen.isoformat(),
            "report_observed_before_tipoff": True,
            "report_includes_this_game_verified": False,
            "team_player_list_extracted_from_pdf": False,
            "individual_player_report_status_verified": False,
            "injury_report_proves_confirmed_active": False,
            "independent_pregame_minutes_projection_verified": False,
            "player_id_crosswalk_verified": False,
            "qualifies_player_prop_training": False,
            "certified_prediction": False, "bet_ready": False,
            "champion_001_modified": False,
        })
    return rows, rejected


def assemble(index_raw, pdf_raw, now, events, report_url, label_at):
    """All output flags remain quarantined even if both sources download."""
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("capture_timestamp_must_be_aware")
    now = now.astimezone(timezone.utc)
    if report_label_from_url(report_url) != label_at or not 0 <= (now - label_at).total_seconds() <= MAX_INDEX_AGE_SECONDS:
        raise ValueError("injury_report_label_not_before_capture")
    if not _pdf_signature(pdf_raw):
        raise ValueError("invalid_or_truncated_nba_injury_pdf")
    eligible, blocked = _future_events(events, now, label_at)
    for event in eligible:
        event.update({
            "official_nba_injury_pdf_url": report_url,
            "official_nba_injury_pdf_sha256": sha(pdf_raw),
            "official_nba_index_url": INDEX_URL,
            "official_nba_index_sha256": sha(index_raw),
            "report_filename_labeled_at_utc_not_authenticated": label_at.isoformat(),
            "report_actual_fetched_at_utc": now.isoformat(),
        })
    report = {
        "stage": "challenger_original_nba_pregame_injury_pdf_archive_research_only",
        "capture_observed_at_utc": now.isoformat(),
        "official_nba_index_url": INDEX_URL,
        "official_nba_index_sha256": sha(index_raw),
        "official_nba_report_url": report_url,
        "original_pdf_sha256": sha(pdf_raw),
        "original_pdf_bytes": len(pdf_raw),
        "report_filename_labeled_at_utc_not_authenticated": label_at.isoformat(),
        "report_filename_label_externally_authenticated": False,
        "original_pdf_authorship_cryptographically_verified": False,
        "event_report_contents_individually_matched": 0,
        "future_nba_event_attachments": len(eligible),
        "excluded_future_event_reasons": dict(sorted(blocked.items())),
        "nba_players_with_verified_injury_status": 0,
        "nba_players_confirmed_active": 0,
        "qualified_player_prop_training_observations": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("An archived NBA-owned injury-report PDF is point-in-time "
                    "source evidence only. Filename time is NOT authenticated "
                    "publication proof; neither the report nor its absence of a "
                    "listing verifies active lineup, same-game participation, "
                    "player ID or projected minutes. No PDF player text parsed."),
    }
    return eligible, report


def fetch_bytes(url, byte_limit):
    if url != INDEX_URL:
        report_label_from_url(url)
    req = Request(url, headers={"Accept": "application/pdf,text/html",
                    "User-Agent": "FreddysPicks-NBAInjuryOriginalReceipt/1.0"})
    with urlopen(req, timeout=20) as response:
        raw = response.read(byte_limit + 1)
    if len(raw) > byte_limit:
        raise ValueError("nba_injury_source_maximum_response_size_exceeded")
    return raw


def run(events=None, now=None, fetcher=fetch_bytes):
    events = [] if events is None else events
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("naive_capture_clock")
    now = now.astimezone(timezone.utc)
    index_raw, pdf_raw = None, None
    failure = None
    selected = None
    try:
        index_raw = fetcher(INDEX_URL, MAX_INDEX_BYTES)
        selected = pick_index_report(index_raw, now)
        if selected is None:
            failure = "no_nba_pdf_index_link_labeled_in_last_24_hours"
        else:
            pdf_raw = fetcher(selected[1], MAX_PDF_BYTES)
            eligible, report = assemble(index_raw, pdf_raw, now, events, selected[1], selected[0])
            report["source_status"] = "captured_original_index_and_pdf"
            return eligible, report, {"index": index_raw, "pdf": pdf_raw}
    except (ValueError, TypeError, OSError, TimeoutError, UnicodeError, OverflowError) as exc:
        failure = "blocked_" + type(exc).__name__
    # Missing/invalid source never attaches future events or claims injury status.
    result = {
        "stage": "challenger_original_nba_pregame_injury_pdf_archive_research_only",
        "capture_observed_at_utc": now.isoformat(),
        "source_status": failure,
        "original_pdf_sha256": None,
        "future_nba_event_attachments": 0,
        "nba_players_with_verified_injury_status": 0,
        "nba_players_confirmed_active": 0,
        "qualified_player_prop_training_observations": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
    }
    return [], result, {}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events")
    p.add_argument("--output-dir", default="pregame_injury_research")
    args = p.parse_args(argv)
    events = []
    if args.events:
        f = Path(args.events)
        if not f.is_file():
            raise FileNotFoundError("missing prospective event file")
        events = [json.loads(x) for x in f.read_text(encoding="utf8").splitlines() if x.strip()]
    rows, report, raw = run(events)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest/"nba_injury_original_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf8")
    (dest/"nba_injury_event_attachments.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True)+"\n" for x in rows), encoding="utf8")
    if raw:
        for key, filename in (("index", "nba_injury_original_index.html"),
                              ("pdf", "nba_injury_original_report.pdf")):
            path = dest / filename
            if path.exists():
                raise FileExistsError("never_overwrite_original_injury_evidence")
            path.write_bytes(raw[key])
    print(json.dumps({"stage": report["stage"], "source_status": report["source_status"],
                      "attachments": report["future_nba_event_attachments"],
                      "player_statuses_verified": 0,
                      "certified_positive_ev_bets": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
