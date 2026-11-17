"""Adversarial tests for the OFFLINE APK inspector (synthetic APK/tools only).

These fixtures do NOT prove a real APK signature or Android behavior.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPT = ROOT / "mvp-android" / "verificar_apk.sh"
ASSETS = ("app.html", "app.js", "app.css", "documents.js", "zonas.js", "sw.js")
CERT = "16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"

APKSIGNER = """#!/bin/sh
[ "${MOCK_SIGN:-ok}" = "bad" ] && exit 7
if [ "${2:-}" = "--print-certs" ]; then
  echo "Signer certificate SHA-256 digest: ${MOCK_CERT}"
fi
exit 0
"""
AAPT2 = """#!/bin/sh
case "${MOCK_AAPT:-ok}" in error) exit 7;; esac
case "${2:-}" in
 permissions)
   [ "${MOCK_AAPT:-ok}" = "empty" ] && exit 0
   [ "${MOCK_AAPT:-ok}" = "garbage" ] && { echo 'not a permissions response'; exit 0; }
   echo 'package: org.preceptoros.mvp'
   [ "${MOCK_AAPT:-ok}" = "internet" ] && echo 'uses-permission: name=android.permission.INTERNET'
   ;;
 xmltree)
   [ "${MOCK_AAPT:-ok}" = "empty" ] && exit 0
   echo 'E: manifest (line=2)'
   [ "${MOCK_AAPT:-ok}" = "debug" ] && echo 'A: android:debuggable=(type 0x12)0xffffffff'
   ;;
 *) exit 8;;
esac
exit 0
"""


class OfflineApkVerifier(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="apk-verify-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.tools = self.root / "build-tools"
        self.tools.mkdir()
        for name, code in (("apksigner", APKSIGNER), ("aapt2", AAPT2)):
            p = self.tools / name
            p.write_text(code, encoding="utf-8")
            p.chmod(0o700)
        self.apk = self.root / "fixture.apk"
        self.make_apk()

    def make_apk(self, missing=None):
        with zipfile.ZipFile(self.apk, "w") as z:
            for name in ASSETS:
                if name != missing:
                    z.writestr(f"assets/{name}", "test-only")

    def run_verifier(self, **overrides):
        env = os.environ.copy()
        env.update(
            ANDROID_BUILD_TOOLS=str(self.tools),
            MOCK_SIGN="ok",
            MOCK_CERT=CERT,
            MOCK_AAPT="ok",
        )
        env.update(overrides)
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.apk)],
            capture_output=True, text=True, env=env, timeout=10,
        )

    def assert_rejected(self, result, text):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stdout + result.stderr)

    def test_synthetic_happy_path_is_only_a_fixture(self):
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 fallo(s)", result.stdout)

    def test_missing_aapt2_fails_closed(self):
        (self.tools / "aapt2").unlink()
        self.assert_rejected(self.run_verifier(), "herramienta ausente")

    def test_missing_apksigner_fails_closed(self):
        (self.tools / "apksigner").unlink()
        self.assert_rejected(self.run_verifier(), "herramienta ausente")

    def test_aapt2_failure_is_not_absence_of_internet(self):
        self.assert_rejected(self.run_verifier(MOCK_AAPT="error"), "inspección fallida")

    def test_aapt2_empty_output_fails_closed(self):
        self.assert_rejected(self.run_verifier(MOCK_AAPT="empty"), "inspección vacía")

    def test_random_permissions_stdout_rejected(self):
        self.assert_rejected(self.run_verifier(MOCK_AAPT="garbage"), "respuesta inválida")

    def test_internet_permission_rejected_in_offline_profile(self):
        self.assert_rejected(self.run_verifier(MOCK_AAPT="internet"), "solicita INTERNET")

    def test_debuggable_rejected(self):
        self.assert_rejected(self.run_verifier(MOCK_AAPT="debug"), "APK depurable")

    def test_wrong_certificate_rejected(self):
        self.assert_rejected(self.run_verifier(MOCK_CERT="0" * 64), "certificado distinto")

    def test_bad_signature_rejected(self):
        self.assert_rejected(self.run_verifier(MOCK_SIGN="bad"), "firma APK inválida")

    def test_missing_documents_asset_rejected(self):
        self.make_apk(missing="documents.js")
        self.assert_rejected(self.run_verifier(), "recurso ausente: documents.js")

    def test_corrupt_zip_rejected(self):
        self.apk.write_text("not a ZIP archive")
        self.assert_rejected(self.run_verifier(), "inventario ZIP ilegible")


if __name__ == "__main__":
    unittest.main()
