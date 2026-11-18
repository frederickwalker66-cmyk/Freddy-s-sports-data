"""Read existing V8 artifacts into one provenance-stamped V9 Sharp Edge board.

This is an evidence index, not a betting engine. Never calls sports providers,
dispatches other Actions workflows, certifies prices/probabilities or wagers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import os
import re
import subprocess

SPECS = {
    "one_display": ("v8-one-command.yml", "v8-one-command-", "ONE_DISPLAY_SHARP_EDGE.json"),
    "sharp_edge": ("v8-nfl-player-props-edge.yml", "v8-nfl-props-edge-", "NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json"),
    "schedule": ("challenger-eight-sport-source-preflight.yml", "eight-sport-source-preflight-", "eight_sport_schedule_coverage.json"),
}
ALLOWED_FILES = {
    "one_display": ("ONE_DISPLAY_SHARP_EDGE.json", "FULL_STACK_BEST_BETS.json"),
    "sharp_edge": ("NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json", "NBA_NFL_FULL_GAME_MARKETS_RESEARCH.json",
                   "NBA_NFL_SHARP_EDGE_CALIBRATION.json", "NBA_NFL_SHARP_EDGE_CLV.json",
                   "sharp_prop_line_movements.jsonl", "sharp_game_market_movements.jsonl"),
    "schedule": ("eight_sport_schedule_coverage.json",),
}
MAX_FILE_BYTES = 12_000_000
MAX_DISPLAY_ROWS = 400
MAX_MOVEMENTS = 90
NY = ZoneInfo("America/New_York")
ROLE_NAMES = (
    "Command Center Manager", "Sports Data Analyst", "Sharp Edge Analyst",
    "Parlay Builder", "Risk Manager", "Audit Engineer",
)


def now_utc():
    return datetime.now(timezone.utc)


def stamped(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except ValueError:
        return None


def text_safe(value, limit=170):
    """Render potentially untrusted strings safely inside Github Markdown."""
    value = str(value) if value is not None else "N/A"
    return re.sub(r"[\r\n|<>{}\x00-\x1f]", " ", value)[:limit]


def _gh(args, *, timeout=35):
    p = subprocess.run(["gh", *args], text=True, capture_output=True,
                       check=False, timeout=timeout)
    if p.returncode:
        raise RuntimeError("github_read_request_unavailable")
    return p.stdout


def download_existing(scope, repository, destination, limit=8):
    """Read only successful existing main-branch runs; never dispatch or collect."""
    workflow, prefix, required_file = SPECS[scope]
    destination.mkdir(parents=True, exist_ok=True)
    runs = json.loads(_gh(["run", "list", "--repo", repository, "--workflow", workflow,
                           "--branch", "main", "--status", "success", "--limit", str(limit),
                           "--json", "databaseId,createdAt,url"]))
    if not isinstance(runs, list):
        raise RuntimeError("workflow_history_unavailable")
    for item in runs[:limit]:
        rid = item.get("databaseId")
        if type(rid) is not int or rid <= 0:
            continue
        response = json.loads(_gh(["api", f"repos/{repository}/actions/runs/{rid}/artifacts?per_page=100"]))
        found = [a for a in response.get("artifacts", [])
                 if isinstance(a, dict) and isinstance(a.get("name"), str)
                 and a["name"].startswith(prefix) and not a.get("expired")]
        for artifact in found[:2]:
            out = destination / str(rid)
            out.mkdir(parents=True, exist_ok=True)
            try:
                _gh(["run", "download", str(rid), "--repo", repository, "--name", artifact["name"],
                     "--dir", str(out)], timeout=95)
            except (RuntimeError, subprocess.TimeoutExpired):
                continue
            if not (out / required_file).is_file():
                continue
            metadata = {
                "workflow": workflow, "run_id": rid, "run_url": f"https://github.com/{repository}/actions/runs/{rid}",
                "run_created_at_utc": item.get("createdAt"),
                "artifact_name": artifact["name"],
                "artifact_id": artifact.get("id"),
                "artifact_archived_at_utc": artifact.get("created_at"),
                "scope": scope,
                "type": "archived_github_actions_artifact_not_original_bookmaker_receipt",
            }
            (out / "_V9_SOURCE_RUN.json").write_text(json.dumps(metadata), encoding="utf-8")
            return out, metadata
    raise RuntimeError("no_usable_successful_artifact_in_recent_runs")


def load_file(root, name, source, *, max_rows=MAX_DISPLAY_ROWS):
    """Return parsed allowed JSON/JSONL and a content checksum pointer."""
    if name not in ALLOWED_FILES[source["scope"]]:
        raise ValueError("unsupported_evidence_file")
    path = root / name
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_FILE_BYTES:
        return None, None
    digest = hashlib.sha256(raw).hexdigest()
    try:
        if name.endswith(".jsonl"):
            lines = [json.loads(ln) for ln in raw.decode("utf-8").splitlines()[:max_rows]
                     if ln.strip()]
            parsed = lines
        else:
            parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, None
    ref = {
        "scope": source["scope"],
        "file": name,
        "sha256_of_downloaded_file": digest,
        "run_id": source.get("run_id"),
        "run_url": source.get("run_url"),
        "run_created_at_utc": source.get("run_created_at_utc"),
        "artifact_name": source.get("artifact_name"),
        "original_provider_or_checkout_signature_verified": False,
    }
    return parsed, ref


def _age(utc_value, clock):
    parsed = stamped(utc_value)
    if parsed is None:
        return {"age_minutes": None, "time_status": "UNKNOWN_TIMESTAMP"}
    minutes = (clock - parsed).total_seconds() / 60
    if minutes < -5:
        status = "FUTURE_TIMESTAMP_INVALID"
    elif minutes > 120:
        status = "HISTORICAL_OR_STALE_GT_120_MIN"
    else:
        status = "RECENT_OBSERVATION_NOT_CHECKOUT"
    return {"age_minutes": round(minutes, 1), "time_status": status}


def _read_scope(scope, local_folder, manifest, files, warnings):
    if not local_folder:
        manifest[scope] = {"status": "UNAVAILABLE", "reason": "no_readable_saved_artifact"}
        return {}
    source = {"scope": scope, **local_folder[1]}
    output = {}
    for name in ALLOWED_FILES[scope]:
        data, ref = load_file(local_folder[0], name, source)
        if ref is None:
            warnings.append(f"{scope}:{name}:MISSING_OR_UNREADABLE")
            continue
        output[name] = (data, ref)
        files.append(ref)
    manifest[scope] = {**source, "status": "READ_EXISTING_ARCHIVE_ONLY",
                       "readable_file_count": len(output)}
    return output


def _as_dict(records, key):
    obj = records.get(key)
    return obj[0] if obj and isinstance(obj[0], dict) else {}


def build_board(roots, *, clock=None):
    """Combine snapshots without claiming cross-source model/price authentication."""
    clock = clock or now_utc()
    if clock.tzinfo is None:
        raise ValueError("timezone_aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    manifest, files, warnings, data = {}, [], [], {}
    for scope in SPECS:
        data[scope] = _read_scope(scope, roots.get(scope), manifest, files, warnings)
    display = _as_dict(data["one_display"], "ONE_DISPLAY_SHARP_EDGE.json")
    best = _as_dict(data["one_display"], "FULL_STACK_BEST_BETS.json")
    props = _as_dict(data["sharp_edge"], "NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json")
    games = _as_dict(data["sharp_edge"], "NBA_NFL_FULL_GAME_MARKETS_RESEARCH.json")
    calib = _as_dict(data["sharp_edge"], "NBA_NFL_SHARP_EDGE_CALIBRATION.json")
    clv = _as_dict(data["sharp_edge"], "NBA_NFL_SHARP_EDGE_CLV.json")
    schedule = _as_dict(data["schedule"], "eight_sport_schedule_coverage.json")
    rows = []
    view_ref = data["one_display"].get("ONE_DISPLAY_SHARP_EDGE.json")
    if isinstance(display.get("rows"), list):
        for idx, raw in enumerate(display["rows"][:MAX_DISPLAY_ROWS]):
            if not isinstance(raw, dict):
                continue
            timestamp = raw.get("source_timestamp_utc")
            rows.append({
                "league": raw.get("league"), "game": raw.get("game"),
                "player": raw.get("player"), "category": raw.get("category"),
                "market": raw.get("market"), "selection": raw.get("selection"),
                "line": raw.get("line"), "source_label": raw.get("source_book_label"),
                "source_timestamp_utc": timestamp,
                "american_odds_attributed_unverified": raw.get("american_odds"),
                "break_even_market_price_percent_unverified": raw.get("break_even_probability_percent"),
                "no_vig_market_price_percent_unverified": raw.get("no_vig_market_probability_percent"),
                "uncalibrated_research_rule_percent_not_champion": raw.get("research_model_probability_percent"),
                "certified_native_model_probability_percent": None,
                "certified_ev_percent": None, "qualified_sharp_handle_percent": None,
                "certified_clv_percent": None,
                "action": "HOLD_RESEARCH_ONLY",
                **_age(timestamp, clock),
                "evidence": {**view_ref[1], "json_array_pointer": f"/rows/{idx}"} if view_ref else None,
            })
    movements = []
    for filename, market_class in (("sharp_prop_line_movements.jsonl", "PLAYER_PROP"),
                                   ("sharp_game_market_movements.jsonl", "GAME_MARKET")):
        pair = data["sharp_edge"].get(filename)
        if not pair or not isinstance(pair[0], list):
            continue
        for idx, raw in enumerate(pair[0][:MAX_MOVEMENTS]):
            if not isinstance(raw, dict):
                continue
            observed = raw.get("last_capture_utc") or raw.get("latest_provider_quote_utc")
            movements.append({
                "market_class": market_class, "league": raw.get("league"),
                "game": " @ ".join(x for x in (raw.get("away_team"), raw.get("home_team"))
                                     if isinstance(x, str)),
                "player": raw.get("player_name") if market_class == "PLAYER_PROP" else None,
                "market": raw.get("stat") or raw.get("market"),
                "line": raw.get("line", raw.get("latest_line")),
                "provider_event_id_unverified": raw.get("provider_event_id"),
                "observed_utc": observed, **_age(observed, clock),
                "status": "HISTORICAL_MARKET_REPRICING_ONLY_HOLD",
                "verified_clv": False, "verified_sharp_money": False,
                "evidence": {**pair[1], "jsonl_line": idx + 1},
            })
    for doc, label in ((display, "one_display"), (props, "sharp_edge_props"),
                       (games, "sharp_edge_game_markets"), (best, "best_bets")):
        claim = doc.get("certified_positive_ev_bets")
        if type(claim) is int and claim > 0:
            warnings.append(f"{label}:UNAUTHENTICATED_UPSTREAM_POSITIVE_EV_CLAIM_NOT_ACCEPTED")
    cover = schedule.get("by_league") if isinstance(schedule.get("by_league"), dict) else {}
    schedule_coverage = {}
    for league in ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league"):
        item = cover.get(league) if isinstance(cover.get(league), dict) else {}
        schedule_coverage[league] = {
            "reported_coverage_class_from_prior_source": item.get("coverage_class", "NOT_CHECKED"),
            "research_source_day_checks": len(item.get("source_checks", []))
                                         if isinstance(item.get("source_checks"), list) else 0,
            "independently_verified_game_eligibility": False,
            "scope": "schedule" if item else "UNAVAILABLE",
        }
    role_notes = (
        (f"{sum(v.get('status') == 'READ_EXISTING_ARCHIVE_ONLY' for v in manifest.values())}/3 source scopes loaded.",
         "One-source overview; inspect the timestamps before interpreting any research row."),
        (f"{len(schedule_coverage)} leagues indexed; source coverage can be absent or historical.",
         "Check original schedule, roster, injuries and quote event identity separately."),
        (f"{len(rows)} archived display rows and {len(movements)} historical market movements indexed.",
         "No certified independent native probability or bookmaker checkout price from this board."),
        ("Mixed market and parlay evidence indexed, but no qualified joint probability.",
         "All 4-, 6- and 8-leg construction remains HOLD until each leg and correlations qualify."),
        ("Frozen Champion-001; challenger remains research-only; no paid API calls or wagers.",
         "No verification of current DraftKings odds, professional sharp flow, EV or CLV."),
        (f"{len(files)} downloaded source-file hashes and exact row/file pointers retained.",
         f"{len(warnings)} missing or anomalous source/file notices."),
    )
    roles = [{"role": name, "status": "HOLD_RESEARCH_ONLY", "findings": list(role_notes[i])}
             for i, name in enumerate(ROLE_NAMES)]
    return {
        "title": "Freddy's Picks AI V9 — Unified Sharp Edge Evidence Board",
        "generated_utc": clock.isoformat(),
        "generated_eastern": clock.astimezone(NY).isoformat(),
        "classification": "RESEARCH_ONLY_HOLD",
        "six_virtual_staff": roles,
        "source_manifest": manifest,
        "file_evidence_index": files,
        "warnings": warnings,
        "game_and_prop_display_rows": rows,
        "market_repricing_research_rows": movements,
        "reported_calibration_context_only": {
            "nba_original_graded_research_outcomes": calib.get("nba_original_graded_outcomes"),
            "nba_original_pending_grading": calib.get("nba_original_pending_grading"),
            "calibration_certified": False, "native_champion_calibration_applied_to_market": False,
            "reported_research_status": calib.get("decision", "UNAVAILABLE"),
        },
        "reported_quote_coverage_context_only": {
            "archived_nba_prop_observations": props.get("nba_exact_prop_archive_observations"),
            "archived_nfl_prop_observations": props.get("nfl_exact_prop_archive_observations"),
            "today_exact_game_market_boards": games.get("today_recent_upcoming_full_games"),
            "today_paired_prop_markets": props.get("today_paired_prop_price_probability_markets"),
            "source_scope": "saved_research_artifact_not_live_checkout",
        },
        "reported_clv_evidence_status": clv.get("status", "UNAVAILABLE"),
        "eight_league_schedule_source_snapshot": schedule_coverage,
        "certified_native_model_probability_count_by_this_board": 0,
        "verified_executable_draftkings_quote_count_by_this_board": 0,
        "certified_positive_ev_count_by_this_board": 0,
        "qualified_parlays_by_this_board": 0,
        "independently_verified_sharp_handle_count_by_this_board": 0,
        "verified_entry_close_clv_by_this_board": 0,
        "champion_001_modified": False,
        "automated_wagers": 0, "paid_api_requests": 0, "shadow_stake_usd": 0,
        "critical_note": "Provenance hashes verify locally downloaded bytes, NOT publisher authenticity. Research forecasts and price-implied probabilities are never Champion-001 certified forecasts or bet-ready EV.",
    }


def markdown(report):
    lines = [
        "# Freddy's Picks AI V9 — ONE DISPLAY Sharp Edge Evidence Board", "",
        f"Generated Eastern: **{text_safe(report['generated_eastern'])}**",
        "**Status: HOLD / RESEARCH ONLY. Champion-001 frozen; Challenger isolated; no wagers or paid APIs.**",
        "",
        "## Verification gates", "",
        "| Evidence gate | Verified here |",
        "|---|---:|",
    ]
    for label, key in (
        ("Authenticated native Champion probability", "certified_native_model_probability_count_by_this_board"),
        ("Executable DraftKings checkout prices", "verified_executable_draftkings_quote_count_by_this_board"),
        ("Certified +EV selections", "certified_positive_ev_count_by_this_board"),
        ("Correlated qualified parlays", "qualified_parlays_by_this_board"),
        ("Verified sharp handle flow", "independently_verified_sharp_handle_count_by_this_board"),
        ("Verified entry/close CLV", "verified_entry_close_clv_by_this_board")):
        lines.append(f"| {label} | {report[key]} |")
    lines.extend(["", "## Six virtual employees", "",
                  "| Employee | Status | Evidence-focused task |", "|---|---|---|"])
    for role in report["six_virtual_staff"]:
        lines.append(f"| {text_safe(role['role'])} | HOLD | {text_safe(role['findings'][0])} |")
    lines.extend(["", "## Saved source archives (not live odds)", "",
                  "| Source | Archived GitHub run | Status |", "|---|---|---|"])
    for scope, source in report["source_manifest"].items():
        run = source.get("run_url")
        label = f"[{source.get('run_id')}]({run})" if run else "Not available"
        lines.append(f"| {text_safe(scope)} | {label} | {text_safe(source['status'])} |")
    cal = report["reported_calibration_context_only"]
    cv = report["reported_quote_coverage_context_only"]
    lines.extend(["", "## Research-only coverage snapshot", "",
        f"NBA pregame research games graded (upstream): **{cal['nba_original_graded_research_outcomes'] if cal['nba_original_graded_research_outcomes'] is not None else 'unknown'}**; never a market-specific certified calibration.",
        f"NBA archived player-prop observations: **{cv['archived_nba_prop_observations'] if cv['archived_nba_prop_observations'] is not None else 'unknown'}**; NFL: **{cv['archived_nfl_prop_observations'] if cv['archived_nfl_prop_observations'] is not None else 'unknown'}** (historical, not bookable).",
        f"Upstream CLV status: **{text_safe(report['reported_clv_evidence_status'])}**.",
        "", "## Game, player and market rows — strictly HOLD", "",
        "| League | Game / player | Category • Market | Line / side | Price / research p | Timestamp | Evidence |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in report["game_and_prop_display_rows"][:80]:
        evidence = row.get("evidence") or {}
        link = evidence.get("run_url")
        pointer = evidence.get("json_array_pointer", "")
        label = f"[{text_safe(pointer, 40)}]({link})" if link else text_safe(pointer, 40)
        price = row["american_odds_attributed_unverified"]
        rp = row["uncalibrated_research_rule_percent_not_champion"]
        x = f"odds {price if price is not None else 'N/A'} / research p {rp if rp is not None else 'N/A'}"
        selection = row["selection"] or "—"
        line = row["line"] if row["line"] is not None else "—"
        lines.append(f"| {text_safe(row['league'])} | {text_safe(row['game'])} / {text_safe(row['player'])} | {text_safe(row['category'])} • {text_safe(row['market'])} | {text_safe(selection)} {text_safe(line)} | {text_safe(x)} | {text_safe(row['source_timestamp_utc'])} ({text_safe(row['time_status'])}) | {label} |")
    if len(report["game_and_prop_display_rows"]) > 80:
        lines.append(f"Remaining {len(report['game_and_prop_display_rows']) - 80} rows and all exact source SHA-256 references are in the archived JSON.")
    lines.extend(["", "## Historical price movements (not verified CLV or sharp action)", "",
                  "| Market | Game • Player | Line | Last observed UTC | Age | Source |",
                  "|---|---|---|---|---|---|"])
    for row in report["market_repricing_research_rows"][:40]:
        ref = row.get("evidence") or {}
        url = ref.get("run_url")
        pointer = f"{ref.get('file')} line {ref.get('jsonl_line')}"
        shown = f"[{text_safe(pointer)}]({url})" if url else text_safe(pointer)
        lines.append(f"| {text_safe(row['league'])} {text_safe(row['market_class'])} {text_safe(row['market'])} | {text_safe(row['game'])} • {text_safe(row['player'])} | {text_safe(row['line'])} | {text_safe(row['observed_utc'])} | {text_safe(row['time_status'])} | {shown} |")
    lines.extend(["", "## Eight-league schedule-source evidence", "",
                  "| League | Prior captured research coverage |", "|---|---|"])
    for league, item in report["eight_league_schedule_source_snapshot"].items():
        lines.append(f"| {text_safe(league.upper())} | {text_safe(item['reported_coverage_class_from_prior_source'])} |")
    if report["warnings"]:
        lines.extend(["", "## Data gaps / unavailable files"])
        lines.extend(f"- {text_safe(w, 250)}" for w in report["warnings"][:24])
    lines.extend(["", f"**{report['critical_note']}**", "",
                  "Files in the archived bundle include the full JSON with exact source run IDs, file names, SHA-256 hashes, row pointers and missing-data flags."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="v9_results")
    parser.add_argument("--fixture-root", default=None, help="Offline tests only; no live provider calls")
    args = parser.parse_args(argv)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    inputs = {}
    if args.fixture_root:
        base = Path(args.fixture_root)
        for scope in SPECS:
            root = base / scope
            if root.is_dir():
                meta_path = root / "_V9_SOURCE_RUN.json"
                meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {
                    "run_id": None, "run_url": None, "artifact_name": "offline_fixture",
                    "run_created_at_utc": None, "type": "offline_test_fixture",
                }
                inputs[scope] = (root, meta)
    else:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo):
            parser.error("GITHUB_REPOSITORY_required_for_read_only_archive_access")
        if not os.environ.get("GH_TOKEN"):
            parser.error("GH_TOKEN_required_for_read_only_archive_access")
        for scope in SPECS:
            try:
                inputs[scope] = download_existing(scope, repo, destination / "_cached_source" / scope)
            except (ValueError, RuntimeError, subprocess.TimeoutExpired, OSError):
                pass
    board = build_board(inputs)
    (destination / "V9_SHARP_EDGE_EVIDENCE_BOARD.json").write_text(
        json.dumps(board, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8")
    view = markdown(board)
    (destination / "V9_SHARP_EDGE_EVIDENCE_BOARD.md").write_text(view, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as file:
            file.write(view)
    print(json.dumps({
        "saved_source_scopes": sum(x["status"] == "READ_EXISTING_ARCHIVE_ONLY"
                                   for x in board["source_manifest"].values()),
        "research_rows": len(board["game_and_prop_display_rows"]),
        "historical_price_movements": len(board["market_repricing_research_rows"]),
        "status": board["classification"], "wagers": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
