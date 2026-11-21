import hashlib
import json
import unittest
from research.challenger_002_artifact_pair_audit import audit_pair

class ArtifactPairAuditTests(unittest.TestCase):
    def setUp(self):
        self.scores=b'[]'
        self.odds=b'[]'
        def report(kind,raw):
            return {"kind":kind,"date":"2026-11-21",
                    "status":"AUTHENTICATED_SNAPSHOT_RESEARCH_ONLY",
                    "retrieved_at":"2026-11-21T17:48:00+00:00",
                    "canonical_payload_sha256":hashlib.sha256(raw).hexdigest()}
        self.s=report("nba_scores",self.scores)
        self.o=report("nba_odds",self.odds)
    def test_valid_pair_still_hold(self):
        r=audit_pair(self.scores,self.odds,self.s,self.o)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertTrue(r["digest_integrity_passed"])
        self.assertEqual(r["certified_take_count"],0)
    def test_tampered_odds_blocked(self):
        r=audit_pair(self.scores,b'[1]',self.s,self.o)
        self.assertIn("ODDS_DIGEST_MISMATCH",r["blockers"])
        self.assertFalse(r["digest_integrity_passed"])
    def test_mismatched_dates_blocked(self):
        self.o["date"]="2026-11-20"
        r=audit_pair(self.scores,self.odds,self.s,self.o)
        self.assertIn("DIFFERENT_GAME_DATES",r["blockers"])
if __name__=="__main__":
    unittest.main()
