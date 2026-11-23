"""Capability Ledger fail-closed tests; no writes to Android devices."""
import hashlib
import importlib.util
import pathlib
import tempfile
import unittest
import warnings
from zipfile import ZipFile

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ledger", ROOT / "mvp-android/capability_ledger.py")
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

class CapabilityLedgerTests(unittest.TestCase):
    def test_real_source_seven_categories_present(self):
        report = ledger.source_ledger(ROOT)
        self.assertTrue(report["all_present"], report)
        self.assertEqual(set(report["categories"]), set(ledger.APK))
        self.assertEqual(len(report["categories"]), 7)

    def test_missing_source_math_is_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = ledger.source_ledger(pathlib.Path(tmp))
            self.assertFalse(report["all_present"])
            self.assertEqual(report["categories"]["mathematics"]["state"], "NO_DATA")

    def test_symbol_removed_fails_even_with_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "mvp-android/native-mini/mini_quality.h"
            path.parent.mkdir(parents=True)
            path.write_text("not actual math")
            missing = ledger.source_ledger(pathlib.Path(tmp))["categories"]["mathematics"]["missing"]
            self.assertIn("mvp-android/native-mini/mini_quality.h#symbol_missing", missing)

    def test_badging_and_owner_cert_are_separate(self):
        b = ledger.parse_badging("package: name='org.preceptoros.app' versionCode='8' versionName='0.3.1-mini-recovery'")
        c = ledger.parse_certificate("Signer #1 certificate SHA-256 digest: " + ledger.OWNER_CERT.upper())
        self.assertEqual((b["package"], b["versionCode"]), (ledger.CANONICAL, 8))
        self.assertEqual(c["sha256"], ledger.OWNER_CERT)
        self.assertEqual(ledger.parse_badging("x")["state"], "NO_DATA")
        self.assertEqual(ledger.parse_certificate("x")["state"], "NO_DATA")

    def test_missing_zip_is_not_package_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ledger.inspect_apk(pathlib.Path(tmp) / "missing.apk")["state"], "NO_DATA")

    def test_corrupt_zip_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bad.apk"
            path.write_bytes(b"not a zip")
            self.assertEqual(ledger.inspect_apk(path)["cause"], "apk_unreadable")

    def test_zip_missing_jni_and_model_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "some.apk"
            with ZipFile(path, "w") as z:
                z.writestr("assets/app.html", "synthetic")
            result = ledger.inspect_apk(path)
            self.assertEqual(result["state"], "NO_DATA")
            self.assertEqual(result["capabilities"]["jni"]["state"], "NO_DATA")
            self.assertEqual(result["capabilities"]["local_model"]["state"], "NO_DATA")

    def test_zip_duplicate_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "duplicate.apk"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(path, "w") as z:
                    z.writestr("assets/app.html", "a")
                    z.writestr("assets/app.html", "b")
            self.assertEqual(ledger.inspect_apk(path)["cause"], "apk_duplicate_entries")

    def test_all_packaged_is_still_not_signed_or_runtime_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "unsealed.apk"
            names = set(p for files in ledger.APK.values() for p in files)
            with ZipFile(path, "w") as z:
                for name in names:
                    z.writestr(name, "test")
            result = ledger.inspect_apk(path)
            self.assertEqual(result["state"], "NO_DATA")
            self.assertTrue(all(x["state"] == "PACKAGED" for x in result["capabilities"].values()))
            self.assertEqual(result["identity"]["state"], "NO_DATA")

    def test_installed_metadata_is_not_model_turn(self):
        p = ledger.parse_dumpsys("Package [org.preceptoros.mvp]\n versionCode=6 minSdk=26\n versionName=0.3.1\n",
                                 ledger.LEGACY)
        self.assertEqual(p["versionCode"], 6)
        self.assertEqual(p["state"], "INSTALLED_METADATA")
        self.assertEqual(ledger.parse_dumpsys("", ledger.CANONICAL)["state"], "NO_DATA")

    def test_default_report_has_four_disjoint_layers(self):
        result = ledger.make_report(ROOT)
        self.assertEqual(result["schema"], ledger.SCHEMA)
        self.assertEqual(result["source"]["all_present"], True)
        self.assertEqual(result["apk"]["state"], "NO_DATA")
        self.assertEqual(result["installed"]["state"], "NO_DATA")
        self.assertEqual(result["runtime"]["state"], "NO_DATA")
        self.assertNotIn("serial", str(result))

    def test_no_source_witness_can_be_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            link = root / "mvp-android/native-mini/mini_quality.h"
            link.parent.mkdir(parents=True)
            target = root / "real.h"
            target.write_text("has_loop( sample_token(")
            link.symlink_to(target)
            self.assertIn(str(link.relative_to(root)), ledger.source_ledger(root)["categories"]["mathematics"]["missing"])


