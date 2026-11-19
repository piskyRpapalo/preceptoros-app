"""Day D one-building draft: reuse the Companion validator without admission.

No local network, no rack writes. Browser E2E is a separate Chromium receipt.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent

class DayDRoomBuilding(unittest.TestCase):
    def test_node_contract_for_room_draft(self):
        proc = subprocess.run(
            ["node", "--test", "tests/room_building_cases.cjs"],
            cwd=ROOT, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout[-2500:]+proc.stderr[-2500:])
        self.assertRegex(proc.stdout, r"(?m)(?:ℹ|#) pass 8")

    def test_getting_started_first_then_identity_and_building(self):
        html = (ROOT/"interface/app.html").read_text(encoding="utf8")
        pos_tab = html.index('id="panel-ajustes"')
        pos_room = html.index('id="room-building"')
        pos_legacy = html.index('id="ajustes-nodo"')
        self.assertLess(pos_tab,pos_room)
        self.assertLess(html.index('id="mvp-journey-guide"'),pos_legacy)
        self.assertLess(pos_legacy,pos_room)
        self.assertNotIn('id="mvp-journey-guide" open',html)
        self.assertIn('id="node-identity-advanced"', html)
        for marker in (
            'id="room-building-title"', 'id="room-building-form"',
            'id="room-building-name"', 'id="room-building-purpose"',
            'id="room-building-create"', 'id="room-building-download"',
            'id="room-building-clear"', 'id="room-building-status"',
            'aria-live="polite"', 'aria-atomic="true"',
            'data-state="NO_DATA" data-acho="NO_DATA"',
            'NO_DATA(world_publication_not_verified)',
        ):
            self.assertIn(marker,html)
        self.assertIn("Feedback stays on the node owner's hardware.",html)
        self.assertNotIn("Hexelion stays on the founder's private rack.",html)
        self.assertIn("prepare a docs-only Companion HITL PR if you have GitHub",html)
        self.assertNotIn('id="node-deploy"',html)

    def test_single_shared_module_and_pwa_cache(self):
        html=(ROOT/"interface/app.html").read_text(encoding="utf8")
        js=(ROOT/"interface/companion_onboarding.js").read_text(encoding="utf8")
        sw=(ROOT/"interface/sw.js").read_text(encoding="utf8")
        self.assertIn('src="/companion_onboarding.js?v=5"',html)
        self.assertIn('PreceptorCompanionOnboarding.mountBuilding(document);',html)
        self.assertIn('renderDraft({ slug: slug, title: title, summary: purpose, agent:',js)
        self.assertIn('const Cache = "preceptoros-armazon-v232"',sw)
        self.assertIn('"/companion_onboarding.js?v=5"',sw)
        self.assertNotIn('localStorage.',js)
        self.assertNotIn('fetch(',js)
        self.assertEqual(js.count('function renderBuildingDraft('),1)

    def test_touch_and_readability(self):
        css=(ROOT/"interface/app.css").read_text(encoding="utf8")
        self.assertIn('room-building',css)
        self.assertIn('min-height: 44px',css)
        self.assertIn('overflow-wrap: anywhere',css)
        self.assertIn(':focus-visible',css)

if __name__=="__main__":
    unittest.main()
