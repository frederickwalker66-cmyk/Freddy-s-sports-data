import unittest
from research.challenger_003_grade_ledger import grade
P={"event_id":"g1","model_id":"Challenger-003","observed_at":"2026-01-01T10:00:00Z","event_start_at":"2026-01-01T12:00:00Z","research_probability":0.6}
R={"event_id":"g1","outcome_observed_at":"2026-01-01T15:00:00Z","outcome":1,"outcome_receipt_sha256":"a"*64}
class LedgerTests(unittest.TestCase):
    def test_pending_not_training(self):
        r=grade([P],[])
        self.assertEqual(r["pending"],["g1"])
        self.assertEqual(r["certified_take_count"],0)
    def test_grade_receipt_not_authentication(self):
        r=grade([P],[R])
        self.assertEqual(r["graded_count"],1)
        self.assertAlmostEqual(r["mean_brier"],0.16)
        self.assertEqual(r["training_admission"],"BLOCKED_UNTIL_PROVIDER_PROVENANCE_VERIFIED")
    def test_missing_receipt_rejected(self):
        r=grade([P],[{**R,"outcome_receipt_sha256":""}])
        self.assertEqual(r["graded_count"],0)
        self.assertEqual(len(r["rejected"]),1)
    def test_postgame_prediction_rejected(self):
        r=grade([{**P,"observed_at":"2026-01-01T13:00:00Z"}],[R])
        self.assertEqual(r["graded_count"],0)
if __name__=="__main__":unittest.main()