class ReleaseCandidateSyntheticTests(unittest.TestCase):
    """Mock tool output proves policy logic only; NEVER claims a genuine signature."""

    def make_fixture(self, tmp, version=8, cert=None):
        root = pathlib.Path(tmp)
        asset_names = set(p for v in ledger.APK.values() for p in v)
        apk = root / "candidate.apk"
        with ZipFile(apk, "w") as z:
            for asset in sorted(asset_names):
                if asset.startswith("assets/") and not asset.endswith(".gguf"):
                    rel = asset.removeprefix("assets/")
                    base = "mvp-android/" if rel in (
                        "offline_mini.js", "android_join_bridge.js",
                        "android_review_bridge.js", "android_heartbeat_bridge.js",
                        "android_node_bridge.js", "android_models_bridge.js") else "interface/"
                    src = root / (base + rel)
                    src.parent.mkdir(parents=True, exist_ok=True)
                    src.write_bytes(b"synthetic-owned-asset")
                    z.writestr(asset, b"synthetic-owned-asset")
                else:
                    z.writestr(asset, b"synthetic-binary")
        tools = root / "fake-tools"
        tools.mkdir()
        aapt = tools / "aapt2"
        aapt.write_text("#!/bin/sh\n" + "echo \"package: name='org.preceptoros.app' versionCode='" + str(version) + "' versionName='synthetic'\"\n")
        signer = tools / "apksigner"
        signer.write_text("#!/bin/sh\n" + "echo 'Signer #1 certificate SHA-256 digest: " + (cert or ledger.OWNER_CERT) + "'\n")
        aapt.chmod(0o700)
        signer.chmod(0o700)
        return root, apk, tools

    def test_synthetic_signed_v8_parity_has_only_apk_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp)
            import hashlib
            pin = hashlib.sha256(b"synthetic-binary").hexdigest()
            x = ledger.inspect_apk(apk, tools, source_root=root,
                                   expected_model_sha=pin, expected_jni_sha=pin)
            self.assertEqual(x["state"], "VERIFIED_PACKAGE", x)
            self.assertEqual(x["embedded_identity"]["state"], "PINNED")
            self.assertEqual(x["identity"]["versionCode"], 8)
            self.assertEqual(x["source_parity"]["state"], "BYTE_EQUAL")
            self.assertGreaterEqual(x["source_parity"]["compared_assets"], 15)
            self.assertEqual(len(x["embedded_artifacts"]), 2)
            self.assertEqual(ledger.make_report(root)["runtime"]["state"], "NO_DATA")

    def test_synthetic_v7_cannot_be_app11_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp, version=7)
            x = ledger.inspect_apk(apk, tools, source_root=root)
            self.assertEqual(x["state"], "NO_DATA")
            self.assertEqual(x["identity"]["state"], "BLOCKED")

    def test_synthetic_wrong_cert_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp, cert="0" * 64)
            x = ledger.inspect_apk(apk, tools, source_root=root)
            self.assertEqual(x["state"], "NO_DATA")
            self.assertEqual(x["identity"]["state"], "BLOCKED")

    def test_synthetic_source_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp)
            (root / "interface/app.html").write_bytes(b"changed-after-build")
            x = ledger.inspect_apk(apk, tools, source_root=root)
            self.assertEqual(x["state"], "NO_DATA")
            self.assertEqual(x["source_parity"]["cause"], "apk_source_bytes_mismatch")

    def test_symlinked_asset_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "symlink.apk"
            with ZipFile(path, "w") as z:
                from zipfile import ZipInfo
                x = ZipInfo("assets/app.html")
                x.create_system = 3
                x.external_attr = 0o120777 << 16
                z.writestr(x, "real-page.html")
                z.writestr("assets/app.css", "css")
            result = ledger.inspect_apk(path)
            self.assertIn("assets/app.html", result["capabilities"]["six_panels"]["missing"])


    def test_signed_synthetic_without_digest_pins_must_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp)
            x = ledger.inspect_apk(apk, tools, source_root=root)
            self.assertEqual(x["identity"]["state"], "VERIFIED")
            self.assertEqual(x["embedded_identity"]["state"], "NO_DATA")
            self.assertEqual(x["state"], "NO_DATA")

    def test_signed_synthetic_with_wrong_model_digest_must_fail(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root, apk, tools = self.make_fixture(tmp)
            pin = hashlib.sha256(b"synthetic-binary").hexdigest()
            x = ledger.inspect_apk(apk, tools, source_root=root,
                                   expected_model_sha="0" * 64, expected_jni_sha=pin)
            self.assertEqual(x["embedded_identity"]["cause"], "model_or_jni_digest_changed")
            self.assertEqual(x["state"], "NO_DATA")

    def test_user0_disabled_is_not_enabled(self):
        body = ("Package [org.preceptoros.mvp]\n"
                "  versionCode=2 minSdk=26\n"
                "  versionName=0.1.0-mvp\n"
                "    User 0: installed=true hidden=false enabled=3\n")
        got = ledger.parse_dumpsys(body, ledger.LEGACY)
        self.assertEqual(got["user0_enabled"], "USER_DISABLED")
        self.assertNotIn("serial", str(got))

    def test_user0_default_is_not_runtime(self):
        body = ("Package [org.preceptoros.app]\n versionCode=7\n"
                " versionName=0.3.0-mvp\n User 0: installed=true enabled=0\n")
        got = ledger.parse_dumpsys(body, ledger.CANONICAL)
        self.assertEqual(got["user0_enabled"], "DEFAULT")
        self.assertEqual(ledger.make_report(ROOT)["runtime"]["state"], "NO_DATA")

    def test_untrusted_apk_path_refused_before_hash(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        with patch.object(ledger.subprocess, "run",
                          return_value=CompletedProcess([], 0, stdout="package:/sdcard/sneaky.apk\n")) as run:
            got = ledger.installed_apk_sha256("opaque-device", ledger.CANONICAL)
        self.assertEqual(got["cause"], "adb_apk_path_untrusted")
        self.assertEqual(run.call_count, 1)

    def test_read_only_hash_result_has_no_serial(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        sha = "a" * 64
        values = [CompletedProcess([], 0, stdout="package:/data/app/~~opaque/pkg/base.apk\n"),
                  CompletedProcess([], 0, stdout=sha + "  /data/app/~~opaque/pkg/base.apk\n")]
        with patch.object(ledger.subprocess, "run", side_effect=values) as run:
            got = ledger.installed_apk_sha256("device-private", ledger.CANONICAL)
        self.assertEqual(got, {"state": "MEASURED", "sha256": sha})
        self.assertNotIn("device-private", str(got))
        self.assertEqual(run.call_count, 2)

class ChunkedSha256RegressionTests(unittest.TestCase):
    """Regression: inspect_apk chunked SHA256 must match full-read digest (Python 3.10 portability)."""

    def test_apk_sha256_matches_full_read_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            apk = root / "digest.apk"
            payload = b"\x00" * 4096 + b"preceptoros-android-ledger-regression" + b"\xff" * 2048
            with ZipFile(apk, "w") as z:
                z.writestr("assets/app.html", payload.decode("latin-1"))
            expected = hashlib.sha256(apk.read_bytes()).hexdigest()
            result = ledger.inspect_apk(apk)
            self.assertEqual(result["sha256"], expected)

    def test_apk_sha256_empty_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            apk = root / "empty.apk"
            with ZipFile(apk, "w") as z:
                pass
            expected = hashlib.sha256(apk.read_bytes()).hexdigest()
            result = ledger.inspect_apk(apk)
            self.assertEqual(result["sha256"], expected)

    def test_apk_sha256_large_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            apk = root / "large.apk"
            # 5 MB payload forces multiple 2 MB chunks
            payload = b"A" * (5 * 1024 * 1024)
            with ZipFile(apk, "w") as z:
                z.writestr("assets/app.html", payload.decode("latin-1"))
            expected = hashlib.sha256(apk.read_bytes()).hexdigest()
            result = ledger.inspect_apk(apk)
            self.assertEqual(result["sha256"], expected)

    def test_no_file_descriptor_leak_on_multiple_calls(self):
        import os
        proc_fd = pathlib.Path("/proc/self/fd")
        if not proc_fd.is_dir():
            self.skipTest("/proc/self/fd not available (non-Linux environment)")

        def count_fds():
            """Count open file descriptors via /proc/self/fd."""
            return len(os.listdir(proc_fd))

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            apk = root / "fd.apk"
            with ZipFile(apk, "w") as z:
                z.writestr("assets/app.html", "fd-leak-check")

            before = count_fds()
            for _ in range(21):
                ledger.inspect_apk(apk)
            after = count_fds()

            self.assertEqual(
                before, after,
                f"File descriptor leak detected: {before} → {after} (leaked {after - before} FDs after 21 inspect_apk calls)"
            )

    def test_sabotage_single_leaked_fd_is_detected(self):
        """Deterministic proof: a single leaked FD causes the no-leak assertion to fail."""
        import os
        proc_fd = pathlib.Path("/proc/self/fd")
        if not proc_fd.is_dir():
            self.skipTest("/proc/self/fd not available (non-Linux environment)")

        fd, tmp_path = tempfile.mkstemp()
        try:
            before = len(os.listdir(proc_fd))
            # Simulate a leak: open a file and deliberately do not close it
            leaked_fd = os.open(tmp_path, os.O_RDONLY)
            after_open = len(os.listdir(proc_fd))
            self.assertEqual(after_open, before + 1, "Injected FD should increase count by exactly 1")
            # Now close it to prove the test itself does not leak
            os.close(leaked_fd)
            after_close = len(os.listdir(proc_fd))
            self.assertEqual(after_close, before, "After cleanup, FD count must return to baseline")
        finally:
            os.close(fd)
            os.unlink(tmp_path)

if __name__ == "__main__":
    unittest.main()
