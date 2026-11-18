"""Offline adversarial tests: a HOLD affects only the reviewed exact pick."""
import unittest
from copy import deepcopy
from v9_unanimous_per_pick import _pick_identity, review, markdown, ROLE_NAMES


def certification():
    return {"final_team_decision":"HOLD","champion_001_modified":False,
            "game_reviews":[{"league":"NBA","event_id":"1234",
                             "game":"Visitors @ Hosts","decision":"HOLD"}]}


def meeting():
    return {"final_team_decision":"HOLD","champion_001_modified":False,
            "meeting_utc":"2026-11-18T13:00:00Z",
            "pregame_games":[{"league":"NBA","event_id":"1234",
                              "game":"Visitors @ Hosts",
                              "start_utc":"2026-11-18T13:40:00Z"}]}


def candidate(market="moneyline",selection="Hosts",line=None,odds=-120):
    return {"league":"NBA","event_id":"1234","market":market,"market_id":"ml-1234",
            "selection":selection,"line":line,"american_odds":odds,
            "sportsbook":"DraftKings","quote_utc":"2026-11-18T12:58:00Z"}


def ballots(c, overrides=None):
    overrides=overrides or {}
    rid,_=_pick_identity(c)
    return [{"review_id":rid,"employee_role":role,
             "choice":overrides.get(role,"APPROVE")} for role in ROLE_NAMES]


class UnanimousPerPickTests(unittest.TestCase):
    def test_no_candidates_is_no_votes_not_fabricated_best_bet(self):
        out=review(certification(),meeting())
        self.assertEqual(out["reviewed_pick_count"],0)
        self.assertEqual(out["unanimous_authenticated_picks"],0)
        self.assertEqual(out["certified_best_bets"],[])
        self.assertEqual(out["meeting_decision"],"HOLD")
        self.assertEqual(len(out["named_specialists"]),6)
        self.assertIn("No individually reviewed picks",markdown(out))

    def test_six_claimed_yes_still_not_real_verified_certification(self):
        c=candidate()
        r=review(certification(),meeting(),[c],ballots(c))
        x=r["pick_reviews"][0]
        self.assertEqual(x["recorded_approvals_unverified"],6)
        self.assertTrue(x["reported_6_of_6"])
        self.assertFalse(x["independently_authenticated_6_of_6"])
        self.assertFalse(x["ceo_final_signoff_authenticated"])
        self.assertIsNone(x["bet_recommendation"])
        self.assertEqual(x["final_release"],"HOLD_NOT_CERTIFIED")
        self.assertEqual(r["wagers_placed"],0)

    def test_reject_is_isolated_by_exact_pick_not_whole_slate(self):
        a=candidate()
        b=candidate(market="spread",selection="Visitors +3.5",line=3.5,odds=-110)
        b["market_id"]="spread-1234"
        aa=ballots(a,{"Risk Manager":"REJECT"})
        bb=ballots(b)
        r=review(certification(),meeting(),[a,b],aa+bb)
        x,y=r["pick_reviews"]
        self.assertEqual(x["vote_review_status"],"REPORTED_VETO_THIS_PICK")
        self.assertEqual(x["recorded_staff_vetoes"],["Risk Manager"])
        self.assertEqual(y["vote_review_status"],"REPORTED_UNANIMOUS_BUT_UNAUTHENTICATED")
        self.assertTrue(y["reported_6_of_6"])
        self.assertEqual(y["recorded_staff_vetoes"],[])
        self.assertEqual(r["certified_best_bets"],[])

    def test_abstention_or_missing_ballot_blocks_only_its_pick(self):
        a=candidate()
        b=candidate(market="spread",selection="Visitors +3.5",line=3.5,odds=-110)
        b["market_id"]="spread-1234"
        r=review(certification(),meeting(),[a,b],
                 ballots(a,{"Sharp Edge Analyst":"ABSTAIN"})+ballots(b))
        self.assertEqual(r["pick_reviews"][0]["recorded_abstentions"],["Sharp Edge Analyst"])
        self.assertEqual(r["pick_reviews"][1]["recorded_approvals_unverified"],6)
        m=review(certification(),meeting(),[a],ballots(a)[:-1])
        self.assertEqual(m["pick_reviews"][0]["vote_review_status"],"PENDING_THIS_PICK_ONLY")
        self.assertEqual(m["pick_reviews"][0]["missing_staff_ballots"],["Audit Engineer"])

    def test_changed_quote_or_line_changes_the_pick_vote_identity(self):
        first=candidate()
        different=deepcopy(first)
        different["american_odds"]=-135
        r=review(certification(),meeting(),[different],ballots(first))
        self.assertEqual(r["pick_reviews"][0]["recorded_approvals_unverified"],0)
        self.assertFalse(r["pick_reviews"][0]["reported_6_of_6"])
        self.assertEqual(len(r["pick_reviews"][0]["missing_staff_ballots"]),6)

    def test_duplicate_ballots_cannot_create_false_6_of_6(self):
        c=candidate()
        votes=ballots(c)
        votes.append(dict(votes[0]))
        r=review(certification(),meeting(),[c],votes)
        self.assertTrue(r["pick_reviews"][0]["conflicting_or_invalid_ballots"])
        self.assertFalse(r["pick_reviews"][0]["reported_6_of_6"])

    def test_unsupported_event_and_unauthenticated_market_rejected(self):
        a=candidate()
        a["event_id"]="9999"
        with self.assertRaises(ValueError):
            review(certification(),meeting(),[a])
        a=candidate()
        a["sportsbook"]="Aggregator DK-labelled"
        with self.assertRaises(ValueError):
            review(certification(),meeting(),[a])

    def test_no_frozen_model_modifications_or_fake_release(self):
        c=certification()
        c["champion_001_modified"]=True
        with self.assertRaises(ValueError):
            review(c,meeting())
        c=certification()
        c["final_team_decision"]="APPROVE"
        with self.assertRaises(ValueError):
            review(c,meeting())

    def test_quote_not_future_or_after_start_and_parlay_rejected(self):
        c=candidate()
        c["quote_utc"]="2026-11-18T13:20:00Z"
        with self.assertRaises(ValueError):
            review(certification(),meeting(),[c])
        c=candidate(market="parlay",selection="Hosts + over 220")
        with self.assertRaises(ValueError):
            review(certification(),meeting(),[c])


if __name__ == "__main__":
    unittest.main()
