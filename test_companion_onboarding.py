"""Companion first-run: test the ACTUAL JS and the existing APP static route.

No Python reimplementation of JavaScript rules; no network or real HOME.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class CompanionOnboarding(unittest.TestCase):
    def test_real_javascript_adversarial_cases(self):
        proc = subprocess.run(
            ["node", "--test", str(ROOT / "tests/companion_onboarding_cases.cjs")],
            cwd=ROOT,
            capture_output=True, text=True,
            env={**os.environ, "NODE_DISABLE_COLORS": "1"},
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr)[-2800:])
        match = re.search(r"(?:#|ℹ)\s*pass\s+(\d+)", proc.stdout)
        self.assertIsNotNone(match, proc.stdout[-700:])
        self.assertGreaterEqual(int(match.group(1)), 13)

    def test_server_static_route_maps_exact_browser_asset(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        path = ROOT / "bin/preceptoros-pwa"
        loader = SourceFileLoader("companion_pwa_asset", str(path))
        spec = spec_from_loader("companion_pwa_asset", loader)
        mod = module_from_spec(spec)
        loader.exec_module(mod)
        route = mod.ESTATICOS.get("/companion_onboarding.js")
        self.assertEqual(route, ("companion_onboarding.js", "application/javascript; charset=utf-8"))
        self.assertTrue((ROOT / "interface" / route[0]).is_file())

    def test_ui_shell_offline_contract_and_accessibility(self):
        html = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        css = (ROOT / "interface/app.css").read_text(encoding="utf-8")
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf-8")
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        js = (ROOT / "interface/companion_onboarding.js").read_text(encoding="utf-8")
        self.assertIn('const Cache = "preceptoros-armazon-v236"', sw)
        self.assertIn('"/companion_onboarding.js?v=5"', sw)
        self.assertIn('src="/companion_onboarding.js?v=5"', html)
        self.assertIn('"interface/companion_onboarding.js"', version)
        self.assertIn('id="companion-status" role="status" aria-live="polite" aria-atomic="true"', html)
        self.assertIn('data-state="DRAFT_ONLY" data-acho="DRAFT_ONLY"', html)
        self.assertIn('id="companion-slug" name="slug" required maxlength="24"', html)
        self.assertIn('id="companion-draft" class="companion-draft"', html)
        self.assertIn('white-space: pre-wrap', css)
        self.assertIn('overflow-wrap: anywhere', css)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('https://github.com/piskyRpapalo/preceptoros-companion', html)
        self.assertIn('NO_DATA(world_publication_not_verified)', html)
        self.assertIn("form.addEventListener('submit'", js)
        self.assertNotIn("localStorage.", js)
        self.assertNotIn("fetch(", js)


if __name__ == "__main__":
    unittest.main()
