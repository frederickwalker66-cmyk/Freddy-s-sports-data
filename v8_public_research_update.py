"""Generate an honest public-facing Freddy's Picks AI research status update.

Strictly no bet recommendations, performance guarantees, synthetic picks,
or 'verified' probabilities from research-only or missing evidence.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

SPORTS = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league")


def safe_public_update(report: dict, as_of: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError("dual_milestone_report_required")
    if report.get("champion_001_modified") is not False:
        raise ValueError("champion_001_state_unverified")
    if report.get("certified_predictions") != 0 or report.get("certified_positive_ev_bets") != 0:
        raise ValueError("unsupported_certification_claim")
    if report.get("automated_wagers") != 0 or report.get("bet_ready") is not False:
        raise ValueError("unsafe_betting_status")
    a = report.get("milestone_a_nba")
    b = report.get("milestone_b_all_eight")
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise ValueError("milestone_fields_missing")
    if a.get("independently_complete") is not False or b.get("independently_complete") is not False:
        raise ValueError("external_release_verification_required")
    raw_models = b.get("research_models_fitted")
    if not isinstance(raw_models, list) or len(raw_models) != len(set(raw_models)) or any(
        sport not in SPORTS for sport in raw_models
    ):
        raise ValueError("unrecognized_research_model")
    summary = (
        f"FREDDY'S PICKS AI | RESEARCH UPDATE ({as_of})\n\n"
        f"NBA research-model artifact: {'available, unverified' if a.get('research_model_fitted') is True else 'not yet fitted'}.\n"
        f"All-sports research: {len(raw_models)} of {len(SPORTS)} league models reported as fitted "
        "(research only; not independently certified).\n"
        "Independent model validation: NOT COMPLETE.\n"
        "Certified positive-EV selections: 0.\n"
        "All betting recommendations: ON HOLD.\n\n"
        "We publish the evidence, methods, and losses as well as wins. "
        "No guaranteed winners. Educational research only."
    )
    return {
        "brand": "Freddy's Picks AI",
        "report_version": "v8-brand-truthful-status-v1",
        "date_utc": as_of,
        "caption": summary,
        "automated_posting": False,
        "certified_selections": 0,
        "source": "V8 dual milestone research report",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default="v8_results/public_research_update.json")
    args = parser.parse_args(argv)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).date().isoformat()
    public = safe_public_update(report, now)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(dest), "certified_selections": 0, "posted": False}))


if __name__ == "__main__":
    main()
