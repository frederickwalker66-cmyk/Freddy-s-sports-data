import unittest
from research.challenger_002_nba_temporal_audit import audit,parse_aware

S={"kind":"nba_scores","date":"2026-11-21"}
O={"kind":"nba_odds","date":"2026-11-21","retrieved_at":"2026-11-21T17:00:00Z"}
def row(start):
    return [{"GameID":1,"GlobalGameID":9,"DateTimeUTC":start}]
ODDS=[{"GameId":1,"GlobalGameId":9,"PregameOdds":[]}]

class TemporalAuditTests(unittest.TestCase):
    def test_aware_pregame_candidate_not_certified(self):
        r=audit(row("2026-11-21T18:00:00Z"),ODDS,S,O)
        self.assertEqual(r["timestamp_before_start_candidates"],1)
        self.assertEqual(r["training_rows_approved"],0)
        self.assertEqual(r["certified_take_count"],0)
    def test_after_start_blocked(self):
        r=audit(row("2026-11-21T16:00:00Z"),ODDS,S,O)
        self.assertEqual(r["blocked_at_or_after_start"],1)
    def test_naive_time_blocked(self):
        r=audit(row("2026-11-21T18:00:00"),ODDS,S,O)
        self.assertEqual(r["blocked_missing_or_ambiguous_time"],1)
    def test_missing_timezone_capture_blocked(self):
        r=audit(row("2026-11-21T18:00:00Z"),ODDS,S,{**O,"retrieved_at":"2026-11-21T17:00:00"})
        self.assertEqual(r["blocked_missing_or_ambiguous_time"],1)
    def test_bad_metadata_blocked(self):
        self.assertEqual(audit([],[],S,{**O,"date":"2026-11-20"})["status"],"BLOCKED_METADATA")
if __name__=="__main__":
    unittest.main()
