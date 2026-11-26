import unittest
from v8_nfl_live_grading import grade_prop, grade_spread
from v8_nfl_live_ticket import track

class LiveTicketTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(grade_prop(None,53)["status"],"UNKNOWN")
        self.assertEqual(grade_spread(None,0,1.5)["status"],"UNKNOWN")
        self.assertEqual(len(track({})["legs"]),8)
        self.assertTrue(all(r["status"]=="UNKNOWN" for r in track({})["legs"]))
    def test_prop(self):
        self.assertEqual(grade_prop(46,82)["remaining"],36)
        self.assertEqual(grade_prop(82,82)["status"],"TARGET_MET")
        self.assertEqual(grade_prop(81,82,True)["status"],"LOSS")
        self.assertEqual(grade_prop(82,82,True)["status"],"WIN")
    def test_spread(self):
        self.assertEqual(grade_spread(0,0,1.5)["adjusted_margin"],1.5)
        self.assertEqual(grade_spread(20,23,3,True)["status"],"PUSH")
        self.assertEqual(grade_spread(20,24,3,True)["status"],"LOSS")
    def test_integration(self):
        game={"id":"fixture","state":"in","completed":False,"teams":[
            {"team":{"abbreviation":"CHI"},"score":"0"},
            {"team":{"abbreviation":"DET"},"score":"3"}],
            "players":[{"name":"Amon-Ra St. Brown","category":"receiving","stats":{"yards":"46"}}]}
        report=track({"games":[game]})
        self.assertEqual(report["legs"][1]["adjusted_margin"],4.5)
        self.assertEqual(report["legs"][2]["remaining"],36)
        self.assertFalse(report["sportsbook_settlement_verified"])

    def test_provider_fields(self):
        game={"id":"fixture","state":"in","completed":False,"teams":[
            {"team":{"abbreviation":"CHI"},"score":"0"},
            {"team":{"abbreviation":"DET"},"score":"3"}],
            "players":[{"name":"Colston Loveland","category":"receiving","stats":{"receivingYards":"5"}},
                       {"name":"Amon-Ra St. Brown","category":"receiving","stats":{"receivingYards":"46"}}]}
        rows=track({"games":[game]})["legs"]
        self.assertEqual(rows[0]["remaining"],48)
        self.assertEqual(rows[2]["remaining"],36)

    def test_touchdown_evidence(self):
        game={"id":"fixture","state":"in","completed":False,"teams":[
            {"team":{"abbreviation":"KC"},"score":"0"},
            {"team":{"abbreviation":"BUF"},"score":"7"}],
            "players":[{"name":"James Cook","category":"passing","stats":{"passingTouchdowns":"1"}}]}
        self.assertEqual(track({"games":[game]})["legs"][5]["status"],"UNKNOWN")
        game["players"].append({"name":"James Cook","category":"rushing","stats":{"rushingTouchdowns":"1"}})
        self.assertEqual(track({"games":[game]})["legs"][5]["status"],"TARGET_MET")

if __name__=="__main__":
    unittest.main()
