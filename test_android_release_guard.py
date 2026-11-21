"""Adversarial offline fixtures for the Android 1.1 release candidate judge.

No real APK, physical inference, model, signing key, or phone is used here.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

sys.path.insert(0, str(Path(__file__).resolve().parent / "mvp-android"))
import release_guard as rg


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReleaseGuardCases(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="preceptor-release-fixture-")
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.apk = self.root / "candidate.apk"
        self.model = b"GGUF-fixture, not a real GGUF"
        self.jni = b"\x7fELF-fixture, not a real ELF"
        self.files = {
            rg.MODEL: self.model, rg.JNI: self.jni,
            "assets/licenses/ATTRIBUTIONS.txt": b"fixture attribution",
            "assets/licenses/Apache-2.0.txt": b"synthetic license",
            "assets/licenses/llama.cpp-MIT.txt": b"synthetic license",
            "assets/app.html": b"<p>LOCAL</p>",
        }
        self.pack()
        self.apksigner = self.root / "apksigner"
        self.aapt2 = self.root / "aapt2"
        self.cert = "a" * 64
        self.tools()

    def pack(self, *, entries=None):
        with ZipFile(self.apk, "w") as z:
            for name, content in (entries if entries is not None else self.files.items()):
                z.writestr(name, content)

    def tools(self, *, sig=True, v2=True, signer=None, package="org.preceptoros.app", version=8,
              debuggable=False):
        signed = self.cert if hasattr(self, "cert") else "a" * 64
        cert = signer or signed
        signature = ("Signer #1 certificate SHA-256 digest: " + cert + "\n"
                     + "Verified using v2 scheme (APK Signature Scheme v2): "
                     + ("true" if v2 else "false") + "\n")
        badging = ("package: name='" + package + "' versionCode='" + str(version)
                   + "' versionName='1.1'\n" + ("application-debuggable\n" if debuggable else ""))
        self.apksigner.write_text("#!/bin/sh\n" + ("exit 9\n" if not sig else
                                  "cat <<'EOF'\n" + signature + "EOF\n"))
        self.aapt2.write_text("#!/bin/sh\ncat <<'EOF'\n" + badging + "EOF\n")
        self.apksigner.chmod(0o700)
        self.aapt2.chmod(0o700)

    def audit(self, **changes):
        kw = dict(apk_sha=rg.sha_file(self.apk), jni_sha=digest(self.jni),
                  model_sha=digest(self.model), cert_sha=self.cert,
                  apksigner=self.apksigner, aapt2=self.aapt2)
        kw.update(changes)
        return rg.audit(self.apk, **kw)

    def hold(self, code, **kwargs):
        with self.assertRaises(rg.ReleaseHold) as cx:
            self.audit(**kwargs)
        self.assertEqual(str(cx.exception), code)

    def test_fixture_is_accepted_but_is_not_a_physical_release(self):
        self.assertIsNone(self.audit())

    def test_no_external_signature_tool_is_not_success(self):
        self.apksigner.unlink()
        self.hold("APK_SIGNATURE_UNVERIFIED")

    def test_unverified_signature_denied(self):
        self.tools(sig=False)
        self.hold("APK_SIGNATURE_UNVERIFIED")

    def test_signer_certificate_mismatch(self):
        self.tools(signer="b" * 64)
        self.hold("APK_SIGNER_MISMATCH")

    def test_v2_or_v3_required(self):
        self.tools(v2=False)
        self.hold("APK_V2_V3_SIGNATURE_MISSING")

    def test_downgrade_or_wrong_package_denied(self):
        self.tools(version=7)
        self.hold("APK_PACKAGE_OR_VERSION_INVALID")
        self.tools(package="org.preceptoros.mvp")
        self.hold("APK_PACKAGE_OR_VERSION_INVALID")

    def test_debuggable_rejected(self):
        self.tools(debuggable=True)
        self.hold("APK_DEBUGGABLE")

    def test_apk_sha_must_be_independently_pinned(self):
        self.hold("APK_SHA_MISMATCH", apk_sha="f" * 64)
        self.hold("APK_PIN_MISSING", apk_sha="")

    def test_jni_and_model_hashes_must_match(self):
        self.hold("JNI_SHA_MISMATCH", jni_sha="f" * 64)
        self.hold("GGUF_SHA_MISMATCH", model_sha="f" * 64)

    def test_missing_libraries_or_licenses_are_denied(self):
        for key in (rg.JNI, rg.MODEL, rg.REQUIRED[-1]):
            original = self.files.pop(key)
            self.pack()
            self.hold("APK_REQUIRED_MEMBER_MISSING")
            self.files[key] = original
        self.pack()

    def test_private_build_path_in_jni_is_rejected_without_echoing_path(self):
        self.jni = b"\x7fELF.../home/fixtureuser/projects/native/obj.o\x00"
        self.files[rg.JNI] = self.jni
        self.pack()
        self.hold("JNI_PRIVATE_BUILD_PATH")

    def test_public_private_route_is_rejected(self):
        self.files["assets/app.html"] = b"/api/hexelion/chat"
        self.pack()
        self.hold("PUBLIC_ASSET_PRIVATE_REFERENCE")

    def test_duplicate_names_and_path_traversal(self):
        self.pack(entries=list(self.files.items()) + [(rg.MODEL, self.model)])
        self.hold("ZIP_DUPLICATE_ENTRY")
        self.pack(entries=list(self.files.items()) + [("../escape", b"no")])
        self.hold("ZIP_INVALID_PATH_OR_LINK")

    def test_symlink_is_rejected(self):
        entries = list(self.files.items())
        with ZipFile(self.apk, "w") as z:
            for name, content in entries:
                z.writestr(name, content)
            link = ZipInfo("assets/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, b"/tmp/should-not-follow")
        self.hold("ZIP_INVALID_PATH_OR_LINK")

    def test_corrupted_archive_fails_closed(self):
        self.apk.write_bytes(b"invalid")
        self.hold("APK_UNREADABLE_OR_CORRUPT")

    def test_empty_license_is_rejected(self):
        self.files["assets/licenses/Apache-2.0.txt"] = b""
        self.pack()
        self.hold("LICENSE_EMPTY")

    def test_immutable_model_release_digest(self):
        self.assertEqual(rg.MODEL_SHA256,
                         "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747")


if __name__ == "__main__":
    unittest.main()
