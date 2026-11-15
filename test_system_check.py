"""Deterministic pure diagnosis and bounded local-adapter tests; no live services."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import estado_app
import system_check as core
import system_check_local as local

NOW = "2026-11-14T12:00:00Z"


def fact(field, value, origin="MEASURED", stamp=NOW):
    return core.Observation(value, core.SOURCES.get(field, "host.service_witness:"+field), stamp, origin)


def snapshot():
    return {"os": fact("os", "Linux"), "architecture": fact("architecture", "x86_64"),
            "python": fact("python", [3, 10, 0]), "auxiliary_python": fact("auxiliary_python", False),
            "sqlite": fact("sqlite", True), "cpu_logical": fact("cpu_logical", 2),
            "memory_available_bytes": fact("memory_available_bytes", 1024),
            "disk_free_bytes": fact("disk_free_bytes", 4096), "models": fact("models", []),
            "internet": fact("internet", False), "privacy_preview": fact("privacy_preview", True)}


class PureDiagnosis(unittest.TestCase):
    def setUp(self):
        self.facts = snapshot()

    def check(self):
        return core.diagnose(self.facts, NOW)

    def test_zero_models_still_useful(self):
        r = self.check()
        self.assertEqual(r["state"], "LOCAL")
        self.assertEqual(r["facts"]["models"]["value"], [])
        self.assertIn("review_diagnosis", r["offline_actions"])
        self.assertIn("review_privacy_rules", r["offline_actions"])

    def test_no_internet_does_not_disable_local_tools(self):
        r = self.check()
        self.assertFalse(r["facts"]["internet"]["value"])
        self.assertEqual(r["state"], "LOCAL")
        self.assertIn("review_requirements", r["local_capabilities"])

    def test_missing_auxiliary_python_not_embedded_runtime(self):
        r = self.check()
        self.assertEqual(r["requirements"]["auxiliary_python"]["cause"], "auxiliary_python_absent")
        self.assertEqual(r["state"], "LOCAL")

    def test_missing_embedded_runtime_is_unknown(self):
        del self.facts["python"]
        self.assertEqual(self.check()["state"], "UNKNOWN")

    def test_unsupported_python(self):
        self.facts["python"] = fact("python", [3, 9, 9])
        self.assertEqual(self.check()["requirements"]["python"]["cause"], "python_unsupported")
        self.assertEqual(self.check()["state"], "UNKNOWN")

    def test_sqlite_absent_does_not_prevent_diagnosis(self):
        self.facts["sqlite"] = fact("sqlite", False)
        r = self.check()
        self.assertEqual(r["requirements"]["sqlite"]["cause"], "dependency_missing")
        self.assertEqual(r["state"], "LOCAL")
        self.assertNotIn("memory.write", r["local_capabilities"])

    def test_partial_hardware_never_fabricates_zero(self):
        del self.facts["memory_available_bytes"]
        self.facts["cpu_logical"] = fact("cpu_logical", 0)
        r = self.check()
        self.assertEqual(r["facts"]["memory_available_bytes"]["state"], "NO_DATA")
        self.assertEqual(r["facts"]["cpu_logical"]["state"], "NO_DATA")
        self.assertEqual(r["facts"]["disk_free_bytes"]["value"], 4096)
        self.assertEqual(r["state"], "LOCAL")

    def test_expired_data(self):
        self.facts["models"] = fact("models", ["fixture:v1"], stamp="2026-11-14T11:57:59Z")
        r = self.check()
        self.assertEqual(r["facts"]["models"]["cause"], "evidence_expired")
        self.assertEqual(r["facts"]["models"]["freshness"], "STALE")
        self.assertNotIn("inspect_model_files", r["offline_actions"])

    def test_expired_runtime_no_local_promotion(self):
        self.facts["python"] = fact("python", [3, 10, 0], stamp="2026-11-14T11:57:59Z")
        self.assertEqual(self.check()["state"], "UNKNOWN")

    def test_exact_ttl_boundary(self):
        self.facts["python"] = fact("python", [3, 10, 0], stamp="2026-11-14T11:58:00Z")
        self.assertEqual(self.check()["state"], "LOCAL")

    def test_future_data(self):
        self.facts["cpu_logical"] = fact("cpu_logical", 8, stamp="2026-11-14T12:00:01Z")
        self.assertEqual(self.check()["facts"]["cpu_logical"]["cause"], "evidence_future")

    def test_declared_and_simulated_runtime_never_ready(self):
        for origin in ("DECLARED", "SIMULATED"):
            self.facts["python"] = fact("python", [3, 10, 0], origin)
            r = self.check()
            self.assertEqual(r["state"], "UNKNOWN")
            self.assertEqual(r["facts"]["python"]["state"], origin)

    def test_declared_service_is_not_connected(self):
        self.facts["services"] = {"model_engine": fact("model_engine", True, "DECLARED")}
        r = self.check()
        self.assertEqual(r["state"], "LOCAL")
        self.assertEqual(r["services"]["model_engine"]["state"], "DECLARED")

    def test_unreachable_service_has_cause(self):
        self.facts["services"] = {"model_engine": fact("model_engine", False)}
        r = self.check()
        self.assertEqual(r["services"]["model_engine"]["cause"], "service_unreachable")
        self.assertEqual(r["state"], "LOCAL")

    def test_verified_service_connection_is_not_internet(self):
        self.facts["services"] = {"tool_transport": fact("tool_transport", True)}
        r = self.check()
        self.assertEqual(r["state"], "CONNECTED")
        self.assertFalse(r["facts"]["internet"]["value"])
        self.assertEqual(r["authority"], "NOT_AUTHORIZED")

    def test_expired_service_not_connected(self):
        self.facts["services"] = {"tool_transport": fact("tool_transport", True, stamp="2026-11-14T11:57:59Z")}
        self.assertEqual(self.check()["state"], "LOCAL")

    def test_unknown_service_not_absent(self):
        row = self.check()["services"]["remote_provider"]
        self.assertEqual(row["state"], "NO_DATA")
        self.assertEqual(row["cause"], "service_not_probed")
        self.assertNotIn("value", row)

    def test_status_has_source_and_freshness(self):
        r = self.check()
        self.assertEqual(r["status_evidence"]["freshness"], "FRESH")
        self.assertEqual(r["status_evidence"]["observed_at"], NOW)
        self.assertEqual(r["status_evidence"]["inputs"][0]["source"], "host.runtime")

    def test_source_mismatch(self):
        self.facts["os"] = replace(self.facts["os"], source="model.prose")
        self.assertEqual(self.check()["facts"]["os"]["cause"], "source_mismatch")

    def test_booleans_are_not_resource_numbers(self):
        for field in ("cpu_logical", "memory_available_bytes", "disk_free_bytes"):
            self.facts[field] = fact(field, True)
            self.assertEqual(self.check()["facts"][field]["state"], "NO_DATA")

    def test_zero_free_memory_and_disk_are_measured(self):
        for field in ("memory_available_bytes", "disk_free_bytes"):
            self.facts[field] = fact(field, 0)
            self.assertEqual(self.check()["facts"][field]["value"], 0)

    def test_invalid_model_labels_and_duplicates(self):
        for models in (["<script>"], ["../private"], ["fixture:v1"]*2, ["fixture:v1"]*65):
            self.facts["models"] = fact("models", models)
            self.assertEqual(self.check()["facts"]["models"]["state"], "NO_DATA")

    def test_untrusted_dict_not_observation(self):
        self.facts["python"] = {"value": [3, 10, 0], "verified": True}
        self.assertEqual(self.check()["state"], "UNKNOWN")

    def test_closed_input(self):
        for field in ("command", "install", "url", "execute", "path", "verified"):
            r = core.diagnose(dict(self.facts, **{field: "untrusted"}), NOW)
            self.assertEqual(r["cause"], "input_invalid")

    def test_unknown_service_schema(self):
        self.facts["services"] = {"invented": fact("model_engine", True)}
        self.assertEqual(self.check()["cause"], "input_invalid")

    def test_input_byte_bound(self):
        self.facts["os"] = fact("os", "x"*core.MAX_INPUT)
        self.assertEqual(self.check()["cause"], "input_limit_exceeded")

    def test_invalid_clock_and_non_json(self):
        self.assertEqual(core.diagnose(self.facts, "no clock")["cause"], "input_invalid")
        self.facts["cpu_logical"] = fact("cpu_logical", float("nan"))
        self.assertEqual(self.check()["cause"], "input_invalid")

    def test_no_mutation_and_deterministic_digest(self):
        before = deepcopy(self.facts)
        first, second = self.check(), self.check()
        self.assertEqual(core.canonical(first), core.canonical(second))
        self.assertEqual(self.facts, before)
        self.assertEqual(first.pop("projection_ref"), "sha256:"+core.fingerprint(first))

    def test_pure_core_has_no_io(self):
        with patch("builtins.open", side_effect=AssertionError("I/O")), \
             patch("subprocess.Popen", side_effect=AssertionError("process")), \
             patch("socket.socket", side_effect=AssertionError("network")):
            self.assertEqual(self.check()["state"], "LOCAL")

    def test_shared_harness_surface_uses_existing_contract(self):
        r = self.check()
        view = core.harness_surface(r)
        self.assertEqual(view["projection_ref"], r["projection_ref"])
        self.assertEqual(view["state"], r["state"])
        surface = view["surface"]
        self.assertEqual(surface["zona"], "harness")
        self.assertIsNone(surface["tick"])
        self.assertEqual(surface["frescura"]["estado"], "NO_DATA")
        self.assertLessEqual(len(estado_app.serializar(surface)), 1024)

    def test_tampered_report_cannot_get_surface(self):
        r = self.check()
        r["state"] = "CONNECTED"
        with self.assertRaises(ValueError):
            core.harness_surface(r)

    def test_first_use_is_not_clean_install_metric(self):
        r = core.first_use_metric(100, 900, True)
        self.assertEqual(r["elapsed_ns"], 800)
        self.assertEqual(r["scope"], "check_to_local_report_not_installation")
        self.assertEqual(self.check()["first_use"]["cause"], "first_use_not_measured")
        self.assertEqual(core.first_use_metric(900, 100, True)["state"], "NO_DATA")
        self.assertEqual(core.first_use_metric(100, 900, False)["cause"], "operation_not_completed")


class CatalogueReuse(unittest.TestCase):
    def test_missing_catalogue_is_not_zero(self):
        row = core.console_models({"estado": "NO_DATA", "modelos": []}, NOW)
        self.assertEqual(row.origin, "NO_DATA")

    def test_known_empty_store(self):
        row = core.console_models({"estado": "MEDIDO", "modelos": [], "total": 0}, NOW)
        self.assertEqual(row.origin, "MEASURED")
        self.assertEqual(row.value, [])

    def test_only_present_blobs_are_installed_files(self):
        row = core.console_models({"estado": "MEDIDO", "modelos": [
            {"id": "fixture:v1", "blob_presente": True, "sha256": "a"*64, "bytes": 3},
            {"id": "missing:v1", "blob_presente": False}], "total": 2}, NOW)
        self.assertEqual(row.value, ["fixture:v1"])

    def test_broken_and_partial_catalogues(self):
        for catalogue in ({"estado": "MEDIDO", "modelos": [], "total": 1},
                          {"estado": "MEDIDO", "modelos": [{"id": "fixture:v1", "error": "private exception"}], "total": 1}):
            row = core.console_models(catalogue, NOW)
            self.assertEqual(row.cause, "model_inventory_partial")
            self.assertNotIn("private", repr(row))

    def test_declared_manifest_never_detected(self):
        row = core.console_models({"estado": "DECLARADO", "modelos": [{"id": "fixture:v1"}], "total": 1}, NOW)
        self.assertEqual(row.origin, "NO_DATA")

    def test_real_existing_reader_with_synthetic_store(self):
        import consola
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/"manifests"/"registry.ollama.ai"/"library"/"fixture"/"v1"
            manifest.parent.mkdir(parents=True)
            blobs = root/"blobs"
            blobs.mkdir()
            digest = "a"*64
            manifest.write_text(json.dumps({"layers": [{"mediaType": "application/vnd.ollama.image.model",
                "digest": "sha256:"+digest, "size": 3}]}))
            (blobs/("sha256-"+digest)).write_bytes(b"123")
            catalogue = consola.modelos_pc(root, visible=lambda _: "fixture-store")
            row = core.console_models(catalogue, NOW)
            self.assertEqual(row.value, ["fixture:v1"])
            (blobs/("sha256-"+digest)).unlink()
            row = core.console_models(consola.modelos_pc(root, visible=lambda _: "fixture-store"), NOW)
            self.assertEqual(row.value, [])


class LocalAdapter(unittest.TestCase):
    def test_offline_without_auxiliary_python_or_models(self):
        with patch("shutil.which", return_value=None), \
             patch("socket.socket", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("subprocess")):
            report = local.run_check(model_reader=lambda: {"estado": "MEDIDO", "modelos": [], "total": 0})
        self.assertEqual(report["state"], "LOCAL")
        self.assertFalse(report["facts"]["auxiliary_python"]["value"])
        self.assertEqual(report["facts"]["internet"]["cause"], "connectivity_not_measured")
        self.assertEqual(report["first_use"]["state"], "MEASURED")
        self.assertEqual(report["facts"]["models"]["value"], [])

    def test_local_catalogue_paths_are_not_echoed(self):
        report = local.run_check(model_reader=lambda: {"estado": "NO_DATA", "causa": "/private/fixture/path", "modelos": []})
        self.assertNotIn("/private/", json.dumps(report))

    def test_model_reader_failure_is_bounded(self):
        def broken():
            raise OSError("private exception text")
        report = local.run_check(model_reader=broken)
        self.assertEqual(report["facts"]["models"]["cause"], "model_inventory_unavailable")
        self.assertNotIn("private exception", json.dumps(report))

    def test_hardware_probe_failure_still_reports_other_fields(self):
        with patch.object(local, "_memory_available", side_effect=PermissionError("private")):
            r = local.run_check(model_reader=lambda: {})
        self.assertEqual(r["facts"]["memory_available_bytes"]["state"], "NO_DATA")
        self.assertEqual(r["facts"]["os"]["state"], "MEASURED")

    def test_non_linux_memory_abstains(self):
        with patch.object(local.sys, "platform", "darwin"):
            with self.assertRaises(OSError):
                local._memory_available()

    def test_memory_reader_is_bounded(self):
        with patch("builtins.open", return_value=io.BytesIO(b"x"*16385)):
            with self.assertRaises(ValueError):
                local._memory_available()

    def test_memory_available_not_total(self):
        with patch("builtins.open", return_value=io.BytesIO(b"MemTotal: 99 kB\nMemAvailable: 5 kB\n")):
            self.assertEqual(local._memory_available(), 5120)

    def test_no_implicit_policy_creation(self):
        import consola
        import guardrails
        with patch.object(guardrails, "ruta_politicas", side_effect=AssertionError("policy write")), \
             patch.object(consola, "raiz_ollama", return_value=Path("/fixture-does-not-exist")):
            r = local.run_check()
        self.assertEqual(r["state"], "LOCAL")
        self.assertEqual(r["facts"]["models"]["state"], "NO_DATA")

    def test_import_is_not_collection(self):
        import ast
        tree = ast.parse(Path(local.__file__).read_text())
        calls = [n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
