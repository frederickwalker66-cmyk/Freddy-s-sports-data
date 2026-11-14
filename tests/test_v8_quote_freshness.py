"""Zero-cost sportsbook-source freshness tests: no stale price can become a bet."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_quote_freshness import quote_freshness
from v8_every_sport_bundle import run_full_stack

NOW = datetime(2026,11,14,15,20,tzinfo=timezone.utc)  # 10:20 AM ET


def quote(*, receipt="2026-11-14T02:50:00Z",
          event_start="2026-11-15T00:00:00Z", league="nba"):
    return {
        "source": "sharpapi_rest", "sportsbook": "draftkings",
        "league": league, "record_type": "pregame_odds_observation",
        "certified_prediction": False, "model_probability": None,
        "recorded_at": receipt,
        "timestamp": receipt,
        "event_start_time": event_start,
        "market_type": "player_points", "is_player_prop": True,
    }


class QuoteFreshnessTests(unittest.TestCase):
    def test_missing_archive_is_unavailable_not_a_live_price(self):
        r=quote_freshness([],leagues=("nba",),now=NOW)
        n=r["by_league"]["nba"]
        self.assertEqual(n["source_readiness"],"NO_ARCHIVED_PROVIDER_QUOTES")
        self.assertIsNone(n["latest_valid_archive_receipt_age_minutes"])
        self.assertEqual(n["fresh_exact_paired_market_groups"],0)
        self.assertFalse(r["champion_001_modified"])
        self.assertEqual(r["provider_collection_network_calls"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_last_night_archived_market_is_stale_not_today_pair(self):
        r=quote_freshness([quote()],leagues=("nba",),now=NOW,
                          fresh_paired_by_league={"nba":0})
        n=r["by_league"]["nba"]
        self.assertEqual(n["source_readiness"],"TODAYS_UPCOMING_SOURCE_QUOTES_STALE")
        self.assertEqual(n["today_upcoming_quote_rows_in_archive"],1)
        self.assertEqual(n["today_upcoming_quote_rows_within_120m"],0)
        self.assertEqual(n["today_upcoming_quote_rows_older_than_120m"],1)
        self.assertGreater(n["latest_valid_archive_receipt_age_minutes"],700)
        self.assertFalse(n["independent_model_probability_available"])

    def test_recent_single_prop_is_not_paired_and_not_certified(self):
        q=quote(receipt="2026-11-14T14:40:00Z")
        r=quote_freshness([q],leagues=("nba",),now=NOW)
        self.assertEqual(r["by_league"]["nba"]["source_readiness"],
                         "RECENT_RAW_QUOTES_BUT_NO_EXACT_PAIRED_MARKETS")
        self.assertEqual(r["by_league"]["nba"]["today_upcoming_quote_rows_within_120m"],1)
        self.assertTrue(r["by_league"]["nba"]
                        ["does_not_establish_live_executable_draftkings_prices"])
        with self.assertRaisesRegex(ValueError,"invalid_paired_market_evidence"):
            quote_freshness([q],leagues=("nba",),now=NOW,
                            fresh_paired_by_league={"nba":-1})

    def test_today_and_other_date_and_invalid_receipt_are_distinguished(self):
        past_game=quote(receipt="2026-11-13T13:00:00Z",
                        event_start="2026-11-13T23:00:00Z")
        tomorrow=quote(receipt="2026-11-14T14:00:00Z",
                       event_start="2026-11-16T01:00:00Z")
        bad=quote(receipt="2026-11-15T14:00:00Z")
        invalid=dict(quote(),certified_prediction=True)
        r=quote_freshness([past_game,tomorrow,bad,invalid],
                          leagues=("nba","nfl"),now=NOW)
        nba=r["by_league"]["nba"]
        self.assertEqual(nba["source_readiness"],
                         "NO_ARCHIVED_QUOTES_FOR_TODAYS_UNSTARTED_EVENTS")
        self.assertEqual(nba["historical_started_quote_rows"],1)
        self.assertEqual(nba["upcoming_other_date_quote_rows"],1)
        self.assertEqual(nba["today_upcoming_quote_rows_in_archive"],0)
        self.assertEqual(nba["rejected_rows_by_reason"]
                         ["future_or_inplay_or_inconsistent_source_receipt"],1)
        self.assertEqual(nba["rejected_rows_by_reason"]
                         ["untrusted_source_identity_or_certification_flags"],1)
        self.assertEqual(r["by_league"]["nfl"]["source_readiness"],
                         "NO_ARCHIVED_PROVIDER_QUOTES")

    def test_all_in_one_outputs_include_quote_age(self):
        def execute(cmd, **kwargs):
            return {
                "command":cmd, "champion_001_modified":False,
                "money_wagered_usd":0, "certified_positive_ev_bets":0,
                "research_forward_probability_rows":[],
            }
        with tempfile.TemporaryDirectory() as directory:
            r=run_full_stack(
                command="run_nba",execute_fn=execute,now=NOW,
                sharp_rows=[quote()],output_dir=directory)
            report=json.loads((Path(directory)/
                "FULL_STACK_SOURCE_FRESHNESS.json").read_text())
            self.assertEqual(report["by_league"]["nba"]["source_readiness"],
                             "TODAYS_UPCOMING_SOURCE_QUOTES_STALE")
            self.assertEqual(r["source_quote_freshness"],report)
            self.assertIn("Archived odds freshness",
                (Path(directory)/"FULL_STACK_ALL_IN_ONE_REPORT.md").read_text())
            self.assertEqual(r["certified_positive_ev_bets"],0)


if __name__=="__main__":
    unittest.main()
