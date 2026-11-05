"""NCAAF 2026 Week09 source-backed historical contest identity regressions.

Oct 31 Week09 is established by a specific NCAA.com scoreboard page,
not an ISO-week conversion or team name similarity.
"""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from challenger_college_ncaa_score_review import (
    VERIFIED_FBS_WEEK_BY_EASTERN_DAY, VERIFIED_FBS_WEEK_SOURCE_URL,
    corroborate, parse_scoreboard, plan, run,
    school_from_espn, school_from_ncaa,
)

NOW=datetime(2026,11,5,16,tzinfo=timezone.utc)
START="2026-10-31T16:45:00Z"


def packet(home="Ole Miss Rebels",away="Auburn Tigers",day=START,event="401000011"):
    return {
        "record_type":"challenger_original_bytes_feature_lineage_review_only",
        "league":"ncaaf","event_id":event,
        "home_team":home,"away_team":away,
        "event_start_utc":day,
        "snapshot_completed_at_utc":"2026-10-31T15:00:00Z",
        "original_bytes_match_same_run_receipt":True,
        "same_run_receipt_independently_authenticated":False,
        "published_final_only":{
            "home_score":45,"away_score":15,"published_result":"home",
            "published_at_observation_utc":"2026-11-01T03:00:00Z",
            "source_url":"https://site.api.espn.com/research-only"
        },
        "independent_outcome_review":False,
        "market_settlement_rules_verified":False,
        "qualified_for_challenger_training":False,
        "model_probability":None,"certified_prediction":False,
        "bet_ready":False,"champion_001_modified":False,
    }


def source(home="Ole Miss",away="Auburn",date="10/31/2026",
           start=START,score_home="45",score_away="15",state="final"):
    epoch=int(datetime.fromisoformat(start.replace("Z","+00:00")).timestamp())
    return json.dumps({"games":[{
        "game":{"gameID":"7200001","gameState":state,"startDate":date,
                "startTimeEpoch":str(epoch),
                "home":{"names":{"short":home},"score":score_home},
                "away":{"names":{"short":away},"score":score_away}}}]}).encode()


