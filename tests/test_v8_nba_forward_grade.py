"""Fixture tests for first-receipt authentic forward NBA research grading."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nba_forward_research import VERSION
from v8_nba_forward_grade import grade, load_archived_forecasts, save

NY = ZoneInfo("America/New_York")
FORECAST = datetime(2026,11,9,20,tzinfo=timezone.utc)
START = datetime(2026,11,10,1,tzinfo=timezone.utc)
AFTER = datetime(2026,11,12,12,tzinfo=timezone.utc)
RUN = 42699985963


def original():
    obj={
        "events":[{
            "id":"40123456", "date":START.isoformat(),
            "season":{"type":2},
            "status":{"type":{"state":"pre","completed":False}},
            "competitions":[{"competitors":[
                {"homeAway":"home","team":{"id":"161","displayName":"Home Five"}},
                {"homeAway":"away","team":{"id":"162","displayName":"Away Five"}},
            ]}],
        }]
    }
    raw=json.dumps(obj,sort_keys=True,separators=(",",":")).encode("utf-8")
    return raw


def write_run(folder, run_id=RUN, *, p=.6, recorded=FORECAST, completed=None):
    start = START
    day = start.astimezone(NY).date()
    base=Path(folder)/str(run_id)
    work=base/"nba_forward"
    work.mkdir(parents=True)
    raw=original()
    when=recorded.isoformat()
    observed=(recorded-timedelta(minutes=1)).isoformat()
    event={
        "record_type":"v8_genuine_forward_clocktime_NBA_Elo_research_only",
        "league":"nba","espn_event_id":"40123456",
        "home_team":"Home Five","away_team":"Away Five",
        "home_team_espn_id":"161", "away_team_espn_id":"162",
        "start_utc":start.isoformat(),"forecast_recorded_utc":when,
        "schedule_original_received_at_utc":observed,
        "schedule_source_url":scoreboard_url("nba",day),
        "schedule_original_sha256_local_receipt":hashlib.sha256(raw).hexdigest(),
        "model_version":VERSION,
        "model_probability_home_win_research_only":p,
        "estimated_away_win_probability_research_only":1-p,
        "champion_001_modified":False,"certified_prediction":False,
        "champion_001_shadow_certified":False,
        "qualifies_for_original_champion_shadow_quota":False,
        "forecast_reconstructed_after_game":False,
        "bet_ready":False,"verified_positive_ev":False,
        "stake_usd":0,"outcome":None,"outcome_observed_at_utc":None,
    }
    def write(where, x):
        where.write_text(json.dumps(x,sort_keys=True)+"\n",encoding="utf-8")
    write(base/"github_run.json",{
        "id":run_id,"head_branch":"main","status":"completed",
        "conclusion":"success","event":"push",
        "created_at":(FORECAST-timedelta(minutes=3)).isoformat(),
        "updated_at":(completed or recorded+timedelta(minutes=3)).isoformat(),
    })
    write(base/"ONE_COMMAND_REPORT.json",{
        "command":"run_nba_forward","champion_001_modified":False,
        "certified_positive_ev_bets":0,
    })
    write(work/"NBA_FORWARD_RESEARCH_STATUS.json",{
        "stage":"v8_elo_genuine_forward_clocktime_research_only",
        "captured_at_utc":when,
        "champion_001_modified":False,
        "original_champion_001_predictions_certified":0,
        "independently_certified_v8_predictions":0,
        "forward_research_probabilities_recorded_before_tipoff":1,
        "v8_research_forward_predictions":1,
    })
    write(work/"NBA_FORWARD_FORECASTS.jsonl",event)
    (work/f"nba_original_future_schedule_{day:%Y%m%d}.json").write_bytes(raw)
    return base,event



def write_nested_phone_nba_run(folder, run_id=RUN+22, *, p=.6,
                               recorded=FORECAST):
    """Same authentic forward bytes, under Run NBA's real artifact layout."""
    base, original_forecast = write_run(folder, run_id, p=p, recorded=recorded)
    nested = base / "components" / "nba" / "nba_best_bets"
    nested.mkdir(parents=True)
    (base / "nba_forward").rename(nested / "nba_forward")
    component = base / "components" / "nba"
    component_report = json.loads((base / "ONE_COMMAND_REPORT.json").read_text())
    component_report["command"] = "run_nba_best_bets"
    (component / "ONE_COMMAND_REPORT.json").write_text(
        json.dumps(component_report) + "\n")
    (base / "ONE_COMMAND_REPORT.json").write_text(json.dumps({
        "report_type": "FREDDYS_PICKS_V8_ONE_COMMAND_ALL_IN_ONE_V1",
        "user_command": "run_nba", "champion_001_modified": False,
        "money_wagered_usd": 0, "certified_positive_ev_bets": 0,
    }) + "\n")
    return base, original_forecast


