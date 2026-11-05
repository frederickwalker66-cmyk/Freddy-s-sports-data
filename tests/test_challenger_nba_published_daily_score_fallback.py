"""Synthetic NBA Stats V3 final-score fallback checks, NO model certification."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import hashlib
import unittest
from urllib.error import HTTPError

from challenger_nba_official_final_crosscheck import (
    review_candidates, RESEARCH_STATUS,
)
from challenger_nba_published_daily_score_fallback import (
    review, parse_original_finals, download_original_scoreboard, main,
)
from test_challenger_nba_official_final_crosscheck import case, official, NOW

URL = "https://stats.nba.com/stats/scoreboardv3?GameDate=2026-10-30&LeagueID=00"


def payload(score=102, league="00", day="2026-10-30",
            status=3, start="2026-10-30T23:00:00Z"):
    return {"scoreboard":{
        "leagueId":league,"gameDate":day,
        "games":[{"gameId":"0022600011","gameStatus":status,"gameTimeUTC":start,
            "homeTeam":{"teamId":1610612746,"teamCity":"LA",
                        "teamName":"Clippers","score":score},
            "awayTeam":{"teamId":1610612738,"teamCity":"Boston",
                        "teamName":"Celtics","score":97}}]}}


def encoded(x):
    return json.dumps(x,separators=(",",":")).encode()


class OriginalDailyScoreFallbackTests(unittest.TestCase):
    def sources(self):
        c = case()
        first,_=review_candidates([c],None,NOW)
        return [c],first

    def test_original_daily_score_corroborates_result_without_certifying(self):
        candidates,primary=self.sources()
        data=encoded(payload())
        rows,report,originals=review(candidates,primary,NOW,fetcher=lambda url:data)
        self.assertEqual(rows[0]["crosscheck_status"],RESEARCH_STATUS)
        self.assertTrue(rows[0]["daily_score_fallback_used"])
        self.assertEqual(rows[0]["official_nba_source_url"],URL)
        self.assertEqual(rows[0]["official_nba_game_id"],"0022600011")
        self.assertEqual(rows[0]["official_nba_score"],{"home":102,"away":97})
        self.assertEqual(rows[0]["official_nba_original_json_sha256_self_attested"],
                         hashlib.sha256(data).hexdigest())
        self.assertEqual(report["new_nba_original_daily_score_agreements_research_only"],1)
        self.assertEqual(report["qualified_training_games"],0)
        self.assertEqual(report["certified_challenger_001_predictions"],0)
        self.assertFalse(report["champion_001_modified"])
        self.assertEqual(originals["2026-10-30"]["raw"],data)

    def test_official_access_denied_stays_unqualified(self):
        candidates,primary=self.sources()
        def denied(url):
            raise HTTPError(url,403,"forbidden",None,None)
        rows,r,originals=review(candidates,primary,NOW,fetcher=denied)
        self.assertEqual(rows[0]["crosscheck_status"],"nba_official_source_unavailable")
        self.assertEqual(r["source_failure_types_by_day"]["2026-10-30"],"HTTP_403")
        self.assertEqual(r["combined_second_source_score_agreements_research_only"],0)
        self.assertEqual(originals,{})

    def test_status_not_final_kept_unqualified(self):
        c,p=self.sources()
        rows,r,_=review(c,p,NOW,fetcher=lambda _:encoded(payload(status=1)))
        self.assertEqual(rows[0]["crosscheck_status"],"nba_daily_game_not_final_or_score_missing")
        self.assertEqual(r["qualified_training_games"],0)

    def test_disagreement_blocks_promotion(self):
        c,p=self.sources()
        rows,r,_=review(c,p,NOW,fetcher=lambda _:encoded(payload(score=103)))
        self.assertEqual(rows[0]["crosscheck_status"],"nba_daily_official_final_disagrees_with_espn")
        self.assertEqual(r["new_nba_original_daily_score_agreements_research_only"],0)

    def test_conflicting_nba_operated_sources_are_quarantined(self):
        c,p=self.sources()
        p[0]["crosscheck_status"]=RESEARCH_STATUS
        p[0]["official_nba_score"]={"home":102,"away":97}
        rows,r,_=review(c,p,NOW,fetcher=lambda _:encoded(payload(score=103)))
        self.assertEqual(rows[0]["crosscheck_status"],"nba_daily_official_final_disagrees_with_espn")
        self.assertEqual(r["combined_second_source_score_agreements_research_only"],0)

    def test_wrong_date_and_league_never_counted(self):
        c,p=self.sources()
        for bad in (payload(day="2026-10-31"),payload(league="10")):
            with self.subTest(bad=bad):
                rows,r,_=review(c,p,NOW,fetcher=lambda _:encoded(bad))
                self.assertEqual(r["nba_daily_source_days_succeeded"],0)
                self.assertEqual(r["combined_second_source_score_agreements_research_only"],0)

    def test_noncanonical_nba_team_id_fail_closed(self):
        d=payload()
        d["scoreboard"]["games"][0]["homeTeam"]["teamId"]=123
        with self.assertRaisesRegex(ValueError,"team_id_name_disagreement"):
            parse_original_finals(encoded(d),"2026-10-30")

    def test_duplicate_nba_game_id_fails_whole_day(self):
        d=payload()
        d["scoreboard"]["games"].append(deepcopy(d["scoreboard"]["games"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_or_invalid"):
            parse_original_finals(encoded(d),"2026-10-30")

    def test_mismatched_clocks_never_use_same_named_teams(self):
        c,p=self.sources()
        rows,r,_=review(c,p,NOW,fetcher=lambda _:
                        encoded(payload(start="2026-10-31T02:00:00Z")))
        self.assertEqual(rows[0]["crosscheck_status"],"nba_official_source_unavailable")
        self.assertEqual(r["new_nba_original_daily_score_agreements_research_only"],0)

    def test_two_game_days_bounded_to_latest_date(self):
        c,p=self.sources()
        older=case(event_id="401701002",
                   start_utc="2026-10-29T23:00:00Z",
                   snapshot_utc="2026-10-29T21:00:00Z",
                   outcome_verified_at_utc="2026-10-30T13:00:00Z")
        primary_older,_=review_candidates([older],None,NOW)
        seen=[]
        def fetch(url):
            seen.append(url)
            return encoded(payload())
        rows,r,_=review(c+[older],p+primary_older,NOW,fetcher=fetch,max_days=1)
        self.assertEqual(len(seen),1)
        self.assertIn("GameDate=2026-10-30",seen[0])
        self.assertEqual(r["candidate_days_not_requested_due_bounded_budget"],1)
        self.assertEqual(len(rows),2)

    def test_invalid_future_outcome_rejected(self):
        c,p=self.sources()
        c[0]["outcome_verified_at_utc"]="2026-11-02T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"historical_result_time_not_really_past"):
            review(c,p,NOW,fetcher=lambda _:encoded(payload()))

    def test_missing_primary_source_reference_is_rejected(self):
        c,p=self.sources()
        p[0]["champion_001_modified"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_primary"):
            review(c,p,NOW,fetcher=lambda _:encoded(payload()))

    def test_original_scoreboard_timestamp_without_timezone_fails(self):
        d=payload(start="2026-10-30T23:00:00")
        with self.assertRaises(ValueError):
            parse_original_finals(encoded(d),"2026-10-30")

    def test_duplicate_primary_candidate_ids_rejected(self):
        c,p=self.sources()
        with self.assertRaisesRegex(ValueError,"unsafe_primary"):
            review(c,p+p,NOW,fetcher=lambda _:encoded(payload()))

    def test_cli_archives_original_bytes_without_training(self):
        c,p=self.sources()
        with TemporaryDirectory() as temp:
            root=Path(temp)
            candidates=root/"candidates.jsonl"
            primary=root/"primary.jsonl"
            candidates.write_text(json.dumps(c[0])+"\n")
            primary.write_text(json.dumps(p[0])+"\n")
            with patch("challenger_nba_published_daily_score_fallback.download_original_scoreboard",
                       return_value=encoded(payload())):
                self.assertIsNone(main([
                    "--candidates",str(candidates),
                    "--primary-comparisons",str(primary),
                    "--output-dir",str(root)]))
            report=json.loads((root/"nba_original_daily_score_fallback_report.json").read_text())
            self.assertEqual(report["new_nba_original_daily_score_agreements_research_only"],1)
            self.assertEqual(report["qualified_training_games"],0)
            self.assertTrue((root/"nba_date_scoped_original_final_scoreboards"/"2026-10-30.json").exists())
            self.assertFalse((root/"historical_results.jsonl").exists())


if __name__=="__main__":
    unittest.main()
