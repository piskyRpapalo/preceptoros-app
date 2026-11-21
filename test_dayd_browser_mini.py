"""Day D MINI-LOCAL browser integration contract (pure, CI-safe).

A real Chromium E2E is retained at tests/dayd_browser_mini.browser.cjs.
This suite does NOT assume Playwright or a personal model on GitHub runners.
"""
from __future__ import annotations
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class MiniBrowserDoor(unittest.TestCase):
    def test_shared_parser_reuses_android_source_and_has_no_authority(self):
        parser = (ROOT / "mvp-android/offline_mini.js").read_text(encoding="utf8")
        gate = (ROOT / "interface/browser_mini_gate.js").read_text(encoding="utf8")
        server = (ROOT / "bin/preceptoros-pwa").read_text(encoding="utf8")
        self.assertIn('"/offline_mini.js": (os.path.join(AQUI, "mvp-android/offline_mini.js")',server)
        self.assertIn('"/browser_mini_gate.js": ("browser_mini_gate.js",',server)
        self.assertIn('PreceptorMiniBrowserEnabled !== true', parser)
        self.assertIn("root.PreceptorProfile === 'private_rack'", parser)
        self.assertIn("root.PreceptorMiniBrowserEnabled = false", gate)
        self.assertIn("root.PreceptorAndroidMiniModel", gate)
        self.assertIn("deterministic routing only, not a model", gate)
        self.assertNotIn("fetch(", gate)
        self.assertNotIn("XMLHttpRequest", gate)
        self.assertNotIn("localStorage", gate)
        self.assertNotIn("navigator.sendBeacon", gate)

    def test_five_zones_and_accessible_explicit_toggle(self):
        html=(ROOT / "interface/app.html").read_text(encoding="utf8")
        css=(ROOT / "interface/app.css").read_text(encoding="utf8")
        sw=(ROOT / "interface/sw.js").read_text(encoding="utf8")
        self.assertIn('id="mini-local-toggle" aria-pressed="false"',html)
        self.assertIn('id="mini-local-mode-status" role="status" aria-live="polite"',html)
        self.assertIn('data-state="NO_DATA" data-acho="NO_DATA"',html)
        self.assertIn('src="/offline_mini.js?v=1"',html)
        self.assertIn('src="/browser_mini_gate.js?v=3"',html)
        self.assertIn('const Cache = "preceptoros-armazon-v242"',sw)
        for asset in ("/offline_mini.js?v=1","/browser_mini_gate.js?v=3"):
            self.assertIn('"'+asset+'"',sw)
        for panel in ("conversacion","cuaderno","lab","ajustes","modelos"):
            self.assertIn('id="tab-'+panel+'"',html)
        self.assertNotIn('id="tab-documentos"',html)
        self.assertIn('min-height: 44px',css)
        self.assertIn('mini-mode-switch',css)
        self.assertIn(':focus-visible',css)

    def test_android_deterministic_router_remains_green(self):
        proc=subprocess.run(
            ["node", "--test", "tests/android_offline_mini_cases.cjs"],
            cwd=ROOT,capture_output=True,text=True,timeout=20,
        )
        self.assertEqual(proc.returncode,0,proc.stderr[-1600:]+proc.stdout[-1600:])
        self.assertRegex(proc.stdout, r"(?m)(?:ℹ|#) pass 7")

if __name__=="__main__":
    unittest.main()
