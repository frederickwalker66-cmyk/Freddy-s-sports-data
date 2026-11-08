"""Research-only SharpAPI odds archive and line-movement report.

Reads ALREADY CAPTURED SharpAPI-labeled DraftKings odds. This module does not
call SharpAPI, spend API credits, infer sharp bettor activity, use sportsbook
odds as model forecasts, or certify value edges or available checkout prices.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from challenger_line_movement_timing import analyze_line_movement
from challenger_moneyline_market_baseline import inspect_quote


def summarize_sharp_archive(rows, now=None, archive_run_ids=()):
    if not isinstance(rows, list):
        raise ValueError("quote_rows_must_be_list")
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    counts = Counter()
    accepted = []
    rejected = Counter()
    captures = []
    for row in rows:
        # Existing fail-closed market inspection handles sport, bookmaker,
        # source, timestamp age, market and primary-line identity.
        item, reason = inspect_quote(row)
        if reason:
            rejected[reason] += 1
            continue
        if item["raw"].get("source") != "sharpapi_rest":
            rejected["not_sharpapi_original"] += 1
            continue
        if item["raw"].get("is_main_line") is not True:
            rejected["primary_line_unconfirmed"] += 1
            continue
        if item["received"] > clock:
            rejected["future_archive_capture"] += 1
            continue
        counts[item["raw"]["league"]] += 1
        captures.append(item["received"])
        accepted.append(row)
    movements, movement_report = analyze_line_movement(accepted)
    # No explicit sharps/public betting percentages, proprietary handle data,
    # multi-book consensus or independently authenticated checkout receipt.
    latest = max(captures) if captures else None
    age_minutes = round((clock - latest).total_seconds() / 60, 1) if latest else None
    report = {
        "report_type": "v8_sharpapi_archived_moneyline_research_only",
        "status": ("historical_quotes_analyzed_not_live" if accepted
                   else "no_eligible_saved_sharpapi_quotes"),
        "raw_quote_observations": len(rows),
        "valid_sharpapi_primary_moneyline_quote_observations": len(accepted),
        "eligible_quotes_by_league": dict(sorted(counts.items())),
        "excluded_quote_observations": dict(sorted(rejected.items())),
        "observed_line_movements": len(movements),
        "line_movement_exclusions": movement_report["excluded"],
        "latest_eligible_capture_utc": latest.isoformat() if latest else None,
        "minutes_since_latest_eligible_capture": age_minutes,
        "quote_currently_executable": False,
        "historical_only": True,
        "sharp_money_or_professional_action_inferred": False,
        "sharp_bet_count_verified": 0,
        "model_probability_generated": False,
        "positive_ev_certified": 0,
        "certified_predictions": 0,
        "bet_ready": False,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "archive_run_ids": list(archive_run_ids),
        "warning": ("SharpAPI aggregator observations show historical bookmaker-labeled "
                    "prices, not bet ticket flow, professional wager identity, a "
                    "trained model probability, or current executable sportsbook odds."),
    }
    return report, movements


def read_archive(directory):
    """Read only expected SharpAPI snapshot filenames from downloaded run artifacts."""
    root = Path(directory)
    if not root.exists():
        return [], [], []
    if not root.is_dir():
        raise ValueError("sharp_archive_path_must_be_directory")
    files = sorted(root.rglob("sharpapi_dk_*.jsonl"))
    if len(files) > 30:
        raise ValueError("sharp_archive_file_budget_exceeded")
    rows, runs = [], set()
    for path in files:
        # Directory naming must be supplied by GitHub's run download step,
        # never inferred from content of the quote.
        try:
            run = path.relative_to(root).parts[0]
            if run.isdigit():
                runs.add(int(run))
        except (IndexError, ValueError):
            pass
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) > 100000:
                raise ValueError("sharp_archive_row_budget_exceeded")
    return rows, sorted(runs), [str(x) for x in files]
