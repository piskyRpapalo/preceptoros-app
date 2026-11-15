"""SWARM-01 independent adversarial tests. Synthetic data, no live services.

Integrated from the independent SWARM-01 proposal; imports use APP modules.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import system_check as core
import system_check_local as local

NOW = "2026-11-14T12:00:00Z"
OLD = "2026-11-14T11:57:59Z"


def observation(field, value, *, origin="MEASURED", stamp=NOW):
    source = core.SOURCES.get(field, "host.service_witness:" + field)
    return core.Observation(value, source, stamp, origin)


def fixture():
    return {
        "os": observation("os", "Linux"),
        "architecture": observation("architecture", "x86_64"),
        "python": observation("python", [3, 10, 0]),
        "auxiliary_python": observation("auxiliary_python", False),
        "sqlite": observation("sqlite", True),
        "cpu_logical": observation("cpu_logical", 2),
        "models": observation("models", []),
        "internet": observation("internet", False),
    }


class IndependentAdversarial(unittest.TestCase):
    def test_zero_models_preserves_first_use(self):
        report = core.diagnose(fixture(), NOW)
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["facts"]["models"]["value"], [])
        self.assertIn("review_diagnosis", report["offline_actions"])
        self.assertEqual(report["services"]["model_engine"]["state"], "NO_DATA")

    def test_machine_without_internet_never_attempts_network_or_child(self):
        with patch("socket.socket", side_effect=AssertionError("network used")), \
             patch("socket.create_connection", side_effect=AssertionError("network used")), \
             patch("subprocess.Popen", side_effect=AssertionError("child used")), \
             patch("shutil.which", return_value=None):
            report = local.run_check(model_reader=lambda: {
                "estado": "MEDIDO", "modelos": [], "total": 0})
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["facts"]["internet"]["state"], "NO_DATA")
        self.assertFalse(report["facts"]["auxiliary_python"]["value"])

    def test_disconnected_local_server_does_not_become_authorization(self):
        facts = fixture()
        facts["services"] = {"model_engine": observation("model_engine", False)}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["services"]["model_engine"]["cause"], "service_unreachable")
        self.assertEqual(report["authority"], "NOT_AUTHORIZED")

    def test_listed_model_without_blob_is_not_installed_file(self):
        import consola
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifests" / "registry.ollama.ai" / "library" / "fixture" / "v1"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"layers": [{
                "mediaType": "application/vnd.ollama.image.model",
                "digest": "sha256:" + "a" * 64, "size": 3}]}))
            catalogue = consola.modelos_pc(root, visible=lambda _: "fixture-store")
            self.assertEqual(catalogue["total"], 1)
            self.assertFalse(catalogue["modelos"][0]["blob_presente"])
            adapted = core.console_models(catalogue, NOW)
            self.assertEqual(adapted.origin, "MEASURED")
            self.assertEqual(adapted.value, [])

    def test_permission_denied_model_reader_is_unknown_and_private_text_absent(self):
        def denied():
            raise PermissionError("/private/fixture/store credential=fixture-only")
        report = local.run_check(model_reader=denied)
        self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")
        self.assertNotIn("/private/fixture", core.canonical(report).decode())
        self.assertNotIn("credential=", core.canonical(report).decode())
        self.assertEqual(report["state"], "LOCAL")

    def test_permission_denied_hardware_preserves_partial_report(self):
        with patch.object(local, "_memory_available", side_effect=PermissionError("fixture")):
            report = local.run_check(model_reader=lambda: {})
        self.assertEqual(report["facts"]["memory_available_bytes"]["state"], "NO_DATA")
        self.assertEqual(report["facts"]["python"]["state"], "MEASURED")
        self.assertNotIn("value", report["facts"]["memory_available_bytes"])

    def test_expired_runtime_and_service_do_not_stay_connected(self):
        facts = fixture()
        facts["python"] = observation("python", [3, 10, 0], stamp=OLD)
        facts["services"] = {"remote_provider": observation("remote_provider", True, stamp=OLD)}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertEqual(report["facts"]["python"]["cause"], "evidence_expired")
        self.assertEqual(report["services"]["remote_provider"]["cause"], "evidence_expired")

    def test_incomplete_hardware_is_not_measured_zero(self):
        report = core.diagnose(fixture(), NOW)
        self.assertEqual(report["facts"]["cpu_logical"]["value"], 2)
        for field in ("memory_available_bytes", "disk_free_bytes"):
            self.assertEqual(report["facts"][field]["state"], "NO_DATA")
            self.assertNotIn("value", report["facts"][field])

    def test_declared_remote_service_is_not_connected(self):
        facts = fixture()
        facts["services"] = {"remote_provider": observation("remote_provider", True, origin="DECLARED")}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["services"]["remote_provider"]["state"], "DECLARED")
        self.assertEqual(report["authority"], "NOT_AUTHORIZED")

    def test_simulated_remote_service_is_not_connected(self):
        facts = fixture()
        facts["services"] = {"remote_provider": observation("remote_provider", True, origin="SIMULATED")}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["services"]["remote_provider"]["state"], "SIMULATED")

    def test_measured_connection_is_still_not_tool_authority(self):
        facts = fixture()
        facts["services"] = {"tool_transport": observation("tool_transport", True)}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "CONNECTED")
        self.assertEqual(report["authority"], "NOT_AUTHORIZED")
        self.assertFalse(any("exec" in action or "grant" in action for action in report["local_capabilities"]))

    def test_missing_store_is_not_a_proven_empty_machine(self):
        adapted = core.console_models({"estado": "NO_DATA", "modelos": []}, NOW)
        self.assertEqual(adapted.origin, "NO_DATA")
        self.assertNotEqual(adapted.value, [])

    def test_manifest_declaration_without_disk_measurement_is_unknown(self):
        adapted = core.console_models({"estado": "DECLARADO", "modelos": [
            {"id": "fixture:v1", "blob_presente": True}], "total": 1}, NOW)
        self.assertEqual(adapted.origin, "NO_DATA")

    def test_future_service_never_becomes_connected(self):
        facts = fixture()
        facts["services"] = {"remote_provider": observation("remote_provider", True, stamp="2026-11-14T12:00:01Z")}
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["state"], "LOCAL")
        self.assertEqual(report["services"]["remote_provider"]["cause"], "evidence_future")

    def test_slow_capture_is_validated_at_completion_not_start(self):
        # Fixed collector start is now stale at the mocked completion time.
        # A report must not remain FRESH by using its own start as validation now.
        class CompletionClock:
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 14, 12, 2, 1, tzinfo=timezone.utc)
        with patch.object(local, "collect", return_value=(fixture(), NOW)), \
             patch.object(local, "datetime", CompletionClock):
            report = local.run_check()
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertEqual(report["facts"]["python"]["cause"], "evidence_expired")


class NativeStoreSecurityRegressions(unittest.TestCase):
    def _manifest(self, root, *, digest=None, size=3, name="fixture", tag="v1"):
        digest = digest if digest is not None else "sha256:" + "a" * 64
        manifest = root / "manifests" / "registry.ollama.ai" / "library" / name / tag
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"layers": [{
            "mediaType": "application/vnd.ollama.image.model", "digest": digest, "size": size}]}))
        return manifest

    def _native(self, root):
        with patch.dict(os.environ, {"OLLAMA_MODELS": str(root)}), \
             patch("socket.socket", side_effect=AssertionError("network used")), \
             patch("subprocess.Popen", side_effect=AssertionError("child used")):
            return local.run_check()

    def test_credential_shaped_catalogue_id_is_withheld(self):
        token = "ghp_" + "A" * 45
        adapted = core.console_models({"estado": "MEDIDO", "modelos": [
            {"id": token, "blob_presente": True, "sha256": "a"*64, "bytes": 3}], "total": 1}, NOW)
        self.assertEqual(adapted.origin, "NO_DATA")
        facts = fixture()
        facts["models"] = adapted
        report = core.diagnose(facts, NOW)
        self.assertNotIn(token, core.canonical(report).decode())

    def test_credential_shaped_direct_model_observation_is_withheld(self):
        token = "ghp_" + "A" * 45
        facts = fixture()
        facts["models"] = observation("models", [token])
        report = core.diagnose(facts, NOW)
        self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")
        self.assertNotIn(token, core.canonical(report).decode())

    def test_native_65_manifest_limit_precedes_any_manifest_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = {"fixture-tag-" + str(i) for i in range(65)}
            for name in names:
                self._manifest(root, tag=name)
            opened = []
            enabled = [True]
            def audit(event, args):
                if enabled[0] and event == "open" and args:
                    path = args[0]
                    if isinstance(path, (str, bytes)) and os.path.basename(os.fsdecode(path)) in names:
                        opened.append(os.fsdecode(path))
            sys.addaudithook(audit)
            try:
                report = self._native(root)
            finally:
                enabled[0] = False
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")
            self.assertEqual(opened, [], "manifest bytes must not be opened/read after the count exceeds MAX64")

    def test_native_model_blob_symlink_outside_store_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "store"
            self._manifest(root)
            target = base / "fixture-outside-blob"
            target.write_bytes(b"123")
            blobs = root / "blobs"
            blobs.mkdir()
            (blobs / ("sha256-" + "a" * 64)).symlink_to(target)
            report = self._native(root)
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")
            self.assertNotIn(str(base), core.canonical(report).decode())

    def test_native_malformed_digest_cannot_claim_installed_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._manifest(root, digest="sha256:not-a-sha")
            blobs = root / "blobs"
            blobs.mkdir()
            (blobs / "sha256-not-a-sha").write_bytes(b"123")
            report = self._native(root)
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")

    def test_native_boolean_manifest_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._manifest(root, size=True)
            blobs = root / "blobs"
            blobs.mkdir()
            (blobs / ("sha256-" + "a" * 64)).write_bytes(b"1")
            report = self._native(root)
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")


    def test_native_permission_failure_is_not_empty_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._manifest(root)
            with patch.object(local, "_directory", side_effect=PermissionError("private fixture")):
                report = self._native(root)
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")
            self.assertNotIn("private fixture", core.canonical(report).decode())

    def test_native_fifo_manifest_is_rejected_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("NO_DATA(fifo_fixture_not_supported)")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            manifest.unlink()
            os.mkfifo(manifest)
            report = self._native(root)
            self.assertEqual(report["facts"]["models"]["state"], "NO_DATA")

    def test_aggregate_byte_limit_does_not_read_a_seventeenth_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b'{"padding":"'+b'x'*(65536-14)+b'"}'
            self.assertEqual(len(data), 65536)
            (root/"manifest").write_bytes(data)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            budget = [local.MAX_STORE_BYTES]
            try:
                for _ in range(16):
                    local._read_manifest(fd, ("manifest",), budget)
                self.assertEqual(budget[0], 0)
                with self.assertRaises(ValueError):
                    local._read_manifest(fd, ("manifest",), budget)
                self.assertEqual(budget[0], 0)
            finally:
                os.close(fd)

    def test_string_completion_does_not_measure_first_operation(self):
        result = core.first_use_metric(0, 10, "false")
        self.assertEqual(result["state"], "NO_DATA")
        self.assertEqual(result["cause"], "input_invalid")


if __name__ == "__main__":
    unittest.main()
