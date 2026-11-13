"""Offline proof that the NBA one-command slate is complete, bounded and HOLD-only."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from v8_nba_slate_best_bets import (assemble, load_sgo_slate_rows,
                                     pair_sgo_prices, read_today_schedule, run)
from v8_one_command import execute, selected


NOW = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)
DAY = NOW.astimezone(ZoneInfo("America/New_York")).date()
START = datetime(2026, 11, 13, 22, 0, tzinfo=timezone.utc)
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261113&limit=500"


def event(event_id, home, away, state="pre", start=START):
    return {
        "id": str(event_id),
        "season": {"type": 2},
        "status": {"type": {"state": state}},
        "date": start.isoformat(),
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": str(event_id) + "1", "displayName": home}},
            {"homeAway": "away", "team": {"id": str(event_id) + "2", "displayName": away}},
        ]}],
    }


def schedule():
    items = [event(101, "Indiana Pacers", "New York Knicks"),
             event(102, "Orlando Magic", "Milwaukee Bucks",
                   state="in", start=START - timedelta(minutes=25)),
             event(103, "Miami Heat", "Cleveland Cavaliers",
                   state="post", start=START - timedelta(minutes=70)),
             event(104, "Minnesota Timberwolves", "Chicago Bulls",
                   start=START + timedelta(days=1))]
    raw = json.dumps({"events": items}).encode()
    return read_today_schedule(raw, DAY, received_at=NOW, url=SOURCE)


def forecast():
    return {"espn_event_id": "101", "league": "nba",
            "home_team": "Indiana Pacers", "away_team": "New York Knicks",
            "start_utc": START.isoformat(),
            "forecast_recorded_utc": NOW.isoformat(),
            "certified_prediction": False,
            "model_probability_independently_calibrated": False,
            "model_probability_home_win_research_only": .48,
            "estimated_away_win_probability_research_only": .52,
            "model_version": "fixed_elo_research_not_champion"}


def odds(market, side, price, line=None, player=None, player_id=None,
         quote=None, selection=None):
    received = NOW - timedelta(minutes=1)
    raw_quote = quote or NOW - timedelta(minutes=3)
    if selection is None:
        if market in ("moneyline", "point_spread"):
            selection = "Indiana Pacers" if side == "home" else "New York Knicks"
        elif market == "total_points":
            selection = side.title()
        else:
            selection = (player or "Unknown") + " " + side.title()
    return {
        "source": "sportsgameodds_v2",
        "record_type": "pregame_odds_observation",
        "league": "nba", "sportsbook": "draftkings",
        "certified_prediction": False, "model_probability": None,
        "is_main_line": False, "cross_provider_identity_verified": False,
        "draftkings_price_independently_verified": False,
        "home_team": "Indiana Pacers", "away_team": "New York Knicks",
        "event_id": "sgo:2026-11-13-NYIND",
        "market_type": market, "selection_type": side,
        "selection": selection,
        "player_id": player_id, "player_name": player,
        "line": line, "odds_american": price,
        "event_start_time": START.isoformat(),
        "timestamp": raw_quote.isoformat(),
        "recorded_at": received.isoformat(),
    }


class FullNBACommandTests(unittest.TestCase):
    def test_schedule_includes_full_even_live_and_final_without_yesterday(self):
        games = schedule()
        self.assertEqual(len(games), 3)
        self.assertEqual([x["source_event_state"] for x in games],
                         ["post", "in", "pre"])
        self.assertEqual({x["away_team"] for x in games},
                         {"New York Knicks", "Milwaukee Bucks", "Cleveland Cavaliers"})

    def test_quote_math_all_categories_but_no_invented_calibration(self):
        rows = [
            odds("moneyline", "home", +120), odds("moneyline", "away", -140),
            odds("point_spread", "home", -110, +3.5),
            odds("point_spread", "away", -110, -3.5),
            odds("total_points", "over", -114, 221.5),
            odds("total_points", "under", -108, 221.5),
            odds("player_points", "over", -105, 24.5, "Star Guard", "p101"),
            odds("player_points", "under", -115, 24.5, "Star Guard", "p101"),
            odds("total_points", "over", -110, 220.5),
            # A team total must NEVER be labeled as a full-game total.
            odds("total_points", "over", -110, 108.5, selection="Home Over"),
            odds("total_points", "under", -110, 108.5, selection="Home Under"),
            odds("player_rebounds", "over", -105, 8.5, "Other", "p102"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sportsgameodds_dk_original.jsonl"
            p.write_text("\n".join(json.dumps(x) for x in rows))
            indexed, counters = load_sgo_slate_rows(tmp, schedule(), now=NOW)
            self.assertEqual(counters["matched_rows"], 12)
            self.assertEqual(len(indexed), 12)
            self.assertTrue(all(not r["actual_sportsbook_checkout_verified"] for r in indexed))
            self.assertTrue(all(not r["primary_or_alt_line_independently_verified"] for r in indexed))
            pairs = pair_sgo_prices(indexed, [forecast()])
        self.assertEqual(len(pairs), 5)
        self.assertEqual(sum(x["market_scope"] == "home_team" for x in pairs), 1)
        self.assertEqual(sum(x["market_scope"] == "full_game" and x["market"] == "total_points" for x in pairs), 1)
        self.assertEqual({x["market"] for x in pairs},
                         {"moneyline", "point_spread", "total_points", "player_points"})
        ml = next(x for x in pairs if x["market"] == "moneyline")
        self.assertEqual(ml["model_home_win_probability_research_percent"], 48.)
        self.assertEqual(ml["sides"][0]["selection_side"], "home")
        self.assertGreater(ml["sides"][0]["no_vig_market_percent"], 40)
        self.assertIsNone(ml["certified_sharp_edge_pp"])
        self.assertIsNone(ml["certified_expected_roi_percent"])
        player_pair = next(x for x in pairs if x["market"] == "player_points")
        self.assertIs(player_pair["player_team_assignment_verified"], False)
        self.assertFalse(ml["source_pair_quote_fresh"])

    def test_never_join_different_providers_players_or_unpaired_legs(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [odds("player_points", "over", -110, 22.5, "Player A", "p1"),
                    odds("player_points", "under", -110, 22.5, "Player A", "p2"),
                    odds("moneyline", "home", -105)]
            # An apparent other side from a different SGO event must not pair.
            alt = odds("moneyline", "away", -105)
            alt["event_id"] = "sgo:DIFFERENT"
            rows.append(alt)
            p = Path(tmp) / "sportsgameodds_dk_test.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in rows))
            actual, _ = load_sgo_slate_rows(tmp, schedule(), now=NOW)
            self.assertEqual(pair_sgo_prices(actual, [forecast()]), [])

    def test_execute_nba_all_best_bets_is_one_unified_safe_command(self):
        self.assertEqual(selected("run_nba_best_bets"), ("nba",))
        slate = assemble(schedule(), [forecast()], [], {}, now=NOW,
                         calibration={"status": "NOT_CERTIFIED"})
        slate["source_coverage_complete_for_all_nba_games"] = True
        slate["nba_forward_research_status"] = {"history_games_retrieved": 151}
        runner_called = []
        def runner(path, *, days, now, sgo_archive_dir, calibration):
            runner_called.append((days, now))
            return slate, [forecast()]
        with tempfile.TemporaryDirectory() as tmp:
            r = execute("run_nba_best_bets", days=35, now=NOW, output_dir=tmp,
                        nba_best_bets_runner=runner)
            self.assertEqual(r["nba_slate_best_bets"]["slate_game_count_from_original_source"], 3)
            self.assertEqual(len(r["research_forward_probability_rows"]), 1)
            self.assertEqual(r["certified_positive_ev_bets"], 0)
            self.assertEqual(r["money_wagered_usd"], 0)
            self.assertFalse(r["champion_001_modified"])
            self.assertTrue((Path(tmp)/"PROBABILITY_SHARP_EDGE_DASHBOARD.md").is_file())
            self.assertEqual(runner_called, [(35, NOW)])
            with self.assertRaises(ValueError):
                execute("run_nba_best_bets", days=35, now=NOW,
                        end_date=date(2026, 11, 10), output_dir=tmp,
                        nba_best_bets_runner=runner)

    def test_missing_schedule_is_failure_not_zero_game_claim(self):
        def unavailable(*args, **kwargs):
            raise RuntimeError("fixture_missing_history")
        def no_schedule(*args, **kwargs):
            raise ConnectionError("fixture_missing_schedule")
        with tempfile.TemporaryDirectory() as tmp:
            report, rows = run(tmp, now=NOW, forward_runner=unavailable,
                               schedule_fetcher=no_schedule)
            self.assertEqual(rows, [])
            self.assertFalse(report["source_coverage_complete_for_all_nba_games"])
            self.assertIn("unavailable", report["schedule_capture_status"])
            self.assertEqual(report["best_bets_ranked_by_certified_ev"], [])
            self.assertTrue((Path(tmp)/"NBA_TONIGHTS_FULL_SLATE.json").is_file())

    def test_full_realistic_run_saves_all_archives_not_only_top_props(self):
        def fixture_runner(folder, **kwargs):
            folder.mkdir(parents=True)
            raw = json.dumps({"events": [event(101, "Indiana Pacers", "New York Knicks")]}).encode()
            (folder/"nba_original_future_schedule_20261113.json").write_bytes(raw)
            return [forecast()], {"history_games_retrieved": 150,
                                  "champion_001_modified": False}
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sgo"
            archive.mkdir()
            rows = [
                odds("moneyline", "home", +120), odds("moneyline", "away", -140),
                odds("player_points", "over", -105, 24.5, "Star", "p101"),
                odds("player_points", "under", -115, 24.5, "Star", "p101"),
            ]
            (archive/"sportsgameodds_dk_test.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows))
            output = Path(tmp)/"out"
            report, forecasts = run(output, days=35, now=NOW,
                                    forward_runner=fixture_runner,
                                    sgo_archive_dir=archive,
                                    calibration={"status": "HOLD"})
            self.assertEqual(len(forecasts), 1)
            self.assertEqual(report["slate_game_count_from_original_source"], 1)
            self.assertEqual(report["paired_archive_market_count"], 2)
            self.assertEqual(report["quarantined_unverified_player_prop_pairs"], 1)
            self.assertEqual(report["player_props_with_independently_verified_team_roster_assignment"], 0)
            self.assertNotIn("Star", (output/"NBA_TONIGHTS_FULL_SLATE.md").read_text())
            self.assertEqual(report["games"][0]["model_home_win_research_percent"], 48)
            self.assertEqual(report["best_bets_ranked_by_certified_ev"], [])
            self.assertTrue((output/"NBA_TONIGHTS_FULL_SLATE.md").exists())
            self.assertEqual(len((output/"NBA_ALL_MARKET_QUOTES.jsonl").read_text().splitlines()), 4)


if __name__ == "__main__":
    unittest.main()
