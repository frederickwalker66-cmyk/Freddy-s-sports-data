"""Explain why research-only odds were staged or quarantined, per league.

Strictly read-only. Never upgrades source status, overrides freshness, marks a
main line, invents a forecast, or edits Champion-001. All entries are copied
from the existing independent Challenger audit, not independently recertified.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from challenger_audit import parse_utc, market_family


def fingerprint(row):
    return json.dumps(row, separators=(",", ":"), sort_keys=True, allow_nan=False)


def quote_age_bucket(row):
    try:
        received = parse_utc(row["recorded_at"])
        source = parse_utc(row["timestamp"])
        seconds = (received - source).total_seconds()
        if seconds < 0:
            return "future_provider_timestamp"
        if seconds <= 120:
            return "fresh_0_to_120s"
        if seconds <= 900:
            return "archive_only_121_to_900s"
        return "stale_over_900s"
    except (KeyError, ValueError, TypeError, OverflowError):
        return "timestamp_unavailable"


def diagnose(raw, staged, quarantined, audit, schedule):
    if not isinstance(raw, list) or not isinstance(staged, list) or not isinstance(quarantined, list):
        raise ValueError("all quote inputs must be arrays")
    if not isinstance(audit, dict) or not isinstance(schedule, dict):
        raise ValueError("missing audit or schedule")
    for key, expected in (
        ("observations", len(raw)),
        ("staged_for_research_only", len(staged)),
        ("quarantined", len(quarantined)),
    ):
        if type(audit.get(key)) is not int or audit[key] != expected:
            raise ValueError("inconsistent audited observation count")
    if any(audit.get(k) != 0 for k in (
        "certified_champion_001_predictions", "certified_challenger_predictions",
        "bet_ready_selections", "automated_bets_placed",
        "independently_reverified_sportsbook_prices",
    )) or audit.get("champion_001_modified") is not False:
        raise ValueError("unsafe prediction or betting promotion")
    if schedule.get("bet_ready_selections") != 0 or schedule.get("champion_001_modified") is not False:
        raise ValueError("untrusted schedule provenance")
    events = schedule.get("events")
    if not isinstance(events, list):
        raise ValueError("schedule must contain independent event list")
    if audit.get("independent_schedule_events_available") != len(events):
        raise ValueError("schedule count differs from audit")
    if staged and not events:
        raise ValueError("research staging requires a nonempty schedule")
    if len(staged) + len(quarantined) != len(raw):
        raise ValueError("quarantine coverage not exhaustive")
    originals = Counter(fingerprint(r) for r in raw)
    partition = Counter(fingerprint(r) for r in staged)
    reasons_per_league = defaultdict(Counter)
    for item in quarantined:
        if (not isinstance(item, dict) or not isinstance(item.get("reasons"), list)
                or not item["reasons"] or len(item["reasons"]) != len(set(item["reasons"]))):
            raise ValueError("quarantine reason evidence missing")
        row = item["observation"]
        if not isinstance(row, dict):
            raise ValueError("invalid quarantined observation")
        partition[fingerprint(row)] += 1
        reasons_per_league[row.get("league", "unknown")].update(item["reasons"])
    if originals != partition:
        raise ValueError("audit staged or quarantined records do not match original quotes")

    groups = defaultdict(lambda: {"received": 0, "research_staged": 0,
                                  "quarantined": 0, "market_families": Counter(),
                                  "quote_freshness": Counter()})
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("invalid raw observation")
        bucket = groups[str(row.get("league", "unknown"))]
        bucket["received"] += 1
        bucket["market_families"][market_family(row)] += 1
        bucket["quote_freshness"][quote_age_bucket(row)] += 1
    for row in staged:
        groups[str(row.get("league", "unknown"))]["research_staged"] += 1
    for item in quarantined:
        groups[str(item["observation"].get("league", "unknown"))]["quarantined"] += 1

    report = {
        "report_type": "challenger_source_gate_diagnostics_research_only",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_observations": len(raw),
        "research_staged": len(staged),
        "quarantined": len(quarantined),
        "staged_not_a_bet_recommendation": True,
        "per_league": {k: {
            "received": v["received"], "research_staged": v["research_staged"],
            "quarantined": v["quarantined"],
            "market_families": dict(sorted(v["market_families"].items())),
            "quote_freshness": dict(sorted(v["quote_freshness"].items())),
            "quarantine_causes": dict(sorted(reasons_per_league[k].items())),
        } for k, v in sorted(groups.items())},
        "schedule_events_corroborated": len(events),
        "near_time_mismatches_research_only":
            schedule.get("near_time_mismatches_research_only", {}),
        "near_time_mismatches_promoted": 0,
        "qualified_historical_training_examples": 0,
        "independently_reverified_checkout_prices": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "positive_ev_bets_verified": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Only a diagnostic of already audited quotes. Near-time "
                    "matches cannot authorize a schedule match. Missing/stale "
                    "quotes or unconfirmed main lines never become bet-ready."),
    }
    return report


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf8").splitlines()
            if s.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", required=True)
    p.add_argument("--audit-dir", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    d = Path(args.audit_dir)
    report = diagnose(read_jsonl(args.raw), read_jsonl(d / "research_only.jsonl"),
                      read_jsonl(d / "quarantine.jsonl"),
                      json.loads((d / "report.json").read_text(encoding="utf8")),
                      json.loads((d / "schedule_manifest.json").read_text(encoding="utf8")))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
