"""#107–110 research-source score integrity and suspected scramble detection.

SportsDataIO says trial/developer keys can return scrambled scores/statistics/
odds. This does NOT identify the user's key tier. Never repair scores using
a ratio, assert native source authenticity, or train from research data.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median

from challenger_sportsdataio_nba_final_crosscheck import AGREEMENT

DOCUMENTED_TRIAL_DATA = "https://sportsdata.io/help/scrambled-data"
MIN_DAY_PAIRS = 4
RATIO_MAX_SPREAD = 0.04
RATIO_MIN_DEVIATION_FROM_REAL = 0.08


def report(rows, provider):
    if not isinstance(rows,list) or not isinstance(provider,dict):
        raise ValueError("nba_published_source_review_required")
    if provider.get("review_candidates") != len(rows):
        raise ValueError("source_event_count_mismatch")
    if provider.get("native_training_qualified_games") != 0 or provider.get(
            "certified_challenger_001_predictions") != 0 or provider.get(
            "champion_001_modified") is not False:
        raise ValueError("promoted_licensed_source_is_not_research")
    seen = set()
    counts = Counter()
    pairs = defaultdict(list)
    fingerprints = provider.get("source_original_bytes_sha256_by_day")
    if not isinstance(fingerprints,dict):
        raise ValueError("source_original_byte_receipts_missing")
    for row in rows:
        if (not isinstance(row,dict)
                or row.get("record_type") !=
                    "sportsdataio_nba_final_result_comparison_research_only"
                or row.get("source_type") !=
                    "licensed_third_party_nba_result_not_league_operated"
                or row.get("qualified_for_challenger_backtest") is not False
                or row.get("independently_verified_original_pregame_features") is not False
                or row.get("independently_adjudicated_market_outcome") is not False
                or row.get("bookmaker_moneyline_settlement_verified") is not False
                or row.get("certified_prediction") is not False
                or row.get("bet_ready") is not False
                or row.get("champion_001_modified") is not False):
            raise ValueError("unsafe_sportsdataio_score_archive")
        eid=row.get("espn_research_event_id")
        if not isinstance(eid,str) or not eid.isdigit() or eid in seen:
            raise ValueError("missing_or_duplicate_original_espn_event")
        seen.add(eid)
        state=row.get("crosscheck_status")
        if not isinstance(state,str) or not state:
            raise ValueError("provider_result_status_missing")
        counts[state]+=1
        date=row.get("source_date_et")
        if not isinstance(date,str):
            raise ValueError("invalid_original_eastern_game_day")
        digest=row.get("source_original_bytes_sha256_self_attested")
        if date in fingerprints:
            expected=fingerprints[date]
            if (digest != expected
                    or not isinstance(digest,str) or len(digest)!=64
                    or any(x not in "0123456789abcdef" for x in digest)):
                raise ValueError("score_source_fingerprint_mismatch")
        elif digest is not None:
            raise ValueError("score_without_retrieved_original_bytes")
        if state not in (AGREEMENT,
                         "sportsdataio_disagrees_with_espn_score_quarantined",
                         "nba_operated_vs_sportsdataio_result_conflict"):
            continue
        pub=row.get("sportsdataio_published_score")
        espn=row.get("espn_published_score")
        if (not isinstance(pub,dict) or not isinstance(espn,dict)
                or any(type(score.get(side)) is not int or
                       not 0 < score[side] <= 999
                       for score in (pub,espn) for side in ("home","away"))):
            raise ValueError("missing_comparable_final_score_pair")
        if state==AGREEMENT and pub!=espn:
            raise ValueError("false_exact_score_agreement")
        ratios=[pub["home"]/espn["home"],pub["away"]/espn["away"]]
        winning_side_agrees=((pub["home"]>pub["away"]) ==
                             (espn["home"]>espn["away"]))
        if not all(math.isfinite(x) and x>0 for x in ratios):
            raise ValueError("invalid_score_ratio_diagnostic")
        pairs[date].append({
            "ratios":ratios,
            "winner_agrees":winning_side_agrees,
            "exact_match":pub==espn,
        })
    if sum(counts.values()) != len(rows) or counts[AGREEMENT] != provider.get(
            "third_party_published_final_score_agreements_research_only"):
        raise ValueError("provider_score_summary_not_reconciled")
    by_day = {}
    suspicious = []
    for date, games in sorted(pairs.items()):
        mismatched=[g for g in games if not g["exact_match"]]
        ratios=[x for pair in mismatched for x in pair["ratios"]]
        if ratios:
            middle=median(ratios)
            spread=max(ratios)-min(ratios)
        else:
            middle=spread=None
        winner_same=sum(g["winner_agrees"] for g in mismatched)
        possible=(len(mismatched)>=MIN_DAY_PAIRS and
                  winner_same==len(mismatched) and
                  abs(middle-1.0)>=RATIO_MIN_DEVIATION_FROM_REAL and
                  spread<=RATIO_MAX_SPREAD)
        by_day[date]={
            "compared_score_games":len(games),
            "nonmatching_exact_scores":len(mismatched),
            "same_winner_in_conflicted_scores":winner_same,
            "provider_to_espn_point_ratio_median_research_only":
                round(middle,5) if middle is not None else None,
            "provider_to_espn_point_ratio_spread_research_only":
                round(spread,5) if spread is not None else None,
            "consistent_with_noncanonical_or_scrambled_score_pattern":possible,
            "corrected_scores_constructed":0,
            "qualified_training_games":0,
        }
        if possible:
            suspicious.append(date)
    return {
        "stage":"challenger_110_nba_provider_original_score_scramble_integrity",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "records_seen":len(rows),
        "source_successful_dates":provider.get("source_days_succeeded"),
        "by_status":dict(sorted(counts.items())),
        "review_dates_with_comparable_score_pairs":len(by_day),
        "by_date":by_day,
        "dates_with_strong_suspected_transformed_score_pattern":suspicious,
        "suspected_scrambled_score_pattern_days":len(suspicious),
        "scrambled_data_documentation_url":DOCUMENTED_TRIAL_DATA,
        "sportsdataio_api_key_tier_independently_verified":False,
        "licensed_provider_scores_accepted_for_training":0,
        "licensed_provider_player_stats_accepted_for_training":0,
        "licensed_provider_odds_accepted_for_positive_ev":0,
        "untrusted_provider_scores_auto_corrected":0,
        "qualified_challenger_training_games":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "release_action":("VERIFY_SPORTSDATAIO_ENTITLEMENT_AND_REAL_UNSCRAMBLED_"
                          "SCORES_BEFORE_ANY_NATIVE_TRAINING"),
        "warning":("The documented SportsDataIO trial/developer key may scramble "
                   "scores, stats and odds while retaining schedule/team identity. "
                   "Observed consistent daily score ratios are a diagnostic "
                   "fingerprint, not proof of the key plan or a valid way to "
                   "reconstruct real scores. Compare exact original values to "
                   "independent official scores after obtaining real-data "
                   "entitlement. Never infer a corrected score by rescaling."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review",required=True)
    p.add_argument("--provider-report",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    def read(f):
        p=Path(f)
        if not p.is_file():
            raise FileNotFoundError(p)
        return p.read_text(encoding="utf8")
    rows=[json.loads(x) for x in read(args.review).splitlines() if x.strip()]
    r=report(rows,json.loads(read(args.provider_report)))
    target=Path(args.output)
    if target.exists():
        raise FileExistsError("refuse_score_integrity_report_overwrite")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "source_dates_with_suspicious_score_transformation":
            r["suspected_scrambled_score_pattern_days"],
        "source_event_rows":r["records_seen"],
        "valid_training_rows":0,
        "certified_model_predictions":0,
        "champion_001_modified":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