class HistoricalFBSWeekTests(unittest.TestCase):
    def test_october_31_2026_has_explicit_ncaa_week09_publisher_evidence(self):
        self.assertEqual(VERIFIED_FBS_WEEK_BY_EASTERN_DAY["2026-10-31"],(2026,9))
        self.assertEqual(VERIFIED_FBS_WEEK_SOURCE_URL,
                         "https://www.ncaa.com/scoreboard/football/fbs/2026/09")

    def test_old_game_fetch_plan_selects_historical_week09_not_current_week(self):
        self.assertEqual(plan([packet()],NOW),
                         {"ncaaf":"football/fbs/2026/09/all-conf"})

    def test_week09_proxy_score_with_exact_school_identity_counts_research_agreement(self):
        rows,r=corroborate([packet()],{"ncaaf":source()},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_derived_final_score_agrees_research_only")
        self.assertEqual(rows[0]["ncaa_contest_id"],"7200001")
        self.assertEqual(rows[0]["ncaa_proxy_raw_sha256"],
                         hashlib.sha256(source()).hexdigest())
        self.assertEqual(r["ncaa_derived_score_agreements"]["ncaaf"],1)
        self.assertEqual(r["verified_historical_ncaaf_2026_week_09_evidence"],
                         VERIFIED_FBS_WEEK_SOURCE_URL)
        self.assertEqual(r["independently_qualified_training_games"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertFalse(rows[0]["qualified_for_challenger_training"])

    def test_actual_proxy_month_day_year_format_normalized(self):
        rows=parse_scoreboard(source())
        self.assertEqual(rows[0]["source_date"],"2026-10-31")
        self.assertEqual(rows[0]["home_school"],"ole miss")
        self.assertEqual(rows[0]["away_school"],"auburn")

    def test_fake_calendar_day_can_never_correspond_to_old_game(self):
        rows,_=corroborate([packet()],
                           {"ncaaf":source(date="11/07/2026")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "no_exact_ncaa_match_in_checked_source")

    def test_wrong_kickoff_time_is_not_fixed_by_school_alias(self):
        rows,_=corroborate([packet()],{"ncaaf":source(
            start="2026-10-31T18:30:00Z")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "no_exact_ncaa_match_in_checked_source")

    def test_football_home_away_reversal_never_matches(self):
        rows,_=corroborate([packet()],{"ncaaf":source(
            home="Auburn",away="Ole Miss")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "no_exact_ncaa_match_in_checked_source")

    def test_completely_unverified_historical_week_does_not_query_current_week(self):
        p=packet()
        p["event_start_utc"]="2026-09-12T16:45:00Z"
        p["snapshot_completed_at_utc"]="2026-09-12T14:00:00Z"
        p["published_final_only"]["published_at_observation_utc"]="2026-09-13T03:00:00Z"
        self.assertNotIn("ncaaf",plan([p],NOW))
        called=[]
        rows,r,orig=run([p],fetcher=lambda x:called.append(x),
                        now=NOW)
        self.assertEqual(called,[])
        self.assertEqual(orig,{})
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_historical_football_week_not_verified")
        self.assertEqual(r["ncaa_derived_score_agreements"]["ncaaf"],0)

    def test_mixed_verified_and_unverified_old_weeks_fail_closed(self):
        a=packet()
        b=deepcopy(a)
        b["event_id"]="401000012"
        b["event_start_utc"]="2026-10-17T16:45:00Z"
        b["snapshot_completed_at_utc"]="2026-10-17T15:00:00Z"
        b["published_final_only"]["published_at_observation_utc"]="2026-10-18T03:00:00Z"
        self.assertNotIn("ncaaf",plan([a,b],NOW))

    def test_explicit_caller_week_remains_possible_with_exact_source_evidence(self):
        self.assertEqual(plan([packet()],NOW,football_year=2026,football_week=9),
                         {"ncaaf":"football/fbs/2026/09/all-conf"})

    def test_names_from_archived_week09_are_exact_not_mascot_fuzzy(self):
        checked={
          "arkansas razorbacks":"arkansas",
          "missouri tigers":"missouri",
          "ole miss rebels":"ole miss",
          "san jos state spartans":"san jose state",
          "miami hurricanes":"miami fl",
          "north dakota state bison":"north dakota state",
          "south florida bulls":"south florida",
          "georgia southern eagles":"georgia southern",
          "florida international panthers":"fiu",
          "boise state broncos":"boise state",
          "army black knights":"army west point",
          "app state mountaineers":"app state"
        }
        for label,expect in checked.items():
            with self.subTest(label=label):
                self.assertEqual(school_from_espn(label),expect)

    def test_exact_source_short_name_conventions_preserve_distinct_institutions(self):
        checked={
            "Mississippi St.":"mississippi state",
            "Miami (FL)":"miami fl",
            "Miami (OH)":None, # Miami Ohio never automatically maps to Miami FL
            "Army West Point":"army west point",
            "Ga. Southern":"georgia southern",
            "San Jose St.":"san jose state",
            "South Fla.":"south florida",
            "Southern Miss.":"southern miss",
            "Arizona St.":"arizona state",
            "Georgia St.":"georgia state",
            "App State":"app state",
            "NIU":"northern illinois",
            "ULM":"ulm",
        }
        for short,expect in checked.items():
            with self.subTest(short=short):
                self.assertEqual(school_from_ncaa(short),expect)

    def test_unknown_source_school_never_matched_by_mascot_similarity(self):
        p=packet()
        rows,_=corroborate([p],{"ncaaf":source(home="Miss",
                                                away="Auburn")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "no_exact_ncaa_match_in_checked_source")

    def test_source_live_state_never_counts_as_final(self):
        rows,_=corroborate([packet()],
                           {"ncaaf":source(state="live")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_event_not_final_or_incomplete_score")

    def test_source_score_mismatch_is_explicit_not_relabelled_win(self):
        rows,_=corroborate([packet()],
                           {"ncaaf":source(score_home="44")},NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_derived_score_disagrees_with_espn")
        self.assertFalse(rows[0]["bet_ready"])


if __name__=="__main__":
    unittest.main()
