"""Reconciled PreceptorOS Android MVP: source contracts and optional sealed APK gates."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
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

# The existing Android 1.1 judge owns signature, package and version policy.
sys.path.insert(0, str(APP))
import release_guard as artifact_guard


def public_mini_builder():
    spec = importlib.util.spec_from_file_location(
        "preceptor_public_mini_build", ROOT / "bin/package_public_mini.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_public_shell():
    return public_mini_builder().shell(
        (ROOT / "interface/app.html").read_text(encoding="utf-8")).encode("utf-8")


def classify_packaged_shell(contents):
    if contents == (ROOT / "interface/app.html").read_bytes():
        return "OWNER"
    if contents == canonical_public_shell():
        return "PUBLIC"
    raise ValueError("APK_SHELL_NOT_SOURCE_DERIVED")


def android_build_tool(name):
    roots = [os.getenv("ANDROID_SDK_ROOT"), os.getenv("ANDROID_HOME"), str(Path.home() / "android-sdk")]
    for root in roots:
        if not root:
            continue
        for candidate in sorted((Path(root) / "build-tools").glob("*/" + name), reverse=True):
            if candidate.is_file():
                return candidate
    installed = shutil.which(name)
    if installed:
        return Path(installed)
    raise RuntimeError("NO_DATA(android_build_tool_unavailable)")



def file_sha(stream):
    hash_ = hashlib.sha256()
    while True:
        chunk = stream.read(4 * 1024 * 1024)
        if not chunk:
            break
        hash_.update(chunk)
    return hash_.hexdigest()

class PreceptorOSRound2Contract(unittest.TestCase):
    def test_packaged_shell_is_owner_or_generated_public(self):
        owner = (ROOT / "interface/app.html").read_bytes()
        public = canonical_public_shell()
        self.assertEqual(classify_packaged_shell(owner), "OWNER")
        self.assertEqual(classify_packaged_shell(public), "PUBLIC")

    def test_unrecognized_or_mutated_shell_rejected(self):
        owner = (ROOT / "interface/app.html").read_bytes()
        with self.assertRaisesRegex(ValueError, "APK_SHELL_NOT_SOURCE_DERIVED"):
            classify_packaged_shell(owner + b"\n")

    def test_android_build_tool_finds_an_explicit_sdk_without_owner_path(self):
        with tempfile.TemporaryDirectory(prefix="apk-build-tool-fixture-") as temp:
            fake = Path(temp) / "build-tools" / "36.0.0" / "aapt2"
            fake.parent.mkdir(parents=True)
            fake.write_bytes(b"synthetic-tool-not-executed")
            with patch.dict(os.environ, {"ANDROID_SDK_ROOT": temp}):
                self.assertEqual(android_build_tool("aapt2"), fake)
    def _probe_synthetic_archive(self, profile, *, corrupt_sw=False):
        # A fixture tests the actual archive-verifier, not an unsigned release.
        with tempfile.TemporaryDirectory(prefix="apk-profile-fixture-") as temp:
            root = Path(temp)
            model = b"GGUF-fixture-not-model"
            jni = b"\x7fELF-fixture-not-native-code"
            if profile == "OWNER":
                html = (ROOT / "interface/app.html").read_bytes()
                sw = (ROOT / "interface/sw.js").read_bytes()
            else:
                target = root / "public-projection"
                public_mini_builder().build(target)
                html = (target / "app/index.html").read_bytes()
                sw = (target / "app/sw.js").read_bytes()
            if corrupt_sw:
                sw += b"synthetic-mutant"
            archive_path = root / "synthetic.apk"
            with ZipFile(archive_path, "w") as z:
                for rel in EXACT_ASSETS:
                    if rel == "app.html":
                        content = html
                    elif rel == "sw.js":
                        content = sw
                    else:
                        content = (ROOT / "interface" / rel).read_bytes()
                    z.writestr("assets/" + rel, content)
                z.writestr("assets/android_join_bridge.js", b"synthetic")
                z.writestr("assets/offline-mini.gguf", model)
                z.writestr("lib/arm64-v8a/libmini_llama.so", jni)
                for rel in ("ATTRIBUTIONS.txt", "Apache-2.0.txt", "llama.cpp-MIT.txt"):
                    z.writestr("assets/licenses/" + rel, b"synthetic")
            with (patch.object(sys.modules[__name__], "GGUF", hashlib.sha256(model).hexdigest()),
                  patch.object(sys.modules[__name__], "JNI", hashlib.sha256(jni).hexdigest())):
                self.verify_packaged_assets(archive_path)

    def test_synthetic_both_profiles_have_source_exact_assets(self):
        self._probe_synthetic_archive("OWNER")
        self._probe_synthetic_archive("PUBLIC")

    def test_synthetic_public_service_worker_tamper_is_rejected(self):
        with self.assertRaises(AssertionError):
            self._probe_synthetic_archive("PUBLIC", corrupt_sw=True)

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
        self.assertIn("preceptoros-armazon-v243", sw)
        self.assertIn('"/app.css?v=57"', sw)
        self.assertIn('"/mvp_first_run.js?v=2"', sw)

    @unittest.skipUnless(APK_PATH, "NO_DATA(no_sealed_apk_in_CI)")
    def test_sealed_apk_identity_and_certificate(self):
        apk = Path(APK_PATH)
        self.assertTrue(apk.is_file(), apk)
        # One source of truth: release_guard rejects <v8, wrong package,
        # invalid signature scheme and signer mismatch; no legacy v7 bypass.
        artifact_guard.inspect_signature_and_identity(
            apk, cert_sha=CERT, apksigner=android_build_tool("apksigner"),
            aapt2=android_build_tool("aapt2"))

    def verify_packaged_assets(self, apk):
        with ZipFile(apk) as archive:
            profile = classify_packaged_shell(archive.read("assets/app.html"))
            # Shared source-backed components remain byte-exact. The two
            # distribution profiles have intentionally different shells/SW.
            for rel in EXACT_ASSETS:
                if rel in {"app.html", "sw.js"}:
                    continue
                expected = ROOT / "interface" / rel
                self.assertTrue(expected.is_file(), rel)
                self.assertIn("assets/" + rel, archive.namelist(), rel)
                self.assertEqual(hashlib.sha256(expected.read_bytes()).hexdigest(),
                                 hashlib.sha256(archive.read("assets/" + rel)).hexdigest(), rel)
            if profile == "OWNER":
                expected_sw = (ROOT / "interface/sw.js").read_bytes()
            else:
                with tempfile.TemporaryDirectory(prefix="android-public-shell-") as temp:
                    target = Path(temp) / "projection"
                    public_mini_builder().build(target)
                    expected_sw = (target / "app/sw.js").read_bytes()
            self.assertEqual(hashlib.sha256(expected_sw).hexdigest(),
                             hashlib.sha256(archive.read("assets/sw.js")).hexdigest())
            self.assertIn("assets/android_join_bridge.js", archive.namelist())
            with archive.open("assets/offline-mini.gguf") as model:
                self.assertEqual(file_sha(model), GGUF)
            with archive.open("lib/arm64-v8a/libmini_llama.so") as lib:
                self.assertEqual(file_sha(lib), JNI)
            self.assertIn("assets/licenses/ATTRIBUTIONS.txt", archive.namelist())
            self.assertIn("assets/licenses/Apache-2.0.txt", archive.namelist())
            self.assertIn("assets/licenses/llama.cpp-MIT.txt", archive.namelist())

    @unittest.skipUnless(APK_PATH, "NO_DATA(no_sealed_apk_in_CI)")
    def test_sealed_apk_assets_byte_exact_and_model(self):
        self.verify_packaged_assets(Path(APK_PATH))


if __name__ == "__main__":
    unittest.main()
