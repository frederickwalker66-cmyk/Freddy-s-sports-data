"""Offline provider-quality regression: no sportsbook quote, model or bet."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from challenger_sportsdataio_ingestion_trust import (
    SOURCE_STATUS, SCHEDULE_STATUS, classify_record, inventory, summarize
)
from challenger_sportsdataio_validation import validate_file, main
from sportsdataio_collector import collect


def game():
    return {
        "GameID":24137,"HomeTeam":"BOS","AwayTeam":"NY",
        "DateTimeUTC":"2026-11-05T23:00:00",
        "Status":"Final",
        "HomeTeamScore":162,"AwayTeamScore":155,
        "BettingMoneyLine":-150,
        "TeamStats":{"Points":117, "Assists":28},
        "PlayerGameStats":[{"PlayerID":77,"Points":31,
                            "Rebounds":12,"FantasyPoints":66.5}],
    }


def record(league="nba",extra=None):
    d={
        "source":"sportsdataio","league":league,
        "requested_date_utc":"2026-11-05",
        "request_started_utc":"2026-11-05T21:00:00+00:00",
        "received_at_utc":"2026-11-05T21:00:01+00:00",
        "provider_payload":game(),
        "qualified_for_challenger_backtest":False,
        "certified_prediction":False,"champion_001_modified":False,
        "schedule_metadata_only_research":True,
        "provider_scores_stats_odds_authenticated":False,
        "numeric_values_eligible_for_training":False,
        "model_probability":None,"bet_ready":False,
    }
    if extra:
        d.update(extra)
    return d


class ProviderQuantitativeQuarantineTests(unittest.TestCase):
    def test_known_score_stats_odds_names_marked_untrusted(self):
        result=inventory(game())
        self.assertGreater(result["numeric_non_identifier_values_present"],5)
        self.assertIn("HomeTeamScore",result["score_stats_odds_related_numeric_names"])
        self.assertIn("BettingMoneyLine",result["score_stats_odds_related_numeric_names"])
        self.assertIn("FantasyPoints",result["score_stats_odds_related_numeric_names"])

    def test_identity_metadata_not_mistaken_for_authoritative_score(self):
        item=classify_record(record())
        self.assertEqual(item["schedule_identity_status"],SCHEDULE_STATUS)
        self.assertEqual(item["quantitative_field_source_status"],SOURCE_STATUS)
        self.assertIn("GameID",item["schedule_identity_candidate_fields_present"])
        self.assertFalse(item["stats_ok_for_native_model_features"])
        self.assertFalse(item["odds_ok_for_verified_ev"])
        self.assertFalse(item["provider_account_license_or_real_data_tier_authenticated"])
        self.assertFalse(item["bet_ready"])

    def test_scoreless_research_metadata_is_still_only_candidate(self):
        x=record(extra={"provider_payload":{
            "GameID":17,"HomeTeam":"NY","AwayTeam":"BOS",
            "DateTimeUTC":"2026-11-06T01:00:00"}})
        item=classify_record(x)
        self.assertEqual(item["observed_numeric_nonidentifier_values"],0)
        self.assertFalse(item["data_source_ok_for_training"])
        self.assertFalse(item["odds_ok_for_verified_ev"])

    def test_all_six_supported_leagues_remain_quarantined(self):
        leagues=("nba","nfl","mlb","nhl","ncaaf","ncaab")
        x=summarize([record(league=z) for z in leagues])
        self.assertEqual(x["research_records_checked"],6)
        self.assertEqual(len(x["by_league"]),6)
        self.assertFalse(x["provider_real_unscrambled_data_entitlement_authenticated"])
        self.assertEqual(x["new_training_eligible_rows"],0)
        self.assertEqual(x["new_certified_challenger_predictions"],0)
        self.assertFalse(x["champion_001_modified"])

    def test_attempted_reclassification_of_provider_as_real_fails(self):
        for extras in (
            {"provider_scores_stats_odds_authenticated":True},
            {"numeric_values_eligible_for_training":True},
            {"bet_ready":True},
            {"model_probability":0.83},
            {"schedule_metadata_only_research":False},
            {"qualified_for_challenger_backtest":True}
        ):
            with self.subTest(extra=extras), TemporaryDirectory() as td:
                p=Path(td)/"nba_2026-11-05.jsonl"
                p.write_text(json.dumps(record(extra=extras))+"\n")
                with self.assertRaises(ValueError):
                    validate_file(p)

    def test_unbounded_nested_bad_values_fail_closed(self):
        with self.assertRaises(ValueError):
            inventory({"TooDeep":{"child":{"child":{"child":{"child":{
                "child":{"child":{"child":{"child":3}}}}}}}}})
        with self.assertRaises(ValueError):
            inventory({"X":object()})

    def test_no_raw_payload_numbers_exposed_in_quality_summary(self):
        output=json.dumps(summarize([record()]))
        self.assertNotIn('"HomeTeamScore": 162',output)
        self.assertNotIn('"Points": 117',output)
        self.assertIn("PROVIDER_QUANTITATIVE_SOURCE_NOT_AUTHENTICATED",output)

    def test_missing_utc_or_tampered_capture_fails_validation(self):
        bad=record(extra={"request_started_utc":"2026-11-05T21:00:00"})
        with TemporaryDirectory() as td:
            p=Path(td)/"nba.jsonl"
            p.write_text(json.dumps(bad)+"\n")
            with self.assertRaises(ValueError):
                validate_file(p)

    def test_collector_raw_files_and_quality_tags_remain_separate(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            payload=json.dumps([game()]).encode()
            with patch("sportsdataio_collector.urlopen",return_value=BytesIO(payload)):
                exit_code=collect("synthetic-key",["nba"],"2026-11-05",root/"raw")
            self.assertEqual(exit_code,0)
            collected=json.loads((root/"raw"/"nba_2026-11-05.jsonl").read_text().strip())
            self.assertEqual(collected["provider_payload"]["HomeTeamScore"],162)
            self.assertFalse(collected["provider_scores_stats_odds_authenticated"])
            self.assertFalse(collected["numeric_values_eligible_for_training"])
            self.assertFalse(collected["bet_ready"])
            self.assertIsNone(collected["model_probability"])
            # Validate the real collector output without treating schema as accuracy.
            quality=validate_file(root/"raw"/"nba_2026-11-05.jsonl")
            self.assertEqual(quality["nba"],1)
            with patch("sys.argv",["quality","--input-dir",str(root/"raw"),
                                   "--output-dir",str(root/"quality")]):
                main()
            checked=json.loads((root/"quality"/"validation_report.json").read_text())
            self.assertEqual(checked["records_validated"],1)
            self.assertEqual(checked["quantitative_values_allowed_for_training"],0)
            self.assertFalse(checked["provider_scores_stats_odds_authenticated"])
            self.assertEqual(
                checked["provider_source_quality"]["records_with_unverified_numeric_fields_by_league"]["nba"],1)
            self.assertEqual(checked["qualified_training_examples"],0)

    def test_reject_duplicate_or_untrusted_source_records_in_summary(self):
        tampered=record(extra={"certified_prediction":True})
        with self.assertRaises(ValueError):
            summarize([tampered])

    def test_no_model_artifact_or_sportsbook_write(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            x=summarize([record()])
            (root/"provider_quality.json").write_text(json.dumps(x))
            self.assertFalse((root/"research_model.json").exists())
            self.assertFalse((root/"bet_slip.json").exists())
            self.assertEqual(x["automated_wagers_placed"],0)


if __name__=="__main__":
    unittest.main()
