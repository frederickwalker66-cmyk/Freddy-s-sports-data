"""Synthetic NBA box score corroboration: no postgame stats become pregame features."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nba_player_two_source_review import (
    SCHEMA, canonical, choose_games, compare_one, main, run,
)

NOW = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)


def game_crosscheck(eid="401999001", nba_id="0022600001"):
    return {
        "crosscheck_status": "nba_second_source_final_score_agrees_research_only",
        "espn_research_event_id": eid,
        "official_nba_game_id": nba_id,
        "official_nba_start_utc": "2026-11-02T23:00:00Z",
        "source_checked_at_utc": "2026-11-04T12:00:00Z",
        "home_team": "Boston Celtics", "away_team": "New York Knicks",
        "official_nba_score": {"home": 111, "away": 100},
        "espn_published_score": {"home": 111, "away": 100},
        "training_row_qualified": False, "independent_feature_asof_verified": False,
        "independent_source_receipt_authenticated": False,
        "independent_bookmaker_settlement_verified": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


def espn_source(eid="401999001", points=28, home_dnp=False, swap_team=False, name="Jayson Tatum"):
    home_id, away_id = "2", "18"
    competitors = [
        {"homeAway": "home", "team": {"id": home_id,
                                     "displayName": "Boston Celtics"}},
        {"homeAway": "away", "team": {"id": away_id,
                                     "displayName": "New York Knicks"}},
    ]
    if swap_team:
        competitors[0]["team"]["displayName"] = "New York Knicks"
    def player(pid, player_name, dnp, vals):
        return {"athlete": {"id": pid, "displayName": player_name},
                "didNotPlay": dnp, "starter": not dnp, "stats": vals}
    def group(team, athlete):
        return {"team": {"id": team},
                "statistics": [{"names": ["MIN", "PTS", "REB", "AST", "STL", "BLK"],
                                "athletes": [athlete]}]}
    home_vals = [] if home_dnp else ["31:30", str(points), "7", "5", "2", "1"]
    return json.dumps({
        "header": {"id": eid, "competitions": [
            {"id": eid, "status": {"type": {"completed": True}},
             "competitors": competitors}]},
        "boxscore": {"players": [
            group(home_id, player("100", name, home_dnp, home_vals)),
            group(away_id, player("200", "Jalen Brunson", False,
                                  ["32:00", "21", "3", "9", "1", "0"]))]}
    }).encode()


def nba_source(gameid="0022600001", points=28, home_played=True,
               duplicate=False, home_team="Celtics", name="Jayson Tatum"):
    def stats(p, r, a, s, b):
        return {"points": p, "reboundsTotal": r, "assists": a, "steals": s, "blocks": b}
    home = {"personId": 800, "name": name,
            "played": "1" if home_played else "0",
            "statistics": stats(points, 7, 5, 2, 1) if home_played else {}}
    return json.dumps({"game": {
        "gameId": gameid, "gameStatus": 3,
        "homeTeam": {"teamId": 1610612738, "teamCity": "Boston",
                     "teamName": home_team, "score": 111,
                     "players": [home, deepcopy(home)] if duplicate else [home]},
        "awayTeam": {"teamId": 1610612752, "teamCity": "New York",
                     "teamName": "Knicks", "score": 100,
                     "players": [{"personId": 900, "name": "Jalen Brunson",
                                  "played": "1", "statistics": stats(21, 3, 9, 1, 0)}]}}
    }).encode()


class TwoSourceNBAPlayerTests(unittest.TestCase):
    def test_exact_player_game_and_stats_agree_but_not_certified(self):
        e, o, c=espn_source(), nba_source(), game_crosscheck()
        rows=compare_one(c,e,o,NOW)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(x["crosscheck_status"]=="two_source_player_stats_agree_research_only"
                            for x in rows))
        self.assertEqual(rows[0]["nba_official_person_id"],"800")
        self.assertTrue(all(x["stat_agreement"]["points"] for x in rows))
        self.assertEqual(rows[0]["record_type"],SCHEMA)
        self.assertFalse(rows[0]["independent_pregame_player_availability_verified"])
        self.assertFalse(rows[0]["qualified_for_player_prop_training"])
        self.assertIsNone(rows[0]["model_player_prop_probability"])

    def test_postgame_stat_disagreement_is_reported(self):
        rows=compare_one(game_crosscheck(),espn_source(points=29),nba_source(),NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"two_source_player_stats_disagree")
        self.assertFalse(rows[0]["stat_agreement"]["points"])
        self.assertTrue(rows[0]["stat_agreement"]["rebounds"])

    def test_both_dnp_is_separate_from_zero_points_bet(self):
        rows=compare_one(game_crosscheck(),espn_source(home_dnp=True),
                         nba_source(home_played=False),NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"two_source_dnp_agreement_research_only")
        self.assertIsNone(rows[0]["stat_agreement"])
        self.assertFalse(rows[0]["historical_bookmaker_prop_settlement_verified"])

    def test_dnp_vs_played_disagreement_must_not_create_prop_label(self):
        rows=compare_one(game_crosscheck(),espn_source(home_dnp=True),nba_source(),NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"two_source_participation_disagreement")
        self.assertFalse(rows[0]["qualified_for_player_prop_training"])

    def test_exact_name_not_fuzzy_and_accents_normalize(self):
        self.assertEqual(canonical("Luka Dončić"),"luka doncic")
        rows=compare_one(game_crosscheck(),espn_source(name="Jayson S. Tatum"),
                         nba_source(),NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "no_exact_cross_provider_player_name_match")

    def test_official_game_id_mismatch_hard_rejected(self):
        with self.assertRaisesRegex(ValueError,"identity_or_final"):
            compare_one(game_crosscheck(),espn_source(),nba_source(gameid="0022600002"),NOW)

    def test_wrong_game_score_rejected(self):
        o=json.loads(nba_source())
        o["game"]["homeTeam"]["score"]=110
        with self.assertRaisesRegex(ValueError,"score_mismatch"):
            compare_one(game_crosscheck(),espn_source(),json.dumps(o).encode(),NOW)

    def test_reversed_team_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"team_mismatch"):
            compare_one(game_crosscheck(),espn_source(),nba_source(home_team="Knicks"),NOW)

    def test_espn_team_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"mismatched_espn"):
            compare_one(game_crosscheck(),espn_source(swap_team=True),nba_source(),NOW)

    def test_duplicate_player_name_in_same_official_team_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate_or_unknown_official"):
            compare_one(game_crosscheck(),espn_source(),nba_source(duplicate=True),NOW)

    def test_unqualified_game_cannot_trigger_network(self):
        cross=game_crosscheck()
        cross["training_row_qualified"]=True
        calls=[]
        with self.assertRaisesRegex(ValueError,"unqualified_or_invalid"):
            run([cross],fetcher=lambda url:calls.append(url),now=NOW)
        self.assertEqual(calls,[])

    def test_missing_second_source_fails_only_that_game(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if "cdn.nba.com" in url:
                raise OSError("synthetic unavailable")
            return espn_source()
        rows,report,original=run([game_crosscheck()],fetcher=fetch,now=NOW)
        self.assertEqual(len(calls),2)
        self.assertEqual(rows,[])
        self.assertEqual(original,{})
        self.assertEqual(report["statuses"],{"blocked_OSError":1})
        self.assertEqual(report["qualified_prop_training_observations"],0)

    def test_successful_raw_archive_hashes_and_bounded_fetches(self):
        def fake(url):
            return nba_source() if "cdn.nba.com" in url else espn_source()
        rows,report,original=run([game_crosscheck()],fetcher=fake,now=NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(report["original_byte_hashes"]["401999001"]["nba"],
                         hashlib.sha256(nba_source()).hexdigest())
        self.assertEqual(original["401999001"]["espn"],espn_source())
        self.assertEqual(report["positive_ev_player_props"],0)
        self.assertFalse(report["champion_001_modified"])

    def test_duplicate_event_or_official_id_rejected(self):
        p1=game_crosscheck()
        p2=game_crosscheck(eid="401999002")
        with self.assertRaisesRegex(ValueError,"duplicate_or_conflicting"):
            choose_games([p1,p2],NOW)

    def test_cli_empty_game_crosschecks_is_valid_research_only(self):
        with TemporaryDirectory() as temp:
            f=Path(temp)/"crosschecks.jsonl"
            f.write_text("")
            self.assertEqual(main(["--official-crosschecks",str(f),
                                   "--output-dir",str(Path(temp)/"out")]),0)
            files=sorted(p.name for p in (Path(temp)/"out").iterdir())
            self.assertEqual(files,["nba_player_two_source_report.json",
                                    "nba_player_two_source_review.jsonl"])
            report=json.loads((Path(temp)/"out"/files[0]).read_text())
            self.assertEqual(report["games_checked"],0)
            self.assertEqual(report["certified_champion_001_predictions"],0)


if __name__=="__main__":
    unittest.main()
