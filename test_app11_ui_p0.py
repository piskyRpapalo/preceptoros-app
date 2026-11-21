"""APP 1.1 P0: installed-version and public Node 0 / crab source contract."""
import re
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent

class App11UIP0(unittest.TestCase):
    def setUp(self):
        self.html = (R/'interface/app.html').read_text()
        self.css = (R/'interface/app.css').read_text()
        self.crab = (R/'interface/talk_crab_canvas.js').read_text()
        self.java = (R/'mvp-android/app/src/main/java/org/preceptoros/mvp/MainActivity.java').read_text()
        self.route = (R/'bin/preceptoros-pwa').read_text()

    def test_native_version_is_buildconfig_only(self):
        self.assertIn('BuildConfig.VERSION_CODE', self.java)
        self.assertIn('BuildConfig.VERSION_NAME', self.java)
        self.assertIn('WebViewCompat.addDocumentStartJavaScript(web, script,', self.java)
        self.assertIn('Collections.singleton(OwnerFrameAccess.ORIGIN)', self.java)
        bridge = (R/'mvp-android/app/src/main/res/raw/local_bridge.js').read_text()
        self.assertIn("window !== window.top || window.location.href !== 'https://preceptoros.mvp.local/app.html'", bridge)
        self.assertIn('version: () => version', bridge)
        self.assertIn('Installed Android application version', self.html)
        self.assertIn('NO_DATA(not_native_android)', self.html)
        self.assertIn('data-cause="native_version_not_checked"', self.html)
        self.assertNotIn('v8 · 0.3.1-mini-recovery</output>', self.html)

    def test_no_duplicate_mobile_app_or_panel(self):
        self.assertEqual(self.html.count('id="panel-modelos"'),1)
        self.assertEqual(self.html.count('id="form-chat"'),1)
        self.assertEqual(self.html.count('id="app-installed-version"'),1)

    def test_public_node_zero_existing_deep_link(self):
        self.assertIn('href="https://preceptoros.org/openworld/?go=hexelion"',self.html)
        self.assertIn('public_link_only',self.html)
        self.assertIn('This is not your private Beelink chat',self.html)
        self.assertIn('rel="noopener noreferrer"',self.html)

    def test_crab_walks_one_direction_and_stays_bounded(self):
        self.assertIn('max-width: 780px;', self.css)
        self.assertRegex(self.css, r'#talk-processing \.talk-processing-crab\s*\{\s*animation: talk-crab-sidestep 9s linear infinite alternate')
        self.assertIn("scene='walking'", self.crab)
        self.assertIn("scene==='walking'", self.crab)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn('animation: none !important',self.css)

    def test_no_status_claim_for_model_or_node(self):
        self.assertIn("render('MEASURED','native_buildconfig')",self.html)
        self.assertIn('NO_DATA(native_version_unavailable)',self.html)
        self.assertIn("root.fetch('/api/estado'",self.html)
        self.assertIn("cacheText='STALE(update_waiting)'",self.html)
        self.assertIn('NO_DATA(cache_hash_not_compared)',self.html)
        self.assertIn('NO_DATA(cache_hash_not_compared)',self.html)
