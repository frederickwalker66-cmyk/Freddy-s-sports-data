"""Independent public schedule corroboration, fail-closed fake input tests."""
import unittest
from datetime import datetime,timezone
from independent_schedule_review import ingest_schedule,corroborate
NOW=datetime(2026,10,29,20,0,tzinfo=timezone.utc)
def entry(sgo_start="2026-10-30T00:00:00+00:00"):
    return {"league":"nba","home_team":"Atlanta Hawks","away_team":"Cleveland Cavaliers",
       "event_time_sharpapi":"2026-10-30T00:00:00+00:00",
       "event_time_sgo":sgo_start,"market_type":"moneyline"}
def schedule(start="2026-10-30T00:00:00+00:00"):
    return {"events":[{"league":"nba","home_team":"Atlanta Hawks","away_team":"Cleveland Cavaliers",
       "start_utc":start,"status":"scheduled","source_url":"https://site.api.espn.com/"}],"sources":{"nba":{"status":"retrieved"}}}
class Tests(unittest.TestCase):
    def test_exact_match_does_not_certify_bet(self):
        rows,report=corroborate([entry()],[],schedule(),NOW)
        self.assertEqual(report["public_schedule_corrobated_price_pairs"],1)
        self.assertTrue(rows[0]["independent_public_schedule_corrobated"])
        self.assertFalse(rows[0]["bet_ready"])
        self.assertEqual(rows[0]["model_probability"],None)
    def test_provider_ten_minute_disagreement_blocks_match(self):
        rows,r=corroborate([entry("2026-10-30T00:10:00+00:00")],[],schedule(),NOW)
        self.assertEqual(r["public_schedule_corrobated_price_pairs"],0)
        self.assertEqual(rows[0]["schedule_rejection_reason"],"provider_start_disagrees_with_independent_schedule")
    def test_missing_schedule_is_not_proof(self):
        rows,r=corroborate([entry()],[],{"events":[],"sources":{}},NOW)
        self.assertEqual(r["public_schedule_corrobated_price_pairs"],0)
    def test_source_failure_stays_unavailable(self):
        def fail(url):raise TimeoutError("network")
        evidence=ingest_schedule("2026-10-29",fetch=fail,now=NOW)
        self.assertEqual(len(evidence["events"]),0)
        self.assertTrue(all(x["status"]=="unavailable" for x in evidence["sources"].values()))
    def test_pre_game_validation(self):
        sample={"events":[{"id":"11","date":"2026-10-30T00:00:00Z",
            "status":{"type":{"state":"pre"}},"competitions":[{"competitors":[
                {"homeAway":"home","team":{"displayName":"Atlanta Hawks"}},
                {"homeAway":"away","team":{"displayName":"Cleveland Cavaliers"}}
            ]}]}]}
        evidence=ingest_schedule("2026-10-29",fetch=lambda url:sample,now=NOW)
        self.assertEqual(evidence["sources"]["nba"]["scheduled_events"],1)
        self.assertTrue(all(x["status"]=="scheduled" for x in evidence["events"]))
