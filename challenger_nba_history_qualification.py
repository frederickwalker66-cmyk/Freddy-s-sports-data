"""Independent NBA history qualification readiness: audit only, never self-certify.

Internal SHA receipts and two currently published scores do not authenticate
original feature publication timestamps or original independent outcomes.
"""
import argparse
import json
from pathlib import Path

REQUIRED = (
    "published_score_second_source_agreement",
    "independent_original_pregame_feature_publication",
    "independently_authenticated_original_capture_receipt",
    "independent_outcome_adjudication",
    "bookmaker_market_settlement_reconciliation",
)


def audit(candidates, comparisons):
    if not isinstance(candidates, list) or not isinstance(comparisons, list):
        raise ValueError("expected candidate and result-review lists")
    by_event = {}
    ambiguous = set()
    for x in comparisons:
        event = x.get("espn_research_event_id") if isinstance(x, dict) else None
        if not isinstance(event, str):
            continue
        if event in by_event:
            ambiguous.add(event)
        else:
            by_event[event] = x
    rows = []
    seen = set()
    for r in candidates:
        if not isinstance(r, dict) or r.get("record_type") != "challenger_nba_history_candidate_review_only":
            raise ValueError("only unqualified NBA candidate records accepted")
        event = r.get("event_id")
        if not isinstance(event, str) or not event.isdigit() or event in seen:
            raise ValueError("invalid/duplicate NBA event")
        seen.add(event)
        c = by_event.get(event)
        score_matches = (
            event not in ambiguous
            and isinstance(c, dict)
            and c.get("crosscheck_status") == "nba_second_source_final_score_agrees_research_only"
            and c.get("official_nba_score") == r.get("published_score_only")
            and c.get("training_row_qualified") is False
        )
        evidence = {key: False for key in REQUIRED}
        evidence["published_score_second_source_agreement"] = bool(score_matches)
        rows.append({
            "event_id": event, "evidence": evidence,
            "independent_qualification": False,
            "outcome_label_from_published_scores_only": r.get("outcome"),
            "missing": [k for k, present in evidence.items() if not present],
            "bet_ready": False, "champion_001_modified": False,
        })
    n = len(rows)
    agreement = sum(x["evidence"]["published_score_second_source_agreement"] for x in rows)
    return rows, {
        "stage": "nba_historical_training_independent_qualification",
        "candidate_games": n, "second_source_result_agreements": agreement,
        "independently_authenticated_pregame_features": 0,
        "independently_adjudicated_game_outcomes": 0,
        "qualified_training_games": 0, "qualified_holdout_games": 0,
        "minimum_training_games": 200, "minimum_later_holdout_games": 50,
        "independently_qualified_shortfall_vs_250": 250,
        "calibration_ready": False, "model_training_authorized": False,
        "champion_001_modified": False,
        "warning": "No way to independently authenticate past publication timestamps using self-issued GitHub receipts. Matching published scores do not certify training. Research review cannot grant its own signoff."
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", required=True)
    p.add_argument("--comparisons", required=True)
    p.add_argument("--output-dir", default="prospective_validation")
    args = p.parse_args(argv)
    def read(path):
        q = Path(path)
        if not q.is_file():
            raise FileNotFoundError(q)
        return [json.loads(line) for line in q.read_text(encoding="utf8").splitlines() if line.strip()]
    rows, report = audit(read(args.candidates), read(args.comparisons))
    dest = Path(args.output_dir); dest.mkdir(parents=True, exist_ok=True)
    (dest/"nba_history_qualification_review.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True)+"\n" for x in rows), encoding="utf8")
    (dest/"nba_history_qualification_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
