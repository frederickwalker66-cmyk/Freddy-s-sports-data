import unittest
from research.sharp_edge_certification_gap import assess, REQUIRED_GATES


class CertificationGapTests(unittest.TestCase):
    def test_empty_report_is_explicitly_blocked(self):
        result = assess({})
        self.assertEqual(result["certified_takes_in_this_run"], 0)
        self.assertEqual(len(result["required_gates"]), len(REQUIRED_GATES))

    def test_research_rows_cannot_self_certify(self):
        result = assess({"universal_sharp_edge_board": {
            "rows": [{"decision": "HOLD"}, {"decision": "PASS"}]},
            "sharp_edge_source_readiness": {"archive_market_receipts_authenticated": 0}})
        self.assertEqual(result["displayed_decisions"], {"TAKE": 0, "HOLD": 1, "PASS": 1})
        self.assertTrue(result["no_self_attested_take"])

    def test_reject_non_list_rows(self):
        with self.assertRaises(TypeError):
            assess({"universal_sharp_edge_board": {"rows": "invalid"}})
