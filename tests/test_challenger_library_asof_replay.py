"""Offline tests: source-as-of vs historical hindsight must stay distinct."""
from datetime import datetime,timedelta,timezone
import unittest

from challenger_library_asof_replay import strict_asof_review,hypothetical_elo,review

UTC=timezone.utc
D=datetime(2026,7,1,tzinfo=UTC)


def game(eid,days=0,observed_days=1,lg='nba',home='1',away='2',result='home'):
    start=D+timedelta(days=days)
    return {
        'event_id':str(eid),'start':start,'league':lg,
        'home_id':home,'away_id':away,'result':result,
        'first_score_observed':D+timedelta(days=observed_days),
        'home_score':101 if result=='home' else 99,
        'away_score':99 if result=='home' else 101,
        'season_type':2,
    }


class AsOfReplayTests(unittest.TestCase):
    def test_late_final_scores_not_retrospectively_backfilled(self):
        games=[game(100+i,days=i*5,observed_days=999) for i in range(8)]
        r=strict_asof_review(games)
        self.assertEqual(
            r['nba']['events_with_three_prior_team_results_observed_pregame_research_only'],0)
        self.assertEqual(r['nba']['qualified_training_games'],0)

    def test_three_prior_results_are_structurally_available_not_certified(self):
        games=[game(100+i,days=i*5,observed_days=i*5+1) for i in range(3)]
        games.append(game(104,days=20,observed_days=21))
        r=strict_asof_review(games)
        self.assertEqual(
            r['nba']['events_with_three_prior_team_results_observed_pregame_research_only'],1)
        self.assertEqual(r['nba']['qualified_training_games'],0)

    def test_identical_start_times_never_share_future_outcomes(self):
        a=game(100,days=1,observed_days=2)
        b=game(101,days=1,observed_days=2)
        r=strict_asof_review([a,b])
        self.assertEqual(r['nba']['earlier_result_observations_accessible_by_event_start'],0)

    def test_hypothetical_elo_has_research_metrics_not_model_qualification(self):
        games=[game(1000+i,days=i*3,observed_days=999,
                    result='home' if i%2==0 else 'away') for i in range(115)]
        diagnostic=hypothetical_elo(games)['nba']
        self.assertEqual(diagnostic['status'],'hypothetical_retrospective_diagnostic_only')
        self.assertEqual(diagnostic['evaluation_games'],35)
        self.assertIsInstance(diagnostic['hypothetical_brier'],float)
        self.assertEqual(strict_asof_review(games)['nba']['qualified_training_games'],0)

    def test_soccer_draw_and_insufficient_nfl_not_binary_forecasts(self):
        games=[game(1000+i,days=i*3,observed_days=999,lg='mls') for i in range(90)]
        games += [game(2000+i,days=i*3,observed_days=999,lg='nfl') for i in range(20)]
        diagnostic=hypothetical_elo(games)
        self.assertEqual(diagnostic['mls']['status'],'three_way_soccer_model_required')
        self.assertIsNone(diagnostic['mls']['hypothetical_brier'])
        self.assertEqual(diagnostic['nfl']['status'],'insufficient_retro_eval_games')

    def test_duplicate_event_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate_event_in_strict_asof'):
            strict_asof_review([game(1),game(1,days=8)])

    def test_missing_real_archive_fails_closed_without_synthetic_data(self):
        with self.assertRaises((OSError,ValueError)):
            review('/definitely-unavailable-file.zip')


if __name__=='__main__':
    unittest.main()
