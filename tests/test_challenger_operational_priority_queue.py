"""#85 offline operational release queue tests: real evidence only."""
from copy import deepcopy
import unittest

from challenger_operational_priority_queue import synthesize

IDENTITIES = {
    "stage": "challenger_78_independent_league_identity_research_only",
    "archived_espn_events_reviewed": 2,
    "network_nba_source_failures_by_url": {
        "https://cdn.nba.com/official.json": "HTTPError",
    },
    "certified_positive_ev_bets": 0,
    "champion_001_modified": False,
}
RELEASE = {
    "stage": "challenger_82_full_sequence_release_readiness",
    "archived_pregame_games": 2,
    "league_operated_identity_matches_research_only": {
        "nba": 0, "nfl": 0, "mlb": 0, "nhl": 1,
        "ncaaf": 0, "ncaab": 0, "mls": 0, "uefa_champions_league": 0,
    },
    "independently_verified_bookmaker_prices": 0,
    "certified_positive_ev_bets": 0,
    "champion_001_modified": False,
}
NFL = {
    "stage": "challenger_83_nflverse_third_party_pregame_identity_research_only",
    "nfl_games_reviewed": 1,
    "independent_third_party_pregame_identity_matches_research_only": 1,
    "official_nfl_operated_identity_matches_verified": 0,
    "qualified_training_games": 0,
    "certified_positive_ev_bets": 0,
    "champion_001_modified": False,
}
ROLLING = {
    "stage": "challenger_84_rolling_original_pregame_research_ledger",
    "distinct_future_espn_game_ids": 2,
    "observations_checked": 4,
    "capture_runs_checked": 2,
    "qualified_training_games": 0,
    "source_revision_status": {"kickoff_revision_observed_research_quarantined": 1},
    "certified_positive_ev_bets": 0,
    "champion_001_modified": False,
}


class OperationalPriorityQueueTests(unittest.TestCase):
    def test_real_research_counts_and_priority_order_without_deployment(self):
        o = synthesize(RELEASE,IDENTITIES,NFL,ROLLING)
        self.assertEqual(o["current_run_future_games"],2)
        self.assertEqual(o["official_league_identity_matches_this_run_research_only"],1)
        self.assertEqual(o["independent_third_party_nfl_matches_this_run_research_only"],1)
        self.assertEqual(o["source_revisions_quarantined"],1)
        self.assertEqual(o["model_release"],"BLOCKED_NOT_CERTIFIED")
        self.assertEqual(o["priorities"][2]["status"],"requires_external_owner_attestation")
        self.assertEqual(o["certified_positive_ev_bets"],0)
        self.assertFalse(o["champion_001_modified"])

    def test_fake_nfl_official_league_identity_rejected(self):
        release=deepcopy(RELEASE)
        release["league_operated_identity_matches_research_only"]["nfl"]=1
        with self.assertRaisesRegex(ValueError,"third_party_nfl_misrepresented"):
            synthesize(release,IDENTITIES,NFL,ROLLING)

    def test_source_count_mismatch_rejected(self):
        release=deepcopy(RELEASE)
        release["archived_pregame_games"]=3
        with self.assertRaisesRegex(ValueError,"unreconciled_operational_counts"):
            synthesize(release,IDENTITIES,NFL,ROLLING)

    def test_bet_or_training_promotion_rejected(self):
        for source in range(4):
            d=list(map(deepcopy, (RELEASE,IDENTITIES,NFL,ROLLING)))
            d[source]["certified_positive_ev_bets"]=1
            with self.subTest(source=source), self.assertRaisesRegex(ValueError,"promoted_unverified"):
                synthesize(*d)
        d=list(map(deepcopy, (RELEASE,IDENTITIES,NFL,ROLLING)))
        d[3]["qualified_training_games"]=1
        with self.assertRaisesRegex(ValueError,"invalid_source_or_training"):
            synthesize(*d)

    def test_missing_source_reports_refused(self):
        broken=deepcopy(NFL)
        broken["stage"]="fabricated_report"
        with self.assertRaisesRegex(ValueError,"wrong_operational_evidence_stages"):
            synthesize(RELEASE,IDENTITIES,broken,ROLLING)


if __name__ == "__main__":
    unittest.main()
