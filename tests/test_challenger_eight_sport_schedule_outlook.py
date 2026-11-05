"""Synthetic all-eight-sport schedule lookahead and source/archival coverage tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs,urlparse
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import unittest

from independent_schedule_review import ingest_schedule, SOURCES
from challenger_prospective_pregame import build
from challenger_all_sports_schedule_coverage import audit, main

NOW=datetime(2026,11,5,17,16,tzinfo=timezone.utc)
END=NOW+timedelta(minutes=2)
TODAY="20261105"


def event(gid="401101",tip="2026-11-08T18:00:00Z",
          home="Detroit Lions",away="Chicago Bears",state="pre"):
    return {
        "id":gid,"date":tip,
        "status":{"type":{"state":state}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":home}},
            {"homeAway":"away","team":{"displayName":away}},
        ]}],
    }


def fetcher(fixtures=None,deny=None,calls=None):
    fixtures=fixtures or {}
    deny=set(deny or [])
    def get(url):
        p=urlparse(url)
        day=parse_qs(p.query)["dates"][0]
        league=[k for k,(sport,comp) in SOURCES.items()
                if p.path.endswith("/"+sport+"/"+comp+"/scoreboard")]
        if len(league)!=1:
            raise AssertionError("unexpected ESPN source")
        lg=league[0]
        if calls is not None:
            calls.append((lg,day))
        if (lg,day) in deny:
            raise TimeoutError("fixture denied")
        return {"events":deepcopy(fixtures.get((lg,day),[]))}
    return get


def snapshot(fixtures=None,deny=None,days=7):
    schedule=ingest_schedule("2026-11-05",fetcher(fixtures,deny),
                             now=NOW,lookahead_days=days,clock=lambda:NOW)
    items, report=build(schedule,[],[],None,END)
    return schedule,items,report


class EightSportScheduleOutlookTests(unittest.TestCase):
    def test_all_eight_leagues_explicitly_have_source_diagnostics(self):
        s,records,r=snapshot()
        self.assertEqual(set(s["sources"]),set(SOURCES))
        self.assertEqual(len(s["sources"]),8)
        self.assertEqual(len(records),0)
        result=audit(s,r,records)
        self.assertEqual(set(result["by_league"]),set(SOURCES))
        self.assertEqual(result["totals"]["pregame_events_archived"],0)
        self.assertEqual(result["certified_positive_ev_bets"],0)

    def test_seven_day_window_is_today_plus_seven_future_dates(self):
        s,records,r=snapshot()
        self.assertEqual(s["sources"]["nfl"]["days_checked"],8)
        self.assertEqual(s["sources"]["nfl"]["days_retrieved"],8)
        self.assertEqual(s["sources"]["nfl"]["lookahead"][0]["date_et"],"2026-11-05")
        self.assertEqual(s["sources"]["nfl"]["lookahead"][-1]["date_et"],"2026-11-12")
        self.assertEqual(audit(s,r,records)["by_league"]["nfl"]["coverage_class"],
                         "espn_no_listed_games_in_fully_checked_window")

    def test_weekend_nfl_game_found_while_thursday_slate_empty(self):
        calls=[]
        s=ingest_schedule("2026-11-05",fetcher({("nfl","20261108"):[event()]},calls=calls),
                          now=NOW,lookahead_days=7,clock=lambda:NOW)
        self.assertEqual(s["sources"]["nfl"]["days_checked"],4)
        self.assertEqual(s["sources"]["nfl"]["first_day_raw_events"],0)
        self.assertEqual(s["sources"]["nfl"]["scheduled_events"],1)
        self.assertEqual(s["events"][0]["requested_date_et"],"2026-11-08")
        self.assertEqual(s["events"][0]["league"],"nfl")
        self.assertNotIn(("nfl","20261109"),calls)

    def test_uefa_champions_league_six_days_ahead_is_archived_research_only(self):
        fixtures={("uefa_champions_league","20261110"):[
            event("901101","2026-11-10T20:00:00Z",
                  "Paris Saint-Germain","Bayern Munich")]}
        s,rows,r=snapshot(fixtures)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["league"],"uefa_champions_league")
        self.assertIsNone(rows[0]["model_probability"])
        self.assertFalse(rows[0]["qualified_for_challenger_backtest"])
        a=audit(s,r,rows)
        self.assertEqual(a["by_league"]["uefa_champions_league"]["archived_pregame_games"],1)
        self.assertEqual(a["by_league"]["uefa_champions_league"]["coverage_class"],
                         "all_discovered_future_games_archived_research_only")
        self.assertFalse(a["historical_feature_publication_authenticated"])

    def test_ncaab_tomorrow_and_nfl_sunday_are_both_preserved(self):
        fixtures={
            ("nfl","20261108"):[event()],
            ("ncaab","20261106"):[event("920","2026-11-06T23:00:00Z",
                                      "Duke Blue Devils","North Carolina Tar Heels")],
        }
        s,rows,r=snapshot(fixtures)
        a=audit(s,r,rows)
        self.assertEqual(len(rows),2)
        self.assertEqual(a["by_league"]["nfl"]["source_days_attempted"],4)
        self.assertEqual(a["by_league"]["ncaab"]["source_days_attempted"],2)
        self.assertEqual(a["totals"]["pregame_events_archived"],2)
        self.assertFalse(a["independent_league_schedule_verified"])

    def test_game_today_stops_extra_requests_for_that_sport(self):
        fixtures={("nhl",TODAY):[event("9800","2026-11-05T23:00:00Z",
                                    "New York Rangers","Boston Bruins")]}
        s,rows,r=snapshot(fixtures)
        self.assertEqual(s["sources"]["nhl"]["days_checked"],1)
        self.assertEqual(audit(s,r,rows)["by_league"]["nhl"]["archived_pregame_games"],1)

    def test_source_unavailable_for_all_dates_is_not_no_games(self):
        denied={("mlb",(NOW+timedelta(days=x)).strftime("%Y%m%d")) for x in range(8)}
        s,rows,r=snapshot(deny=denied)
        a=audit(s,r,rows)
        self.assertEqual(s["sources"]["mlb"]["status"],"unavailable")
        self.assertEqual(s["sources"]["mlb"]["days_unavailable"],8)
        self.assertEqual(a["by_league"]["mlb"]["coverage_class"],
                         "partial_or_total_source_failure_not_proof_of_no_games")

    def test_partial_failed_dates_prevent_no_games_claim(self):
        s,rows,r=snapshot(deny={("ncaaf","20261107")})
        a=audit(s,r,rows)
        self.assertEqual(a["by_league"]["ncaaf"]["source_days_failed"],1)
        self.assertEqual(a["by_league"]["ncaaf"]["coverage_class"],
                         "partial_or_total_source_failure_not_proof_of_no_games")

    def test_all_listed_today_games_already_finished_not_empty_slate(self):
        fixtures={("mlb",TODAY):[event("8888","2026-11-05T15:00:00Z",
                                     "New York Yankees","Boston Red Sox",state="post")]}
        s,rows,r=snapshot(fixtures)
        a=audit(s,r,rows)
        self.assertEqual(a["by_league"]["mlb"]["first_day_listed_games"],1)
        self.assertEqual(a["by_league"]["mlb"]["coverage_class"],
                         "games_listed_but_none_future_valid_at_capture")

    def test_missing_archive_event_reports_gap_not_no_game(self):
        fixtures={("nfl","20261108"):[event()]}
        s,rows,r=snapshot(fixtures)
        # Model a game starting while the full history pull was executing:
        # source saw it, but the eventual snapshot could not retain it.
        partial=deepcopy(r)
        partial["scheduled_pregame_events"]=0
        partial["by_league"]["nfl"]["upcoming_events"]=0
        a=audit(s,partial,[])
        self.assertEqual(a["by_league"]["nfl"]["discovered_games_not_archived"],1)
        self.assertEqual(a["by_league"]["nfl"]["coverage_class"],
                         "some_discovered_future_games_missing_from_archive")

    def test_exact_duplicate_espn_ids_on_same_day_never_count_twice(self):
        fixtures={("nfl","20261108"):[event(),event()]}
        s,rows,r=snapshot(fixtures)
        a=audit(s,r,rows)
        self.assertEqual(len(rows),0)
        self.assertEqual(a["by_league"]["nfl"]["source_days_failed"],1)
        self.assertEqual(a["by_league"]["nfl"]["source_future_games_discovered"],0)

    def test_no_game_source_not_automatic_verified_zero_event_sport(self):
        s,rows,r=snapshot()
        a=audit(s,r,rows)
        self.assertFalse(a["independent_league_schedule_verified"])
        self.assertEqual(a["by_league"]["mlb"]["coverage_class"],
                         "espn_no_listed_games_in_fully_checked_window")
        self.assertEqual(a["qualified_chronological_training_games"],0)

    def test_invalid_start_time_or_missing_provider_id_is_not_invented(self):
        p=event(gid="",tip="2026-11-08T18:00:00Z")
        s,rows,r=snapshot({("nfl","20261108"):[p]})
        self.assertEqual(len(rows),0)
        a=audit(s,r,rows)
        self.assertEqual(a["by_league"]["nfl"]["source_game_listings"],1)
        self.assertEqual(a["by_league"]["nfl"]["source_future_games_discovered"],0)

    def test_schedule_event_and_archived_event_ids_must_agree(self):
        s,rows,r=snapshot({("nfl","20261108"):[event()]})
        rows[0]["espn_schedule_event_id"]="999"
        with self.assertRaisesRegex(ValueError,"missing_or_duplicate_original"):
            audit(s,r,rows)

    def test_promoted_probability_or_bet_is_rejected(self):
        s,rows,r=snapshot({("nfl","20261108"):[event()]})
        rows[0]["bet_ready"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_archived_pregame_event"):
            audit(s,r,rows)

    def test_source_counts_changed_after_capture_are_rejected(self):
        s,rows,r=snapshot({("nfl","20261108"):[event()]})
        s["sources"]["nfl"]["scheduled_events"]=15
        with self.assertRaisesRegex(ValueError,"schedule_source_and_archive_counts_disagree"):
            audit(s,r,rows)

    def test_outlook_not_allowed_to_reconstruct_past_game_date(self):
        with self.assertRaisesRegex(ValueError,"actual_eastern_today"):
            ingest_schedule("2026-10-30",fetcher(),now=NOW,lookahead_days=7,clock=lambda:NOW)

    def test_no_request_budget_over_seven_days(self):
        with self.assertRaisesRegex(ValueError,"outside_bounded_window"):
            ingest_schedule("2026-11-05",fetcher(),now=NOW,lookahead_days=8,clock=lambda:NOW)

    def test_zero_day_default_retains_existing_schedule_scan_behavior(self):
        calls=[]
        s=ingest_schedule("2026-11-05",fetcher(calls=calls),now=NOW)
        self.assertEqual(len(calls),8)
        self.assertEqual(s["sources"]["nfl"]["days_checked"],1)

    def test_multiday_source_cannot_use_scan_start_as_response_clock(self):
        with self.assertRaisesRegex(ValueError,"requires_actual_response_clock"):
            ingest_schedule("2026-11-05",fetcher(),now=NOW,lookahead_days=7)

    def test_clock_after_fixture_tipoff_does_not_backdate_nfl_game(self):
        clock_after=datetime(2026,11,8,18,0,1,tzinfo=timezone.utc)
        clock_calls=0
        def measured():
            nonlocal clock_calls
            clock_calls+=1
            # Simulate a source that finishes just after the Sunday's kickoff.
            return clock_after if clock_calls>=7 else NOW
        fixture={("nfl","20261108"):[event()]}
        source=ingest_schedule("2026-11-05",fetcher(fixture),
                               now=NOW,lookahead_days=7,clock=measured)
        self.assertEqual(source["sources"]["nfl"]["scheduled_events"],0)
        self.assertEqual(source["events"],[])
        self.assertGreater(clock_calls,0)

    def test_individual_response_receipt_is_event_observation_time(self):
        later=NOW+timedelta(seconds=15)
        source=ingest_schedule("2026-11-05",
             fetcher({("nfl","20261108"):[event()]}),
             now=NOW,lookahead_days=7,clock=lambda:later)
        game=source["events"][0]
        q=source["sources"]["nfl"]["lookahead"][-1]
        self.assertEqual(game["observed_at_utc"],later.isoformat())
        self.assertEqual(q["response_observed_at_utc"],later.isoformat())
        self.assertEqual(q["request_started_at_utc"],later.isoformat())
        self.assertNotEqual(game["observed_at_utc"],source["collected_at_utc"])
        rows,report=build(source,[],[],None,END)
        self.assertEqual(audit(source,report,rows)["by_league"]["nfl"]["archived_pregame_games"],1)

    def test_tampered_per_response_receipt_blocks_archive_coverage(self):
        s,rows,r=snapshot({("nfl","20261108"):[event()]})
        s["sources"]["nfl"]["lookahead"][-1]["response_observed_at_utc"]=(
            NOW+timedelta(seconds=30)).isoformat()
        with self.assertRaisesRegex(ValueError,"missing_actual_response_receipt"):
            audit(s,r,rows)

    def test_wrong_espn_game_eastern_date_cannot_stand_in_for_queried_day(self):
        s,rows,r=snapshot({("nfl","20261108"):[
            event("401212","2026-11-09T18:00:00Z")]})
        self.assertEqual(rows,[])
        q=s["sources"]["nfl"]["lookahead"][3]
        self.assertEqual(q["wrong_requested_eastern_date_listings"],1)
        self.assertEqual(s["sources"]["nfl"]["scheduled_events"],0)
        self.assertEqual(audit(s,r,rows)["by_league"]["nfl"]["archived_pregame_games"],0)

    def test_regressed_request_clock_blocks_a_date_without_pregame_rows(self):
        state=iter([NOW+timedelta(seconds=15), NOW+timedelta(seconds=10)])
        def measured():
            try:return next(state)
            except StopIteration:return NOW+timedelta(seconds=15)
        s=ingest_schedule("2026-11-05",fetcher(),now=NOW,
                          lookahead_days=7,clock=measured)
        self.assertEqual(s["sources"]["nba"]["lookahead"][0]["status"],"unavailable")
        self.assertEqual(s["sources"]["nba"]["lookahead"][0]["reason"],"ValueError")
        self.assertEqual(s["sources"]["nba"]["scheduled_events"],0)

    def test_cli_output_research_only_and_no_training_artifact(self):
        s,rows,r=snapshot({("nfl","20261108"):[event()]})
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"espn_schedule_capture.json").write_text(json.dumps(s))
            (root/"prospective_report.json").write_text(json.dumps(r))
            (root/"prospective_event_evidence.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in rows))
            self.assertEqual(main(["--capture-dir",tmp]),0)
            report=json.loads((root/"eight_sport_schedule_coverage.json").read_text())
            self.assertEqual(report["totals"]["pregame_events_archived"],1)
            self.assertEqual(report["certified_champion_001_predictions"],0)
            self.assertFalse((root/"historical_results.jsonl").exists())


if __name__=="__main__":
    unittest.main()
