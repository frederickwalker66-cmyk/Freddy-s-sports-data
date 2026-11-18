"""Public V9 boardroom safety contract: no public paid voice calls or fabricated votes."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "boardroom.html"


class PageScanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.persons=[]
        self.sources=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if "data-person" in a: self.persons.append(a["data-person"])
        if tag=="script" and "src" in a:self.sources.append(a["src"])


class BoardroomPublicPrototypeTests(unittest.TestCase):
    def test_roster_includes_all_six_and_no_duplicate_nodes(self):
        raw=HTML.read_text(encoding="utf-8")
        scan=PageScanner()
        scan.feed(raw)
        self.assertEqual(len(scan.ids),len(set(scan.ids)))
        self.assertEqual(scan.persons,["bella","david","cassidy","roger","sarah","adam"])
        for name in ("Bella","David","Cassidy","Roger","Sarah","Adam Stone"):
            self.assertIn(name,raw)
        self.assertIn("Freddy voice remains reserved for the CEO",raw)
        for person in ('bella','david','cassidy','roger','sarah','adam-stone'):
            self.assertIn('assets/v9-'+person+'.jpg',raw)
            self.assertTrue((ROOT/'docs'/'assets'/('v9-'+person+'.jpg')).exists())
        self.assertIn('picture.onload',raw)
        self.assertNotIn('portrait pending',raw)
        self.assertEqual(raw.count('Static fictional portrait of '),6)


    def test_voice_call_security_not_open_to_public_page(self):
        raw=HTML.read_text(encoding="utf-8")
        self.assertNotIn("agent_8301",raw)
        self.assertNotIn("agent_6601",raw)
        self.assertNotIn("<elevenlabs-convai",raw)
        self.assertNotIn("convai-widget-embed",raw)
        self.assertNotIn("xi-api-key",raw)
        self.assertNotIn("GH_TOKEN",raw)
        self.assertNotIn("HeyGen",raw.replace("No HeyGen used.",""))
        self.assertIn("https://elevenlabs.io/app/agents",raw)
        self.assertIn("voice employees",raw.lower())

    def test_exact_pick_voting_fail_closed(self):
        raw=HTML.read_text(encoding="utf-8")
        self.assertIn("6/6",raw)
        self.assertIn("that one reviewed pick only",raw)
        self.assertIn("HOLD",raw)
        self.assertIn("0/6 authenticated employee votes",raw)
        self.assertIn("No wagers are placed",raw)
        self.assertIn("does not send a bet",raw)
        self.assertIn("replaceChildren()",raw)
        self.assertNotIn("localStorage",raw)
        self.assertNotIn("sessionStorage",raw)
        self.assertNotIn("innerHTML",raw)

    def test_source_checks_read_only_public_github_and_no_fake_live_odds(self):
        raw=HTML.read_text(encoding="utf-8")
        self.assertIn("https://api.github.com/repos/",raw)
        self.assertIn("v9-pregame-meeting.yml",raw)
        self.assertIn("v8-source-cadence-watchdog.yml",raw)
        self.assertIn("challenger-eight-sport-source-preflight.yml",raw)
        self.assertNotIn("method:\"POST\"",raw)
        self.assertNotIn("Authorization",raw)
        self.assertIn("does not certify any bets",raw)
        self.assertIn("GitHub scheduling is best-effort",raw)


if __name__=="__main__":
    unittest.main()
