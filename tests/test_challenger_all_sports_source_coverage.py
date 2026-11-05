"""Synthetic all-eight-league evidence coverage tests; no live scores or wagers."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_all_sports_source_coverage import (
    reconcile, main, SOURCE_SPECS, EXPECTED_SECOND_RECORD,
)
from challenger_multisport_evidence_bridge import LEAGUES

NOW=datetime(2026,11,5,16,tzinfo=timezone.utc)
RAW_SHA="a"*64
START="2026-11-01T20:00:00Z"
SNAP="2026-11-01T18:00:00Z"
FINAL="2026-11-02T06:00:00Z"


def lineage(league="nfl",eid="40100001",final=True,features=True):
    return {
        "record_type":"challenger_original_bytes_feature_lineage_review_only",
        "league":league,"event_id":eid,
        "home_team":"Home Team","away_team":"Away Team",
        "event_start_utc":START,"snapshot_completed_at_utc":SNAP,
        "source_event_line_sha256":RAW_SHA,
        "source_archive_file_sha256":RAW_SHA,
        "same_run_receipt_sha256":RAW_SHA,
        "same_run_receipt_independently_authenticated":False,
        "original_bytes_match_same_run_receipt":True,
        "independent_feature_asof_review":False,
        "independent_outcome_review":False,
        "market_settlement_rules_verified":False,
        "qualified_for_challenger_training":False,
        "model_probability":None,
        "certified_prediction":False,"bet_ready":False,
        "champion_001_modified":False,
        "asof_features_for_manual_review_only":
            {"pregame_home_prior_win_rate":0.6} if features else None,
        "published_final_only":{
            "home_score":100,"away_score":90,
            "published_result":"home",
            "published_at_observation_utc":FINAL,
            "source_url":"https://site.api.espn.com/example"
        } if final else None,
    }


def secondary(league,eid="40100001",status=None):
    path,field,agreement,source=SOURCE_SPECS[league]
    x={
        "record_type":EXPECTED_SECOND_RECORD[league] or "nba_secondary_score_review",
        field:eid,
        "crosscheck_status":status or agreement,
        "bet_ready":False,"champion_001_modified":False,
        "certified_prediction":False,
        "qualified_for_challenger_training":False,
    }
    if league in ("nfl","nhl","ncaaf","ncaab","mls","uefa_champions_league"):
        x["league"]=league
    return x


def write(root,lin,by_file=None):
    root=Path(root)
    (root/"original_bytes_lineage_review.jsonl").write_text(
        "".join(json.dumps(x)+"\n" for x in lin))
    if by_file:
        for path,items in by_file.items():
            (root/path).write_text("".join(json.dumps(x)+"\n" for x in items))


def case(lin,by_file=None):
    with TemporaryDirectory() as root:
        write(root,lin,by_file)
        return reconcile(root,NOW)


class AllSportsSourceCoverageTests(unittest.TestCase):
    def test_empty_original_archive_shows_exact_eight_leagues_zero_certification(self):
        r=case([])
        self.assertEqual(set(r["by_league"]),set(LEAGUES))
        self.assertEqual(len(r["by_league"]),8)
        self.assertEqual(r["totals"]["original_pregame_events_receipt_backed"],0)
        self.assertEqual(r["qualified_training_records"],0)
        self.assertFalse(r["champion_001_modified"])
        for sport in LEAGUES:
            self.assertEqual(r["by_league"][sport]["next_evidence_priority"],
                             "collect_original_pregame_snapshots_and_receipts")

    def test_exact_nfl_pregame_and_nflverse_agreement_is_research_only(self):
        r=case([lineage()],{"nfl_second_source_score_review.jsonl":[secondary("nfl")]})
        n=r["by_league"]["nfl"]
        self.assertEqual(n["original_pregame_events_receipt_backed"],1)
        self.assertEqual(n["linked_published_results"],1)
        self.assertEqual(n["second_source_rows_reviewed"],1)
        self.assertEqual(n["second_source_published_score_agreements_research_only"],1)
        self.assertEqual(n["source_class"],"nflverse_community_third_party_score")
        self.assertEqual(n["qualified_chronological_training_records"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_nhl_nba_and_both_college_sports_separate_source_attribution(self):
        leagues=("nba","nhl","ncaaf","ncaab")
        original=[lineage(lg,str(i+40100)) for i,lg in enumerate(leagues)]
        files={}
        for i,lg in enumerate(leagues):
            file=SOURCE_SPECS[lg][0]
            files.setdefault(file,[]).append(secondary(lg,str(i+40100)))
        r=case(original,files)
        for lg in leagues:
            self.assertEqual(r["by_league"][lg]["second_source_published_score_agreements_research_only"],1)
            self.assertEqual(r["by_league"][lg]["qualified_chronological_training_records"],0)
        self.assertIn("proxy",r["by_league"]["ncaab"]["source_class"])
        self.assertIn("league_operated",r["by_league"]["nhl"]["source_class"])

    def test_soccer_two_leagues_never_infer_ninety_minute_market_settlement(self):
        leagues=("mls","uefa_champions_league")
        p=[lineage(lg,str(i+50000)) for i,lg in enumerate(leagues)]
        rows=[secondary(lg,str(i+50000)) for i,lg in enumerate(leagues)]
        r=case(p,{"soccer_90min_second_source_review.jsonl":rows})
        for lg in leagues:
            self.assertEqual(r["by_league"][lg]["second_source_published_score_agreements_research_only"],1)
            self.assertEqual(r["by_league"][lg]["independently_adjudicated_market_settlements"],0)
        self.assertFalse(r["bookmaker_market_settlement_rules_verified"])

    def test_mlb_is_explicit_missing_independent_second_source_stage(self):
        r=case([lineage("mlb")])
        m=r["by_league"]["mlb"]
        self.assertEqual(m["source_class"],"second_source_stage_not_integrated")
        self.assertEqual(m["published_results_without_second_source_review"],1)
        self.assertEqual(m["next_evidence_priority"],"add_separate_publisher_score_crosscheck")

    def test_no_published_final_does_not_count_score_agreement(self):
        r=case([lineage(final=False)])
        self.assertEqual(r["by_league"]["nfl"]["linked_published_results"],0)
        self.assertEqual(r["by_league"]["nfl"]["next_evidence_priority"],
                         "link_later_results_without_retroactive_feature_filling")

    def test_source_review_agreement_without_original_published_final_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"agreement_without_published_final"):
            case([lineage(final=False)],
                 {"nfl_second_source_score_review.jsonl":[secondary("nfl")]})

    def test_published_final_without_secondary_file_means_missing_not_disagreement(self):
        r=case([lineage()])
        n=r["by_league"]["nfl"]
        self.assertEqual(n["source_availability"],"source_review_artifact_missing")
        self.assertEqual(n["published_results_without_second_source_review"],1)
        self.assertEqual(n["second_source_score_disagreements_for_review"],0)

    def test_secondary_mismatch_is_not_credit_for_agreement(self):
        sec=secondary("nfl",status="nflverse_published_score_disagrees_with_espn")
        r=case([lineage()],{"nfl_second_source_score_review.jsonl":[sec]})
        self.assertEqual(r["by_league"]["nfl"]["second_source_score_disagreements_for_review"],1)
        self.assertEqual(r["by_league"]["nfl"]["second_source_published_score_agreements_research_only"],0)
        self.assertEqual(r["certified_challenger_001_predictions"],0)

    def test_nba_extra_retrospective_event_is_quarantined_not_counted(self):
        original=[lineage("nba","4011")]
        items=[secondary("nba","4011"),secondary("nba","4012")]
        r=case(original,{"nba_official_final_crosscheck.jsonl":items})
        n=r["by_league"]["nba"]
        self.assertEqual(n["second_source_rows_reviewed"],1)
        self.assertEqual(n["source_review_rows_quarantined_without_original_lineage"],1)
        self.assertEqual(n["second_source_published_score_agreements_research_only"],1)

    def test_duplicate_original_event_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate_original_sport_event_key"):
            case([lineage(),lineage()])

    def test_duplicate_second_source_event_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate_second_source_event"):
            case([lineage()],{"nfl_second_source_score_review.jsonl":[secondary("nfl"),secondary("nfl")]})

    def test_promoted_second_source_bet_ready_flag_rejected(self):
        row=secondary("nfl")
        row["bet_ready"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_second_source_promotion_flag"):
            case([lineage()],{"nfl_second_source_score_review.jsonl":[row]})

    def test_promoted_original_source_record_is_rejected(self):
        row=lineage()
        row["qualified_for_challenger_training"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_or_unverified_original"):
            case([row])

    def test_tampered_unqualified_original_sha_rejected(self):
        row=lineage()
        row["same_run_receipt_sha256"]="not-a-hash"
        with self.assertRaisesRegex(ValueError,"missing_original_source_byte_receipt"):
            case([row])

    def test_snapshot_observed_at_or_after_tipoff_rejected(self):
        row=lineage()
        row["snapshot_completed_at_utc"]=START
        with self.assertRaisesRegex(ValueError,"future_or_after_game_original"):
            case([row])

    def test_missing_and_ambiguous_secondary_status_quarantined(self):
        row=secondary("nfl")
        row["crosscheck_status"]=None
        with self.assertRaisesRegex(ValueError,"missing_second_source_review_status"):
            case([lineage()],{"nfl_second_source_score_review.jsonl":[row]})

    def test_unsupported_league_in_original_lineage_hard_rejected(self):
        with self.assertRaisesRegex(ValueError,"unsafe_or_unverified_original"):
            case([lineage("wnba")])

    def test_cli_writes_only_readonly_eight_sport_json_report(self):
        with TemporaryDirectory() as root:
            write(root,[lineage()])
            out=Path(root)/"summary.json"
            self.assertEqual(main(["--input-dir",root,"--output",str(out)]),0)
            result=json.loads(out.read_text())
            self.assertEqual(set(result["by_league"]),set(LEAGUES))
            self.assertEqual(result["certified_champion_001_predictions"],0)
            self.assertEqual(result["trained_probability_models_created"],0)
            self.assertFalse((Path(root)/"historical_results.jsonl").exists())


if __name__=="__main__":
    unittest.main()
