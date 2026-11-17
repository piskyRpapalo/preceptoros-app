"""Native Companion review URL policy, tested against the ACTUAL JS generator.

Uses JDK only; no network, credentials, Android emulator, or real submissions.
"""
from __future__ import annotations
import os
import pathlib
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "mvp-android/app/src/main/java/org/preceptoros/mvp/CompanionReviewPolicy.java"
PROBE = """import org.preceptoros.mvp.CompanionReviewPolicy;
public final class PolicyProbe {
 public static void main(String[] args) {
  for (String url : args) System.out.println(CompanionReviewPolicy.accepts(url) ? "ALLOW" : "DENY");
 }
}
"""


class AndroidAdmissionPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="companion-review-policy-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.folder = pathlib.Path(cls.tmp.name)
        probe_file = cls.folder / "PolicyProbe.java"
        probe_file.write_text(PROBE, encoding="utf-8")
        result = subprocess.run(
            ["javac", "-d", str(cls.folder), str(SOURCE), str(probe_file)],
            text=True, capture_output=True, timeout=25,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        js = subprocess.run(
            ["node", "-e",
             "process.stdout.write(require('./interface/companion_onboarding.js').architectReviewUrl('node-7'))"],
            cwd=ROOT, text=True, capture_output=True, timeout=10,
        )
        if js.returncode != 0:
            raise RuntimeError(js.stderr)
        cls.real_generated_url = js.stdout

    def allowed(self, url):
        result = subprocess.run(
            ["java", "-cp", str(self.folder), "PolicyProbe", url],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip() == "ALLOW"

    def test_current_js_generator_accepted(self):
        self.assertTrue(self.allowed(self.real_generated_url))

    def test_http_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("https://", "http://", 1)))

    def test_domain_suffix_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("github.com", "github.com.evil.test", 1)))

    def test_url_userinfo_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("https://", "https://attacker@", 1)))

    def test_port_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("github.com/", "github.com:443/", 1)))

    def test_fragment_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url + "#ignored"))

    def test_wrong_repo_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("preceptoros-companion", "preceptoros-app", 1)))

    def test_wrong_route_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("/issues/new?", "/issues/1?", 1)))

    def test_extra_query_param_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url + "&auto_submit=true"))

    def test_body_slug_mismatch_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("Companion%20slug%3A%20node-7", "Companion%20slug%3A%20other", 1)))

    def test_approval_status_tampering_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("pending%20review", "approved", 1)))

    def test_body_secret_injection_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url + "%26token%3Dsecret"))

    def test_invalid_slug_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("node-7", "Node_7", 1)))

    def test_malformed_percent_escape_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url.replace("title=", "title=%ZZ", 1)))

    def test_no_query_rejected(self):
        self.assertFalse(self.allowed("https://github.com/piskyRpapalo/preceptoros-companion/issues/new"))

    def test_overlong_url_rejected(self):
        self.assertFalse(self.allowed(self.real_generated_url + "x" * 5000))

    def test_android_handoff_js_adversarial_cases(self):
        result = subprocess.run(
            ["node", "--test", "tests/android_admission_bridge_cases.cjs"],
            cwd=ROOT, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pass 6", result.stdout)

    def test_android_only_bundle_and_no_network_permission(self):
        main = (ROOT / "mvp-android/app/src/main/java/org/preceptoros/mvp/MainActivity.java").read_text()
        build = (ROOT / "mvp-android/app/build.gradle").read_text()
        manifest = (ROOT / "mvp-android/app/src/main/AndroidManifest.xml").read_text()
        js = (ROOT / "mvp-android/android_review_bridge.js").read_text()
        self.assertIn('from(rootProject.file(\'android_review_bridge.js\'))', build)
        self.assertIn('getAssets().open(name)', main)
        self.assertIn('evaluateBundledScript(view, "android_review_bridge.js")', main)
        self.assertIn('evaluateBundledScript(view, "offline_mini.js")', main)
        self.assertIn('CompanionReviewPolicy.accepts(url)', main)
        self.assertIn('new Intent(Intent.ACTION_VIEW', main)
        self.assertIn("PreceptorAndroidReview", js)
        self.assertNotIn("android.permission.INTERNET", manifest)


if __name__ == "__main__":
    unittest.main()
