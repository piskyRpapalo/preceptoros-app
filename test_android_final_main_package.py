"""Reconciled PreceptorOS Android MVP: source contracts and optional sealed APK gates."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
APP = ROOT / "mvp-android"
CERT = "16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"
GGUF = "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747"
JNI = "c167d707308b734013e7bd01ab5e8fdda08e05e4c2ad2fb2436f8124902d1504"
BODY = "e332c81bdee87a90a3aa76e7e34dea32c5f493879b64c1f97104510a6e3404b0"
EXACT_ASSETS = [
    "app.html", "app.css", "sw.js", "mvp_first_run.js", "superbot_talk.js",
    "talk_crab_canvas.js", "face/bubble/openworld_crab_body.js",
    "node_registration.js",
]
APK_PATH = os.getenv("PRECEPTOROS_FINAL_APK")

def file_sha(stream):
    hash_ = hashlib.sha256()
    while True:
        chunk = stream.read(4 * 1024 * 1024)
        if not chunk:
            break
        hash_.update(chunk)
    return hash_.hexdigest()

class PreceptorOSRound2Contract(unittest.TestCase):
    def test_shell_has_exact_six_panels(self):
        shell = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        for id_ in ("conversacion", "cuaderno", "lab", "ajustes", "modelos", "settings"):
            self.assertEqual(shell.count(f'id="tab-{id_}"'), 1)
        self.assertIn("mvp_first_run.js", shell)
        self.assertIn("talk_crab_canvas.js", shell)
        self.assertIn("superbot_talk.js", shell)

    def test_android_local_router_navigation_is_current(self):
        source = (APP / "offline_mini.js").read_text(encoding="utf-8")
        self.assertIn("documents: 'tab-cuaderno'", source)
        self.assertNotIn("documents: 'tab-documentos'", source)

    def test_source_state_and_security(self):
        src = (APP / "app/src/main/java/org/preceptoros/mvp/DeploymentJoinBridge.java").read_text()
        self.assertIn("addWebMessageListener", src)
        self.assertIn("isMainFrame", src)
        self.assertIn("setInstanceFollowRedirects(false)", src)
        self.assertIn("setPositiveButton", src)
        self.assertNotIn("web.addJavascriptInterface", src)
        manifest = (APP / "app/src/main/AndroidManifest.xml").read_text()
        self.assertIn('android.permission.INTERNET', manifest)
        self.assertIn('usesCleartextTraffic="false"', manifest)

    def test_canonical_crab_and_cache(self):
        with (ROOT / "interface/face/bubble/openworld_crab_body.js").open("rb") as source:
            self.assertEqual(file_sha(source), BODY)
        sw = (ROOT / "interface/sw.js").read_text()
        self.assertIn("preceptoros-armazon-v235", sw)
        self.assertIn('"/app.css?v=55"', sw)
        self.assertIn('"/mvp_first_run.js?v=1"', sw)

    @unittest.skipUnless(APK_PATH, "NO_DATA(no_sealed_apk_in_CI)")
    def test_sealed_apk_identity_and_certificate(self):
        apk = Path(APK_PATH)
        self.assertTrue(apk.is_file(), apk)
        aapt = "/home/pisky/android-sdk/build-tools/36.0.0/aapt2"
        signer = "/home/pisky/android-sdk/build-tools/36.0.0/apksigner"
        result = subprocess.run([aapt, "dump", "badging", str(apk)],
                                capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertIn("name='org.preceptoros.app'", result)
        self.assertIn("versionCode='7'", result)
        signature = subprocess.run([signer, "verify", "--print-certs", str(apk)],
                                   capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertIn("certificate SHA-256 digest: " + CERT, signature)

    @unittest.skipUnless(APK_PATH, "NO_DATA(no_sealed_apk_in_CI)")
    def test_sealed_apk_assets_byte_exact_and_model(self):
        apk = Path(APK_PATH)
        with ZipFile(apk) as archive:
            for rel in EXACT_ASSETS:
                expected = ROOT / "interface" / rel
                self.assertTrue(expected.is_file(), rel)
                self.assertIn("assets/" + rel, archive.namelist(), rel)
                self.assertEqual(hashlib.sha256(expected.read_bytes()).hexdigest(),
                                 hashlib.sha256(archive.read("assets/" + rel)).hexdigest(), rel)
            self.assertIn("assets/android_join_bridge.js", archive.namelist())
            with archive.open("assets/offline-mini.gguf") as model:
                self.assertEqual(file_sha(model), GGUF)
            with archive.open("lib/arm64-v8a/libmini_llama.so") as lib:
                self.assertEqual(file_sha(lib), JNI)
            self.assertIn("assets/licenses/ATTRIBUTIONS.txt", archive.namelist())
            self.assertIn("assets/licenses/Apache-2.0.txt", archive.namelist())
            self.assertIn("assets/licenses/llama.cpp-MIT.txt", archive.namelist())

if __name__ == "__main__":
    unittest.main()
