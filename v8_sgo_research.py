"""Read SportsGameOdds archived odds as a separate HOLD-only research feed.

No network access, no native model probabilities, no SharpAPI identity joins,
no invented executable DraftKings prices, and no paid requests.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

MARKETS = frozenset(("moneyline", "point_spread", "total_points"))
MAX_FILES = 8
MAX_ROWS = 25000
MAX_FILE_BYTES = 30_000_000
MAX_WATCH_AGE_SECONDS = 120


def aware(value):
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp_not_timezone_aware")
    return dt.astimezone(timezone.utc)


def market_name(m):
    if m in MARKETS:
        return m
    if isinstance(m, str) and m.startswith("player_") and len(m) <= 80:
        return "player_prop"
    return None


def audit_source_archive(directory, *, now=None):
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("aware_clock_required")
    clock = clock.astimezone(timezone.utc)
    sources = []
    if directory is not None and Path(directory).is_dir():
        sources = sorted(Path(directory).rglob("sportsgameodds_dk_*.jsonl"))
    if len(sources) > MAX_FILES:
        raise ValueError("too_many_sgo_source_snapshots")
    counts, exclusions = Counter(), Counter()
    recent = []
    total = 0
    for path in sources:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("unsafe_sgo_source_archive")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total += 1
            if total > MAX_ROWS:
                raise ValueError("sgo_archived_row_budget_exceeded")
            try:
                r = json.loads(line)
                if (not isinstance(r, dict) or r.get("source") != "sportsgameodds_v2"
                        or r.get("record_type") != "pregame_odds_observation"
                        or r.get("sportsbook") != "draftkings"
                        or r.get("certified_prediction") is not False
                        or r.get("model_probability") is not None
                        or r.get("is_main_line") is not False
                        or r.get("cross_provider_identity_verified") is not False
                        or r.get("draftkings_price_independently_verified") is not False):
                    raise ValueError("untrusted_source_or_promotion")
                league = r.get("league")
                family = market_name(r.get("market_type"))
                if league not in ("nba", "nfl", "mlb") or family is None:
                    raise ValueError("unsupported_league_or_market")
                odds = r.get("odds_american")
                if type(odds) not in (int, float) or not math.isfinite(odds) or abs(odds) < 100:
                    raise ValueError("invalid_odds")
                when, receipt, start = (aware(r.get(field)) for field in
                                        ("timestamp", "recorded_at", "event_start_time"))
                if not when <= receipt < start or receipt > clock:
                    raise ValueError("not_original_valid_pregame_capture")
                counts[f"{league}_{family}"] += 1
                seconds = (clock-receipt).total_seconds()
                if 0 <= seconds <= MAX_WATCH_AGE_SECONDS and start > clock:
                    recent.append({
                        "league": league, "market": r.get("market_type"),
                        "matchup": f"{r.get('away_team', 'unknown')} @ {r.get('home_team', 'unknown')}",
                        "selection": r.get("selection"),
                        "line": r.get("line"),
                        "provider_american_odds": odds,
                        "source_quote_utc": when.isoformat(),
                        "captured_utc": receipt.isoformat(),
                        "source_age_seconds": round(seconds, 1),
                        "provider_event_id_unverified": r.get("event_id"),
                        "provider_player_id_unverified": r.get("player_id"),
                        "qualified_main_line": False,
                        "sportsbook_checkout_verified": False,
                        "native_model_probability": None,
                        "certified_positive_ev": False,
                        "decision": "HOLD_SOURCE_BOOK_PROVIDER_ONLY",
                    })
            except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
                exclusions[type(exc).__name__] += 1
    recent.sort(key=lambda x: (x["league"], x["matchup"], x["market"],
                               x["selection"] or "", x["captured_utc"]), reverse=False)
    return {
        "report_type": "V8_SGO_SEPARATE_ARCHIVE_RESEARCH_ONLY",
        "status": ("no_successful_sgo_capture_artifacts" if not sources
                   else "sgo_archived_quotes_research_only"),
        "archive_files_found": len(sources),
        "rows_examined": total,
        "source_labeled_quotes_by_market": dict(sorted(counts.items())),
        "excluded_rows": dict(sorted(exclusions.items())),
        "recent_upcoming_quote_references": recent[:20],
        "recent_upcoming_quote_reference_count": len(recent),
        "source_labeled_not_bookmaker_authenticated": True,
        "max_fresh_quote_age_seconds": MAX_WATCH_AGE_SECONDS,
        "provider_event_and_player_identities_crosschecked": False,
        "source_primary_market_status_authenticated": False,
        "independently_validated_native_model_probabilities": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False, "stake_usd": 0,
        "champion_001_modified": False,
        "decision": "HOLD_PROVIDER_DATA_NOT_NATIVE_MODEL_OR_VERIFIED_CHECKOUT",
    }