def final_game(*, published_at=AFTER, actual_start=START, homeid="161"):
    ev={
        "id":"40123456","date":actual_start.isoformat(),
        "season":{"type":2},"status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":homeid,"displayName":"Home Five"},"score":"110"},
            {"homeAway":"away","team":{"id":"162","displayName":"Away Five"},"score":"100"},
        ]}],
    }
    day=actual_start.astimezone(NY).date()
    return normalize_game(ev,"nba",scoreboard_url("nba",day),published_at)


def results_collector(leagues, days, end_date):
    assert leagues==("nba",) and days==1 and end_date==START.astimezone(NY).date()
    records=[final_game()]
    return records, {"leagues":["nba"],"by_league":{"nba":{
        "days_attempted":1,"days_ok":1,"days_failed":0,
        "completed_games":1,
    }},"champion_001_modified":False,"total_completed_results":len(records)}


class ForwardGradingTests(unittest.TestCase):
    def test_phone_run_nba_nested_forward_is_legitimate_original_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            base, forecast = write_nested_phone_nba_run(folder)
            predictions, receipt = load_archived_forecasts(folder)
            self.assertEqual(len(predictions), 1)
            self.assertEqual(receipt["source_github_run_ids"], [RUN+22])
            self.assertEqual(predictions[0]["model_probability_home_win_research_only"], .6)
            self.assertEqual(predictions[0]["espn_event_id"], forecast["espn_event_id"])
            result, ledger = grade(predictions, AFTER, collector=results_collector)
            self.assertEqual(result["real_forward_research_forecasts_graded"], 1)
            self.assertIsNone(result["probability_research_Brier"])
            self.assertFalse(ledger[0]["certified_prediction"])

    def test_phone_run_nba_does_not_accept_fake_wrapper_or_unsettled_forecast(self):
        with tempfile.TemporaryDirectory() as folder:
            base, forecast = write_nested_phone_nba_run(folder)
            envelope=base/"ONE_COMMAND_REPORT.json"
            data=json.loads(envelope.read_text())
            data["certified_positive_ev_bets"]=1
            envelope.write_text(json.dumps(data))
            predictions, receipt=load_archived_forecasts(folder)
            self.assertEqual(predictions, [])
            self.assertIn("excluded_untrusted_run_ValueError",
                          receipt["excluded_archive_or_duplicate_reasons"])
            data["certified_positive_ev_bets"]=0
            envelope.write_text(json.dumps(data))
            path=(base/"components/nba/nba_best_bets/nba_forward/"
                  "NBA_FORWARD_FORECASTS.jsonl")
            altered=dict(forecast, outcome=1)
            path.write_text(json.dumps(altered)+"\n")
            predictions, receipt=load_archived_forecasts(folder)
            self.assertEqual(predictions, [])

    def test_original_archive_and_github_time_verified_with_untouched_probability(self):
        with tempfile.TemporaryDirectory() as temp:
            base, first=write_run(temp)
            forecasts, receipt=load_archived_forecasts(temp)
            self.assertEqual(len(forecasts),1)
            self.assertEqual(receipt["source_github_run_ids"],[RUN])
            self.assertEqual(forecasts[0]["model_probability_home_win_research_only"],.6)
            result,ledger=grade(forecasts,AFTER,collector=results_collector,receipt=receipt)
            self.assertEqual(result["real_forward_research_forecasts_graded"],1)
            # One genuine graded outcome is useful per-event evidence, but
            # too small to report an aggregate skill score.
            self.assertIsNone(result["probability_research_Brier"])
            self.assertIsNone(result["probability_research_log_loss"])
            self.assertIsNone(result["classification_accuracy_provisional"])
            self.assertIsNone(result["neutral_50_50_Brier_not_sportsbook"])
            self.assertEqual(result["minimum_mature_grades_for_aggregate_skill"],50)
            self.assertFalse(result["meets_minimum_50_forward_graded_games"])
            self.assertEqual(ledger[0]["graded_published_result"]["home_won_from_ESPN_published_final"],1)
            self.assertFalse(ledger[0]["original_forecast_modified"])
            self.assertFalse(result["bet_ready"])
            self.assertEqual(result["original_champion_001_shadows_certified"],0)
            self.assertEqual(result["certified_positive_ev_bets"],0)
            dest=Path(temp)/"reports"
            save(result,ledger,dest)
            self.assertTrue((dest/"NBA_FORWARD_GRADING_REPORT.json").is_file())

    def test_live_fetch_allows_authenticated_receipt_after_scan_start(self):
        # Regression: the fetch receipt occurs after the grading scan begins.
        # Do not confuse legitimate collection latency with future leakage.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts, _ = load_archived_forecasts(temp)

            def just_fetched(*args):
                records, summary = results_collector(*args)
                records[0]["retrieved_at_utc"] = (
                    AFTER + timedelta(seconds=1)).isoformat()
                return records, summary

            with patch("v8_nba_forward_grade.datetime") as clock:
                clock.now.side_effect = [
                    AFTER, AFTER + timedelta(seconds=2)]
                summary, ledger = grade(forecasts, collector=just_fetched)
            self.assertEqual(summary["real_forward_research_forecasts_graded"], 1)
            self.assertEqual(ledger[0]["evaluation_status"],
                             "GRADED_ESPN_PUBLISHED_FINAL_RESEARCH_ONLY")
            self.assertEqual(summary["certified_positive_ev_bets"], 0)

    def test_live_fetch_rejects_unobserved_future_result_receipt(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts, _ = load_archived_forecasts(temp)

            def future_receipt(*args):
                records, summary = results_collector(*args)
                records[0]["retrieved_at_utc"] = (
                    AFTER + timedelta(seconds=3)).isoformat()
                return records, summary

            with patch("v8_nba_forward_grade.datetime") as clock:
                clock.now.side_effect = [
                    AFTER, AFTER + timedelta(seconds=2)]
                with self.assertRaisesRegex(
                        ValueError, "unsupported_published_outcome_source"):
                    grade(forecasts, collector=future_receipt)

    def test_historical_as_of_prohibits_later_source_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts, _ = load_archived_forecasts(temp)

            def later_receipt(*args):
                records, summary = results_collector(*args)
                records[0]["retrieved_at_utc"] = (
                    AFTER + timedelta(seconds=1)).isoformat()
                return records, summary

            with self.assertRaisesRegex(
                    ValueError, "unsupported_published_outcome_source"):
                grade(forecasts, as_of=AFTER, collector=later_receipt)

    def test_before_48h_no_final_requested_or_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts,_=load_archived_forecasts(temp)
            def forbidden(*args):
                raise AssertionError("must_not_fetch_future_published_final")
            result,ledger=grade(forecasts,FORECAST,collector=forbidden)
            self.assertEqual(result["real_forward_research_forecasts_graded"],0)
            self.assertEqual(result["forecasts_still_pending_or_unmatched"],1)
            self.assertEqual(ledger[0]["evaluation_status"],"PENDING_48H_RESULT_MATURITY")
            self.assertIsNone(result["probability_research_Brier"])

    def test_source_failure_not_counted_as_wrong_prediction(self):
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts,_=load_archived_forecasts(temp)
            def bad_source(*args):
                return [],{"leagues":["nba"],"by_league":{"nba":{
                    "days_attempted":1,"days_ok":0,"days_failed":1}},
                    "champion_001_modified":False,"total_completed_results":0}
            report,rows=grade(forecasts,AFTER,collector=bad_source)
            self.assertEqual(report["real_forward_research_forecasts_graded"],0)
            self.assertEqual(rows[0]["evaluation_status"],"HOLD_SOURCE_DAY_UNAVAILABLE")

    def test_tampered_source_bytes_or_fake_run_time_quarantined(self):
        with tempfile.TemporaryDirectory() as temp:
            base,_=write_run(temp)
            file=next((base/"nba_forward").glob("nba_original_future_schedule_*.json"))
            file.write_text('{"events":[]}')
            forecasts,receipt=load_archived_forecasts(temp)
            self.assertEqual(forecasts,[])
            self.assertEqual(receipt["unique_earliest_forecasts"],0)
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp,completed=START+timedelta(minutes=10))
            forecasts,receipt=load_archived_forecasts(temp)
            self.assertEqual(forecasts,[])
            self.assertIn("excluded_untrusted_run_ValueError",receipt["excluded_archive_or_duplicate_reasons"])

    def test_earliest_forward_record_kept_later_reforecast_cannot_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            write_run(temp,RUN+1,p=.8,recorded=FORECAST+timedelta(minutes=10))
            forecasts,receipt=load_archived_forecasts(temp)
            self.assertEqual(len(forecasts),1)
            self.assertAlmostEqual(forecasts[0]["model_probability_home_win_research_only"],.6)
            self.assertEqual(receipt["excluded_archive_or_duplicate_reasons"]["later_duplicate_forecast_not_regraded"],1)

    def test_changed_team_identity_prohibits_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            write_run(temp)
            forecasts,_=load_archived_forecasts(temp)
            def changed(*args):
                rows,report=results_collector(*args)
                rows[0]["home_team_espn_id"]="wrong"
                return rows,report
            summary,ledger=grade(forecasts,AFTER,collector=changed)
            self.assertEqual(summary["real_forward_research_forecasts_graded"],0)
            self.assertEqual(ledger[0]["evaluation_status"],"HOLD_SCHEDULE_OR_TEAM_IDENTITY_CHANGED")

    def test_empty_archive_reports_no_grade_or_validated_win_rate(self):
        with tempfile.TemporaryDirectory() as temp:
            forecasts,receipt=load_archived_forecasts(temp)
            summary,ledger=grade(forecasts,AFTER,receipt=receipt)
            self.assertEqual(forecasts,[])
            self.assertEqual(ledger,[])
            self.assertEqual(summary["real_forward_research_forecasts_graded"],0)
            self.assertIsNone(summary["classification_accuracy_provisional"])


if __name__=="__main__":
    unittest.main()
