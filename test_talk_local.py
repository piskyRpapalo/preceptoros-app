"""APP-TALK-LOCAL-01 · local model routing, fail-closed receipts, no tools."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import memory
import test_pwa as P


class LocalTalk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "memory.db"
        memory.crear(str(self.db))
        self.base = self.root / "base.gguf"
        self.base.write_bytes(b"base fixture")
        self.fine = self.root / "fine.gguf"
        self.fine.write_bytes(b"fine fixture")
        with memory.abrir(str(self.db)) as c:
            memory.escribir_perfil(c, "captura", "no")
        self.patch_home = mock.patch.object(P.PWA._casa, "raiz", return_value=self.root)
        self.patch_home.start()
        self.h = P.PWA.PWA.__new__(P.PWA.PWA)
        self.h.server = SimpleNamespace(ruta_db=str(self.db), modelo=str(self.base))
        self.h.path = "/api/charla"
        self.h.codigo = None
        self.h.cuerpo = None
        self.h._json = lambda code, body: (setattr(self.h, "codigo", code), setattr(self.h, "cuerpo", body))

    def tearDown(self):
        self.patch_home.stop()
        self.tmp.cleanup()

    def _fake_turn(self, *args, **kwargs):
        return {"texto": "synthetic fixture reply", "ms_motor": 12.5,
                "id_salida": 9, "rastro": None}

    def _run_turn(self):
        P.PWA.PWA._turno(self.h, {"texto": "hello"})
        return self.h.codigo, self.h.cuerpo

    def test_selected_base_and_finetuned_are_the_models_in_each_turn_receipt(self):
        P.PWA._afinado.promover(self.root, self.fine, "fixture-v1")
        for selected, expected_name in (("afinado", self.fine.name), ("base", self.base.name)):
            if selected == "base":
                P.PWA._afinado.rollback(self.root, "fixture choice")
            motor = mock.Mock(return_value="synthetic fixture reply")
            with mock.patch.object(P.PWA._charla, "motor_llama", return_value=motor) as factory, \
                 mock.patch.object(P.PWA._charla, "turno", side_effect=self._fake_turn), \
                 mock.patch.object(P.PWA._cara, "progreso_camino", return_value={}):
                code, body = self._run_turn()
            self.assertEqual(code, 200)
            self.assertEqual(body["estado"], "ok")
            self.assertEqual(body["modelo"]["nombre"], expected_name)
            self.assertEqual(os.path.basename(factory.call_args.args[0]), expected_name)
            self.assertEqual(body["id_salida"], 9)
            self.assertNotEqual(body["estado"], "MEASURED")
            self.assertNotIn("fuentes", body)
            self.assertNotIn("herramientas", body)

    def test_invalid_finetuned_digest_is_rejected_without_running_either_model(self):
        P.PWA._afinado.promover(self.root, self.fine, "fixture-v1")
        self.fine.write_bytes(b"tampered fixture")
        with mock.patch.object(P.PWA._charla, "motor_llama") as factory:
            code, body = self._run_turn()
        self.assertEqual(code, 409)
        self.assertEqual(body["estado"], "NO_DATA")
        self.assertEqual(body["causa"], "selected_model_integrity_failed")
        factory.assert_not_called()

    def test_malformed_registry_and_path_escape_are_rejected(self):
        registry = self.root / P.PWA._afinado.NOMBRE_REGISTRO
        registry.write_text('{"afinado": []}', encoding="utf-8")
        with mock.patch.object(P.PWA._charla, "motor_llama") as factory:
            code, body = self._run_turn()
        self.assertEqual((code, body["causa"]), (409, "model_registry_invalid"))
        factory.assert_not_called()
        P.PWA._afinado.escribir_registro(self.root, {
            "afinado": {"destino": "../outside.gguf", "sha256": "a" * 64}})
        with mock.patch.object(P.PWA._charla, "motor_llama") as factory:
            code, body = self._run_turn()
        self.assertEqual((code, body["causa"]), (409, "selected_model_integrity_failed"))
        factory.assert_not_called()

    def test_missing_model_or_runtime_is_an_explicit_no_data(self):
        for model_path, available, cause in (
            (str(self.root / "missing.gguf"), None, "sin_nada"),
            (str(self.base), None, "sin_binario"),
        ):
            self.h.server.modelo = model_path
            with mock.patch.object(P.PWA._charla, "motor_llama", return_value=None), \
                 mock.patch.object(P.PWA._charla, "diagnostico", return_value=(None, cause)):
                code, body = self._run_turn()
            self.assertEqual(code, 503)
            self.assertEqual(body["estado"], "NO_DATA")
            self.assertEqual(body["causa"], cause)

    def test_unknown_memory_is_byte_identical_after_refusal(self):
        unknown = self.root / "unknown-memory.db"
        original = b"not an initialized PreceptorOS database\x00\xff"
        unknown.write_bytes(original)
        self.h.server.ruta_db = str(unknown)
        with mock.patch.object(P.PWA._charla, "motor_llama") as factory:
            code, body = self._run_turn()
        self.assertEqual(code, 503)
        self.assertEqual(body["estado"], "NO_DATA")
        self.assertEqual(unknown.read_bytes(), original)
        factory.assert_not_called()

    def test_existing_turn_consent_is_unchanged(self):
        import captura
        P.PWA._afinado.promover(self.root, self.fine, "fixture-v1")
        with memory.abrir(str(self.db)) as c:
            captura.asegurar(c)
            cur = c.execute("insert into turnos (prompt, respuesta, modelo, idioma, consent) values (?, ?, ?, ?, ?)",
                            ("old", "old", "base", "en", 1))
            prior_id = cur.lastrowid
        with mock.patch.object(P.PWA._charla, "motor_llama", return_value=mock.Mock()), \
             mock.patch.object(P.PWA._charla, "turno", side_effect=self._fake_turn), \
             mock.patch.object(P.PWA._cara, "progreso_camino", return_value={}):
            code, _ = self._run_turn()
        self.assertEqual(code, 200)
        with memory.abrir(str(self.db)) as c:
            row = c.execute("select consent from turnos where id=?", (prior_id,)).fetchone()
        self.assertEqual(row["consent"], 1)

    def test_talk_mode_is_server_derived_and_unknown_mode_is_not_a_client_choice(self):
        with mock.patch.dict(os.environ, {P.PWA._hexelion_proxy.ENDPOINT_ENV: ""}):
            local = P.PWA._cerebro_paquete(str(self.base))
        with mock.patch.dict(os.environ, {P.PWA._hexelion_proxy.ENDPOINT_ENV: "http://127.0.0.1:11434"}):
            private = P.PWA._cerebro_paquete(str(self.base))
        self.assertEqual(local["talk_mode"], "local_gguf")
        self.assertEqual(private["talk_mode"], "private_hexelion")


if __name__ == "__main__":
    unittest.main()
