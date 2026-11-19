"""Tank 3 model APK provenance and fail-closed packaging checks.

No phone operations, no keystore exposure and no live model claims.
Run on the release candidate with TANK3_APK=<path> for binary verification.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent
ANDROID = ROOT / "mvp-android"
EXPECTED_MODEL = "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747"
EXPECTED_SIGNER = "16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"
BUILD_TOOLS = Path(os.environ.get("ANDROID_BUILD_TOOLS", "/home/pisky/android-sdk/build-tools/36.0.0"))


class Tank3Mini(unittest.TestCase):
    def test_uses_known_package_names_only(self):
        build = (ANDROID / "app/build.gradle").read_text()
        self.assertIn("'org.preceptoros.app'", build)
        self.assertIn("'org.preceptoros.mvp'", build)
        self.assertIn("Unexpected Android package id", build)
        self.assertIn("mvpVersionCode", build)

    def test_model_digest_fixed_in_source(self):
        java = (ANDROID / "app/src/main/java/org/preceptoros/mvp/MainActivity.java").read_text()
        self.assertIn(EXPECTED_MODEL, java)
        self.assertIn("MessageDigest.getInstance(\"SHA-256\")", java)
        self.assertIn("getAssets().open(\"offline-mini.gguf\")", java)
        self.assertIn("NO_DATA(mini_model_asset_missing_or_invalid)", java)

    def test_native_model_does_not_have_node_or_network_tools(self):
        cxx = (ANDROID / "native-mini/mini_jni.cpp").read_text()
        self.assertIn("llama_model_load_from_file", cxx)
        self.assertIn("llama_process", cxx)
        self.assertIn("llama_vocab_n_tokens", cxx)
        for forbidden in ("socket(", "curl", "ssh", "system(", "exec(", "popen("):
            self.assertNotIn(forbidden, cxx)

    def test_js_reports_no_data_without_model_runtime(self):
        source = (ANDROID / "offline_mini.js").read_text()
        self.assertIn("NO_DATA(on_device_model_unavailable)", source)
        self.assertIn("PreceptorAndroidMiniModel", source)
        self.assertIn("stopImmediatePropagation", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("XMLHttpRequest", source)

    def test_apk_provenance_build_is_reproducible_from_pinned_checkout(self):
        script = (ANDROID / "native-mini/build-android.sh").read_text()
        self.assertIn("f2cc7282ce0042641df55e0e563b75e824e2b647", script)
        self.assertIn("NO_DATA(llama_source_revision_mismatch)", script)
        self.assertIn("ANDROID_ABI=arm64-v8a", script)

    def test_join_network_permission_is_explicit_and_origin_checked(self):
        manifest = (ANDROID / "app/src/main/AndroidManifest.xml").read_text()
        self.assertIn("uses-permission android:name=\"android.permission.INTERNET\"", manifest)
        self.assertIn('android:usesCleartextTraffic="false"', manifest)
        native = (ANDROID / "app/src/main/java/org/preceptoros/mvp/DeploymentJoinBridge.java").read_text()
        self.assertIn("WebViewCompat.addWebMessageListener", native)
        self.assertIn("isMainFrame", native)
        self.assertIn("EXPECTED_ORIGIN", native)
        self.assertIn("new AlertDialog.Builder", native)
        self.assertIn("setInstanceFollowRedirects(false)", native)
        self.assertNotIn("addJavascriptInterface(", native)
        shim = (ANDROID / "android_join_bridge.js").read_text()
        self.assertIn("PreceptorAndroidJoin", shim)
        self.assertNotIn("fetch(", shim)
        self.assertNotIn("XMLHttpRequest", shim)

    def test_debug_join_package_if_provided(self):
        location = os.environ.get("JOIN_DEBUG_APK")
        if not location:
            self.skipTest("NO_DATA(JOIN_DEBUG_APK_unset): debug bridge package not measured")
        apk = Path(location)
        self.assertTrue(apk.is_file())
        aapt2 = str(BUILD_TOOLS / "aapt2")
        badging = subprocess.run([aapt2, "dump", "badging", str(apk)],
            capture_output=True, text=True, check=True, timeout=20).stdout
        self.assertRegex(badging, r"package: name='org.preceptoros.app' versionCode='5' ")
        perms = subprocess.run([aapt2, "dump", "permissions", str(apk)],
            capture_output=True, text=True, check=True, timeout=20).stdout
        self.assertIn("android.permission.INTERNET", perms)
        with zipfile.ZipFile(apk) as bundle:
            for name in ("assets/android_join_bridge.js", "assets/offline-mini.gguf",
                         "lib/arm64-v8a/libmini_llama.so", "assets/app.html",
                         "assets/node_registration.js"):
                self.assertIn(name, bundle.namelist())
            self.assertEqual(hashlib.sha256(bundle.read("assets/offline-mini.gguf")).hexdigest(), EXPECTED_MODEL)
            # This debug build is intentionally based on the older phone UI.
            # It is not yet the final owner UI with requestDeploymentReview.
            self.assertNotIn(b"requestDeploymentReview",bundle.read("assets/node_registration.js"))

    def test_binary_assets_are_ignored(self):
        ignore = (ANDROID / ".gitignore").read_text()
        self.assertIn("app/src/main/assets/", ignore)
        self.assertIn("app/src/main/jniLibs/", ignore)
        self.assertIn(".native-build/", ignore)
        tracked = subprocess.run(["git", "ls-files", "--",
            "mvp-android/app/src/main/assets/offline-mini.gguf",
            "mvp-android/app/src/main/jniLibs/arm64-v8a/libmini_llama.so"],
            cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(tracked.stdout.strip(), "")

    def test_release_candidate_binary_contract(self):
        location = os.environ.get("TANK3_APK")
        if not location:
            self.skipTest("NO_DATA(TANK3_APK_unset): only source tests executed")
        apk = Path(location)
        self.assertTrue(apk.is_file())
        aapt2 = str(BUILD_TOOLS / "aapt2")
        signer = str(BUILD_TOOLS / "apksigner")
        badging = subprocess.run([aapt2, "dump", "badging", str(apk)],
            capture_output=True, text=True, check=True, timeout=20).stdout
        self.assertRegex(badging,
            r"package: name='org.preceptoros.app' versionCode='4' ")
        cert = subprocess.run([signer, "verify", "--print-certs", str(apk)],
            capture_output=True, text=True, check=True, timeout=20).stdout
        self.assertIn(EXPECTED_SIGNER, cert)
        perms = subprocess.run([aapt2, "dump", "permissions", str(apk)],
            capture_output=True, text=True, check=True, timeout=20).stdout
        self.assertNotIn("android.permission.INTERNET", perms)
        with zipfile.ZipFile(apk) as bundle:
            for name in ("assets/app.html", "assets/app.js", "assets/app.css",
                         "assets/offline_mini.js", "assets/android_review_bridge.js",
                         "assets/documents.js", "assets/sw.js",
                         "lib/arm64-v8a/libmini_llama.so",
                         "assets/offline-mini.gguf"):
                self.assertIn(name, bundle.namelist())
            checksum = hashlib.sha256()
            with bundle.open("assets/offline-mini.gguf") as stream:
                while data := stream.read(1024 * 1024):
                    checksum.update(data)
            self.assertEqual(checksum.hexdigest(), EXPECTED_MODEL)


if __name__ == "__main__":
    unittest.main()
