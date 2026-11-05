"""Synthetic provider originals only; no SportsDataIO calls or model promotion."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
import unittest

from challenger_sportsdataio_nba_final_crosscheck import (
    AGREEMENT, corroborate, parse_published_finals, main,
)
from test_challenger_nba_official_final_crosscheck import case, NOW


def original(home=102, away=97, status="Final", when="2026-10-30T23:00:00",
             code="LAC", game_id=24001, is_closed=True):
    return {"GameID":game_id, "HomeTeam":code,"AwayTeam":"BOS",
            "DateTime":"2026-10-30T19:00:00",
            "DateTimeUTC":when, "Status":status,
            "IsClosed":is_closed,
            "HomeTeamScore":home,"AwayTeamScore":away}


def raw(records=None):
    return json.dumps([original()] if records is None else records).encode()


class SportsDataioNbaFinalSourceTests(unittest.TestCase):
    def test_research_only_two_publisher_agreement_with_exact_original_bytes(self):
        c=case()
        bytes_=raw()
        rows,r,originals=corroborate([c],NOW,"unit-key",lambda d,k:bytes_)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["crosscheck_status"],AGREEMENT)
        self.assertEqual(rows[0]["sportsdataio_game_id"],"24001")
        self.assertEqual(rows[0]["sportsdataio_published_score"],{"home":102,"away":97})
        self.assertEqual(rows[0]["source_original_bytes_sha256_self_attested"],
                         hashlib.sha256(bytes_).hexdigest())
        self.assertEqual(r["third_party_published_final_score_agreements_research_only"],1)
        self.assertEqual(r["native_training_qualified_games"],0)
        self.assertEqual(r["official_league_outcomes_authenticated"],0)
        self.assertEqual(r["certified_challenger_001_predictions"],0)
        self.assertEqual(r["direct_draftkings_checkout_quotes_verified"],0)
        self.assertEqual(originals["2026-10-30"]["raw"],bytes_)

    def test_espn_provider_score_disagreement_is_quarantined(self):
        rows,r,_=corroborate([case()],NOW,"key",lambda d,k:raw([original(home=111)]))
        self.assertEqual(rows[0]["crosscheck_status"],
                         "sportsdataio_disagrees_with_espn_score_quarantined")
        self.assertEqual(r["third_party_published_final_score_agreements_research_only"],0)

    def test_sdio_final_must_have_unambiguous_score_and_closed_status(self):
        for payload in [original(status="Scheduled"),
                        original(home=None),original(home=100,away=100),
                        original(is_closed=False)]:
            with self.subTest(payload=payload):
                rows,r,_=corroborate([case()],NOW,"key",
                                     lambda d,k:raw([payload]))
                self.assertNotEqual(rows[0]["crosscheck_status"],AGREEMENT)
                self.assertEqual(r["certified_challenger_001_predictions"],0)

    def test_invalid_provider_utc_date_or_teams_do_not_match(self):
        for payload in [original(code="XXX"),
                        original(when="2026-10-30T21:00:00"),
                        original(when="2026-10-31T23:00:00"),
                        original(game_id=-1)]:
            with self.subTest(payload=payload):
                rows,r,_=corroborate([case()],NOW,"key",
                                     lambda d,k:raw([payload]))
                self.assertNotEqual(rows[0]["crosscheck_status"],AGREEMENT)

    def test_ambiguous_two_different_provider_games_quarantined(self):
        rows,r,_=corroborate([case()],NOW,"key",lambda d,k:raw([
            original(game_id=24001),
            original(game_id=24002)]))
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ambiguous_sportsdataio_final_event_identity")
        self.assertEqual(r["third_party_published_final_score_agreements_research_only"],0)

    def test_duplicate_provider_game_id_not_reinterpreted(self):
        rows,r,_=corroborate([case()],NOW,"key",lambda d,k:raw([
            original(game_id=24001),original(game_id=24001)]))
        self.assertEqual(r["third_party_published_final_score_agreements_research_only"],0)

    def test_missing_api_key_does_not_call_network(self):
        def must_not_call(day,key):
            self.fail("API invoked without key")
        rows,r,_=corroborate([case()],NOW,"",must_not_call)
        self.assertEqual(r["source_failures_by_day"],
                         {"2026-10-30":"sportsdataio_secret_not_configured"})
        self.assertEqual(rows[0]["crosscheck_status"],"sportsdataio_source_unavailable")

    def test_http429_captured_without_retrying(self):
        calls=[]
        def denied(day,key):
            calls.append(day)
            raise HTTPError("https://api.sportsdata.io",429,"rate limit",None,None)
        rows,r,_=corroborate([case()],NOW,"key",denied)
        self.assertEqual(calls,["2026-10-30"])
        self.assertEqual(r["source_failures_by_day"]["2026-10-30"],"HTTP_429")

    def test_bounded_calendar_window(self):
        c=case()
        other=case(event_id="401701004",
                   start_utc="2026-10-29T22:00:00Z",
                   snapshot_utc="2026-10-29T21:00:00Z",
                   outcome_verified_at_utc="2026-10-30T12:00:00Z")
        calls=[]
        def fetch(day,key):
            calls.append(day)
            return raw()
        rows,r,_=corroborate([c,other],NOW,"key",fetch,max_days=1)
        self.assertEqual(calls,["2026-10-30"])
        self.assertEqual(r["source_days_not_requested_due_to_limit"],1)
        self.assertEqual(len(rows),2)

    def test_nba_operated_conflicting_final_cannot_be_overridden(self):
        official_cmp=[{
            "espn_research_event_id":case()["event_id"],
            "crosscheck_status":"nba_second_source_final_score_agrees_research_only",
            "official_nba_score":{"home":101,"away":97},
            "training_row_qualified":False,
            "champion_001_modified":False,
        }]
        rows,r,_=corroborate([case()],NOW,"key",lambda d,k:raw(),
                             official_comparisons=official_cmp)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nba_operated_vs_sportsdataio_result_conflict")
        self.assertEqual(r["third_party_published_final_score_agreements_research_only"],0)

    def test_quarantined_pregame_promoted_candidate_rejected(self):
        c=case(qualified_for_challenger_backtest=True)
        with self.assertRaises(ValueError):
            corroborate([c],NOW,"key",lambda d,k:raw())

    def test_pregame_in_future_cannot_become_result_verification(self):
        c=case(outcome_verified_at_utc="2026-11-06T00:00:00Z")
        with self.assertRaisesRegex(ValueError,"historical_timestamp_order"):
            corroborate([c],NOW,"key",lambda d,k:raw())

    def test_cannot_accept_wrong_provider_original_response_shape(self):
        with self.assertRaises(ValueError):
            parse_published_finals(b'{"GameID": 7}',"2026-10-30")

    def test_cli_preserves_original_bytes_and_never_emits_training(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"candidates.jsonl").write_text(json.dumps(case())+"\n")
            with patch.dict("os.environ",{"SPORTSDATAIO_API_KEY":"synthetic"}):
                with patch("challenger_sportsdataio_nba_final_crosscheck.fetch_original",
                           return_value=raw()) as fetch:
                    main(["--candidates",str(root/"candidates.jsonl"),
                          "--output-dir",str(root)])
                    fetch.assert_called_once()
            result=json.loads((root/"nba_sportsdataio_published_final_report.json").read_text())
            self.assertEqual(result["native_training_qualified_games"],0)
            self.assertEqual(result["third_party_published_final_score_agreements_research_only"],1)
            self.assertTrue((root/"sportsdataio_nba_original_final_source"/
                             "2026-10-30.json").is_file())
            self.assertFalse((root/"historical_results.jsonl").exists())


if __name__=="__main__":
    unittest.main()
