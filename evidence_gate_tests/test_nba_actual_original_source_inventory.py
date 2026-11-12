"""Synthetic test fixtures only: never count these as real NBA training games."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from nba_actual_original_source_inventory import audit_archives, digest


class ActualOriginalInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.run=self.root/"12345"
        (self.run/"nba_forward").mkdir(parents=True)
        self.schedule={
            "events":[{
                "id":"401999999", "date":"2026-11-10T00:00:00Z",
                "status":{"type":{"state":"pre"}},
                "competitions":[{"competitors":[
                    {"homeAway":"home","id":"1","team":{"displayName":"Atlanta Hawks"}},
                    {"homeAway":"away","id":"13","team":{"displayName":"Los Angeles Lakers"}},
                ]}]
            }]
        }
        self.original=self.run/"nba_forward"/"nba_original_future_schedule_20261109.json"
        self.original.write_text(json.dumps(self.schedule))
        self.meta={
            "id":12345, "conclusion":"success", "head_branch":"main",
            "head_sha":"abcd", "created_at":"2026-11-09T21:10:00Z",
            "run_started_at":"2026-11-09T21:10:10Z",
            "updated_at":"2026-11-09T21:11:40Z",
        }
        (self.run/"github_run.json").write_text(json.dumps(self.meta))
        self.forecast={
            "record_type":"v8_genuine_forward_clocktime_NBA_Elo_research_only",
            "espn_event_id":"401999999","league":"nba",
            "champion_001_modified":False,"certified_prediction":False,
            "bet_ready":False,"verified_positive_ev":False,
            "source_original_publisher_signed":False,
            "forecast_reconstructed_after_game":False,
            "model_probability_independently_calibrated":False,
            "official_result_verified":False,"stake_usd":0,
            "model_probability_home_win_research_only":0.55,
            "home_team":"Atlanta Hawks","away_team":"Los Angeles Lakers",
            "home_team_espn_id":"1","away_team_espn_id":"13",
            "model_version":"v8-nba-elo-forward-research-test",
            "schedule_source_url":"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261109",
            "start_utc":"2026-11-10T00:00:00Z",
            "forecast_recorded_utc":"2026-11-09T21:11:30Z",
            "schedule_original_received_at_utc":"2026-11-09T21:11:20Z",
            "schedule_original_sha256_local_receipt":digest(self.original.read_bytes()),
        }
        self.store()

    def store(self):
        p=self.run/"nba_forward"/"NBA_FORWARD_FORECASTS.jsonl"
        p.write_text(json.dumps(self.forecast)+"\n")

    def test_one_real_format_original_yields_only_manual_review(self):
        rows,report=audit_archives(self.root)
        self.assertEqual(len(rows),1)
        self.assertEqual(report["unique_nba_first_original_research_forecasts_reviewable"],1)
        self.assertEqual(report["qualified_chronological_training_games"],0)
        self.assertEqual(report["qualified_untouched_holdout_games"],0)
        self.assertFalse(rows[0]["original_publisher_publication_time_independently_authenticated"])
        self.assertFalse(rows[0]["draftkings_checkout_price_verified"])
        self.assertFalse(rows[0]["bet_ready"])

    def test_live_github_run_metadata_agreement_is_not_publisher_authentication(self):
        live=self.root/"live"
        live.mkdir()
        (live/"12345.json").write_text(json.dumps(self.meta))
        rows,report=audit_archives(self.root,live)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]["github_live_metadata_crosscheck"])
        self.assertFalse(report["source_publication_time_externally_authenticated"])
        changed=dict(self.meta,head_sha="fake-sha")
        (live/"12345.json").write_text(json.dumps(changed))
        rows,report=audit_archives(self.root,live)
        self.assertFalse(rows)
        self.assertTrue(any("github_live_run_metadata_conflict" in x
                            for x in report["rejected_or_redundant"]))

    def test_tampered_original_schedule_hash_quarantined(self):
        self.original.write_text(json.dumps({"events":[]}))
        rows,report=audit_archives(self.root)
        self.assertFalse(rows)
        self.assertTrue(any("digest_missing" in x for x in report["rejected_or_redundant"]))

    def test_gameday_not_original_first_pregame_quarantined(self):
        self.forecast["forecast_recorded_utc"]="2026-11-10T01:00:00Z"
        self.store()
        rows,report=audit_archives(self.root)
        self.assertFalse(rows)
        self.assertTrue(any("clock_conflict" in x for x in report["rejected_or_redundant"]))

    def test_wrong_event_team_id_quarantined(self):
        self.forecast["home_team_espn_id"]="999"
        self.store()
        rows,report=audit_archives(self.root)
        self.assertFalse(rows)
        self.assertTrue(any("team_id_or_name" in x for x in report["rejected_or_redundant"]))

    def test_conflicting_first_receipt_remains_quarantined_after_later_duplicate(self):
        # Synthetic original ESPN payloads can have the same event identity
        # and timestamp but different preserved bytes. A later forecast must
        # never silently restore a disputed first receipt to review inventory.
        other=self.run/"nba_forward"/"nba_original_future_schedule_alt.json"
        other.write_text(json.dumps(self.schedule,indent=2))
        first=dict(self.forecast)
        conflicting=dict(self.forecast,
                         schedule_original_sha256_local_receipt=digest(other.read_bytes()))
        later=dict(self.forecast,
                   forecast_recorded_utc="2026-11-09T21:11:35Z")
        path=self.run/"nba_forward"/"NBA_FORWARD_FORECASTS.jsonl"
        path.write_text("".join(json.dumps(r)+"\n" for r in (first,conflicting,later)))
        rows, report=audit_archives(self.root)
        self.assertEqual(rows,[])
        self.assertEqual(report["unique_nba_first_original_research_forecasts_reviewable"],0)
        self.assertEqual(report["rejected_or_redundant"].get("conflicting_first_original_quarantined"),1)
        self.assertEqual(report["rejected_or_redundant"].get("already_quarantined_first_original_ignored"),1)
        self.assertEqual(report["qualified_chronological_training_games"],0)
        self.assertEqual(report["certified_positive_ev_selections"],0)

    def test_repository_without_real_original_runs_never_fakes_games(self):
        with TemporaryDirectory() as folder:
            rows,report=audit_archives(folder)
            self.assertFalse(rows)
            self.assertEqual(report["qualified_chronological_training_games"],0)
            self.assertEqual(report["shortfall_to_200_training"],200)
            self.assertEqual(report["shortfall_to_50_holdout"],50)

if __name__=="__main__":
    unittest.main()
