"""Read-only NFL and NHL phone board refuses fabricated counts or fake EV."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_nfl_nhl_board_view import read_boards


def board(sport,n=14):
    return {
        "version":"v8-NFL-NHL-durable-forward-v1",
        "sport":sport,"status":"HOLD_Fewer_than_50_research_forward_grades_per_model",
        "champion_001_modified":False,"bet_ready":False,
        "certified_champion_001_shadows":0,"certified_positive_ev_bets":0,
        "verified_sportsbook_checkout_quotes":0,
        "ESPN_final_is_independently_verified_bookmaker_settlement":False,
        "original_saved_forecasts":n,"pending_48h":n,
        "graded_research_games":0,"original_game_identity_conflicts_quarantined":0,
        "unmatched_or_source_missing":0,"published_NFL_ties_excluded":0,
        "research_ranked_models_after_50":[],
    }


class PhoneSportBoardsTests(unittest.TestCase):
    def test_no_durable_branch_means_unknown_not_fake_zero(self):
        r=read_boards({})
        for lg in ("nfl","nhl"):
            self.assertEqual(r["by_sport"][lg]["status"],"NOT_YET_PERSISTED")
            self.assertIsNone(r["by_sport"][lg]["original_saved_forecasts"])
        self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_actual_pending_sports_show_honest_source_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            files={}
            for lg,count in (("nfl",14),("nhl",10)):
                p=Path(folder)/(lg+".json")
                p.write_text(json.dumps(board(lg,count)))
                files[lg]=p
            view=read_boards(files)
            self.assertEqual(view["by_sport"]["nfl"]["original_saved_forecasts"],14)
            self.assertEqual(view["by_sport"]["nhl"]["pending_48h"],10)
            self.assertEqual(view["by_sport"]["nfl"]["research_ranked_models_after_50"],[])
            self.assertFalse(view["bet_ready"])

    def test_tampered_research_certification_or_count_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"sport.json"
            x=board("nfl")
            x["certified_positive_ev_bets"]=1
            p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"untrusted_or_promoted"):
                read_boards({"nfl":p})
            x=board("nfl")
            x["graded_research_games"]=2
            p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"do_not_reconcile"):
                read_boards({"nfl":p})


if __name__=="__main__":
    unittest.main()
