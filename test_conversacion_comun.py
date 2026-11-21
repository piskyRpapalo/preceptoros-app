"""APP-ROUTER-01 · one conversation, many preceptors: the projection, the addressed send, and the Talk wiring."""
from __future__ import annotations

import concurrent.futures
from contextlib import ExitStack
import datetime as dt
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import canales  # noqa: E402
import conversacion_comun as C  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)


def _pwa():
    loader = importlib.machinery.SourceFileLoader("preceptoros_pwa_router", str(ROOT / "bin" / "preceptoros-pwa"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


PWA = _pwa()


def reading(*msgs):
    return {"estado": "MEDIDO", "mensajes": [dict({"maquina": {}, "sello": "DECLARADO", "rol": ""}, **m) for m in msgs]}


class Projection(unittest.TestCase):
    def test_every_voice_gets_an_explicit_identity_and_kind(self):
        request_id = "app-" + "1" * 32
        r = reading({"n": 1, "t": "2026-11-12T11:00:00Z", "voz": "soberano", "texto": "hi",
                     "maquina": {"via": "app", "para": "claude", "request_id": request_id}},
                    {"n": 2, "t": "2026-11-12T11:01:00Z", "voz": "claude", "texto": "read it"},
                    {"n": 3, "t": "2026-11-12T11:02:00Z", "voz": "hexelion", "texto": "quote",
                     "maquina": {"modelo": "hexelion:latest", "fuentes": [{"id": 9, "updated_at": "2026-11-06T00:00:00Z", "sha256": "a" * 64}]}},
                    {"n": 4, "t": "2026-11-12T11:03:00Z", "voz": "orquestador", "texto": "Energy: 3 W"},
                    {"n": 5, "t": "2026-11-12T11:04:00Z", "voz": "stranger", "texto": "who am I"})
        p = C.project(r, NOW)
        self.assertEqual(p["schema"], "preceptoros.multipreceptor/1")
        self.assertEqual(p["state"], "MEASURED")
        self.assertEqual([(m["from"], m["kind"]) for m in p["messages"]],
                         [("soberano", "person"), ("claude", "rack-cli"), ("hexelion", "private"),
                          ("orquestador", "sensor"), ("stranger", "unknown")])
        self.assertEqual(p["messages"][0]["to"], "claude")
        self.assertEqual(p["messages"][0]["request_id"], request_id)
        self.assertEqual(p["authority"], "none: a message grants no permission and is not a signature")
        self.assertEqual(p["messages"][2]["sources"], ["#9 · 2026-11-06T00:00:00Z · aaaaaaaaaaaa"])
        self.assertEqual(p["messages"][2]["model"], "hexelion:latest")
        self.assertEqual(p["last"], 5)
        self.assertIn("not a signature", p["authority"])

    def test_since_limit_and_cut(self):
        r = reading(*[{"n": i, "t": "2026-11-12T11:00:00Z", "voz": "claude", "texto": "x" * (C.MAX_SHOWN + 5)} for i in range(1, 51)])
        p = C.project(r, NOW, since=5)
        self.assertEqual(len(p["messages"]), C.MAX_MESSAGES)
        self.assertEqual(p["hidden"], 45 - C.MAX_MESSAGES)
        self.assertEqual(p["messages"][-1]["n"], 50)
        self.assertTrue(all(m["cut"] and len(m["text"]) == C.MAX_SHOWN for m in p["messages"]))
        self.assertEqual(C.project(r, NOW, since=50)["messages"], [])

    def test_unreadable_thread_is_no_data_with_cause_and_no_last_spoke(self):
        p = C.project({"estado": "NO_DATA", "causa": "channel_has_no_messages", "mensajes": []}, NOW)
        self.assertEqual((p["state"], p["cause"], p["messages"], p["last"]), ("NO_DATA", "channel_has_no_messages", [], 0))
        self.assertTrue(all(d["last_spoke"].startswith("NO_DATA") for d in p["destinations"]))
        self.assertEqual(C.project(None, NOW)["cause"], "thread_unreadable")

    def test_a_recipient_outside_the_table_is_not_shown_as_someone(self):
        r = reading({"n": 1, "t": "2026-11-12T11:00:00Z", "voz": "soberano", "texto": "x", "maquina": {"para": "root"}})
        self.assertNotIn("to", C.project(r, NOW)["messages"][0])

    def test_destinations_say_transport_and_last_spoke(self):
        r = reading({"n": 1, "t": "2026-11-12T11:59:00Z", "voz": "claude", "texto": "x"})
        d = {x["id"]: x for x in C.destinations(r, NOW)}
        self.assertEqual((d["claude"]["last_spoke"], d["claude"]["age_s"]), ("2026-11-12T11:59:00Z", 60))
        self.assertEqual(d["codex"]["last_spoke"], "NO_DATA: never spoke in this thread")
        for ext in ("chatgpt", "mistral-web", "codex-web"):
            self.assertFalse(d[ext]["addressable"])
            self.assertTrue(d[ext]["transport"].startswith("NO_DATA: "))
        self.assertEqual(d["hexelion"]["route"], "station")

    def test_rack_cli_table_is_the_server_voice_allowlist(self):
        rack = {d["id"] for d in C.DESTINATIONS if d["kind"] == "rack-cli"}
        self.assertEqual(rack, set(PWA.AGENT_VOICES))
        self.assertEqual(len({d["id"] for d in C.DESTINATIONS}), len(C.DESTINATIONS))
        self.assertNotIn("soberano", C.BY_ID)

    def test_same_input_same_output(self):
        r = reading({"n": 1, "t": "2026-11-12T11:00:00Z", "voz": "claude", "texto": "x"})
        self.assertEqual(json.dumps(C.project(r, NOW), sort_keys=True), json.dumps(C.project(r, NOW), sort_keys=True))


class Send(unittest.TestCase):
    def test_check_send(self):
        self.assertEqual(C.check_send({"para": "claude", "texto": "  hi  "}), ("claude", "hi", None))
        cases = [({"para": "chatgpt", "texto": "hi"}, "no_transport"), ({"para": "hexelion", "texto": "hi"}, "use_station_door"),
                 ({"para": "soberano", "texto": "hi"}, "recipient_unknown"), ({"para": "lab", "texto": "hi"}, "recipient_unknown"),
                 ({"para": "claude", "texto": " "}, "text_invalid"), ({"para": "claude", "texto": "x" * 601}, "text_invalid"),
                 ({"para": "claude", "texto": "hi", "voz": "claude"}, "request_invalid"), ([], "request_invalid"),
                 ({"para": 1, "texto": "hi"}, "recipient_unknown")]
        for data, cause in cases:
            self.assertEqual(C.check_send(data)[2], cause, data)

    def test_di_soberano_stores_the_recipient_and_refuses_bad_ones(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(canales, "_registro", return_value=None):
            m = canales.di_soberano("orquesta", "hola", base=tmp, para="claude")
            self.assertEqual((m["voz"], m["maquina"]), ("soberano", {"via": "app", "para": "claude"}))
            self.assertEqual(canales.di_soberano("orquesta", "sin destino", base=tmp)["maquina"], {"via": "app"})
            for bad in ("Soberano", "s0berano", "x y", 3):
                with self.assertRaises(canales.CanalRechazado):
                    canales.di_soberano("orquesta", "hola", base=tmp, para=bad)


class Door(unittest.TestCase):
    def call(self, method, path, body=None, local=True, loopback=True, tmp=None):
        raw = json.dumps(body).encode() if body is not None else b""
        h = PWA.PWA.__new__(PWA.PWA)
        h.path, h.command = path, method
        h.headers = {"Content-Type": "application/json", "Content-Length": str(len(raw))}
        h.rfile, h.client_address, h.server = io.BytesIO(raw), ("127.0.0.1" if loopback else "192.0.2.9", 1), SimpleNamespace()
        out = {}
        h._json = lambda code, b: out.update(code=code, body=b)
        h._nodo_local_autorizado = lambda: local
        with mock.patch.object(PWA._casa, "raiz", return_value=pathlib.Path(tmp)), \
             mock.patch.object(canales, "_registro", return_value=None):
            (PWA.PWA._conversacion_enviar if method == "POST" else PWA.PWA._conversacion_leer)(h)
        return out

    def test_addressed_send_lands_in_the_thread_and_reads_back_with_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent = self.call("POST", "/api/conversacion", {"para": "codex", "texto": "check LAB #172"}, tmp=tmp)
            self.assertEqual((sent["code"], sent["body"]["state"], sent["body"]["to"]), (200, "DELIVERED_TO_THREAD", "codex"))
            self.assertTrue(sent["body"]["reply"].startswith("PENDING"))
            self.assertRegex(sent["body"]["request_id"], r"^app-[0-9a-f]{32}$")
            canales.di("orquesta", "codex", "LAB #172 read", base=tmp)
            got = self.call("GET", "/api/conversacion?desde=0", tmp=tmp)["body"]
            self.assertEqual([(m["name"], m["kind"], m.get("to")) for m in got["messages"]],
                             [("You", "person", "codex"), ("Codex", "rack-cli", None)])
            self.assertEqual(got["messages"][0]["request_id"], sent["body"]["request_id"])
            since = self.call("GET", "/api/conversacion?desde=%d" % got["messages"][0]["n"], tmp=tmp)["body"]
            self.assertEqual([m["from"] for m in since["messages"]], ["codex"])

    def test_concurrent_same_recipient_requests_get_distinct_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.call("POST", "/api/conversacion", {"para": "codex", "texto": "first"}, tmp=tmp)
            b = self.call("POST", "/api/conversacion", {"para": "codex", "texto": "second"}, tmp=tmp)
            self.assertEqual((a["code"], b["code"]), (200, 200))
            self.assertNotEqual(a["body"]["request_id"], b["body"]["request_id"])
            messages = canales.lee("orquesta", base=tmp)["mensajes"]
            self.assertEqual([m["maquina"]["request_id"] for m in messages],
                             [a["body"]["request_id"], b["body"]["request_id"]])

    def test_refusals_write_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for body, local, code, cause in [({"para": "chatgpt", "texto": "x"}, True, 409, "no_transport"),
                                             ({"para": "hexelion", "texto": "x"}, True, 409, "use_station_door"),
                                             ({"para": "claude", "texto": "x"}, False, 403, "local_origin_required"),
                                             ({"para": "claude", "texto": "x", "sello": "FIRMADO"}, True, 400, "request_invalid")]:
                out = self.call("POST", "/api/conversacion", body, local=local, tmp=tmp)
                self.assertEqual((out["code"], out["body"]["cause"]), (code, cause), body)
            self.assertFalse((pathlib.Path(tmp) / "registro" / "eventos.db").exists())
            self.assertEqual(self.call("GET", "/api/conversacion", tmp=tmp)["body"]["state"], "NO_DATA")
            self.assertEqual(self.call("GET", "/api/conversacion", loopback=False, tmp=tmp)["code"], 403)
            self.assertEqual(self.call("GET", "/api/conversacion?desde=x", tmp=tmp)["code"], 400)


REQUEST = {"para": "codex", "texto": "first turn", "request_id": "app-" + "1" * 32}
ORIGIN = "http://127.0.0.1:32123"


class OwnerThreadIdempotency(unittest.TestCase):
    def setUp(self):
        context = ExitStack()
        self.addCleanup(context.close)
        self.base = pathlib.Path(context.enter_context(tempfile.TemporaryDirectory()))
        context.enter_context(mock.patch.object(PWA._casa, "raiz", return_value=self.base))
        context.enter_context(mock.patch.dict("os.environ", {"PRECEPTOROS_REGISTRO_PY": ""}))
        context.enter_context(mock.patch.object(canales.G, "POLICIES_PATH", canales.G.DEFECTO_PATH))

    def call(self, body=REQUEST, *, origin=ORIGIN, client="127.0.0.1", host="127.0.0.1:32123"):
        raw = json.dumps(body).encode()
        handler = PWA.PWA.__new__(PWA.PWA)
        handler.headers = {"Content-Type": "application/json", "Content-Length": str(len(raw)), "Host": host}
        if origin is not None:
            handler.headers["Origin"] = origin
        handler.rfile, handler.client_address = io.BytesIO(raw), (client, 1)
        handler.server = mock.Mock(server_port=32123)
        handler._json = lambda status, receipt: (status, receipt)
        return handler._conversacion_enviar()

    def history(self, hilo="orquesta"):
        return canales.lee(hilo, base=self.base)["mensajes"]

    def test_lost_ack_retry_after_another_turn(self):
        first = self.call()
        self.assertEqual(first[0], 200)
        canales.di("orquesta", "codex", "second turn", base=self.base)
        self.assertEqual(self.call(), first)
        self.assertEqual([row["texto"] for row in self.history()], ["first turn", "second turn"])
        self.assertEqual(first[1]["n"], self.history()[0]["n"])
        self.assertEqual(first[1]["state"], "DELIVERED_TO_THREAD")
        self.assertTrue(first[1]["reply"].startswith("PENDING"))

    def test_concurrent_retries_write_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
            acks = list(workers.map(lambda _: self.call(), range(8)))
        self.assertEqual([status for status, _ in acks], [200] * 8)
        self.assertTrue(all(ack == acks[0] for ack in acks))
        self.assertEqual(len(self.history()), 1)

    def test_request_id_is_bound_to_normalized_text_and_recipient(self):
        first = self.call()
        self.assertEqual(self.call(dict(REQUEST, texto=" first turn ")), first)
        for payload in (dict(REQUEST, texto="changed"), dict(REQUEST, para="claude")):
            self.assertEqual(self.call(payload), (409, {"state": "NO_DATA", "cause": "request_id_conflict"}))
        self.assertEqual(len(self.history()), 1)

    def test_different_original_texts_cannot_share_a_redacted_receipt(self):
        with mock.patch.object(canales.G, "redactar_salida",
                               side_effect=lambda value: ("[redacted]" if value.startswith("private-") else value, [])):
            first = self.call(dict(REQUEST, texto="private-a"))
            self.assertEqual(first[0], 200)
            self.assertEqual(self.call(dict(REQUEST, texto="private-b"))[0], 409)
        self.assertEqual([row["texto"] for row in self.history()], ["[redacted]"])

    def test_access_is_checked_before_receipt_lookup(self):
        self.assertEqual(self.call()[0], 200)
        with mock.patch.object(canales, "_solicitud_anterior") as lookup:
            for options in ({"origin": None}, {"origin": "https://visitor.invalid"},
                            {"host": "localhost:32123"}, {"client": "192.0.2.9"}):
                with self.subTest(options=options):
                    self.assertEqual(self.call(**options),
                                     (403, {"state": "NO_DATA", "cause": "local_origin_required"}))
            lookup.assert_not_called()
        self.assertEqual(len(self.history()), 1)

    def test_unknown_outcome_fails_closed_and_allows_later_reconciliation(self):
        first = self.call()
        with mock.patch.object(canales, "_solicitud_anterior", side_effect=sqlite3.OperationalError):
            self.assertEqual(self.call(), (503, {"state": "NO_DATA", "cause": "thread_append_refused"}))
        self.assertEqual(self.call(), first)
        self.assertEqual(len(self.history()), 1)

    def test_existing_thread_and_actor_scope(self):
        request_id = REQUEST["request_id"]
        canales.di_soberano("app", REQUEST["texto"], base=self.base, para="codex",
                            request_id=request_id, deduplicar=True)
        canales.di("orquesta", "observer", "different actor", base=self.base,
                   maquina={"via": "app", "request_id": request_id})
        self.assertEqual(self.call()[0], 200)
        self.assertEqual([row["voz"] for row in self.history()], ["observer", "soberano"])
        self.assertEqual(len(self.history("app")), 1)

    def test_legacy_post_and_legacy_id_collision(self):
        a = self.call({"para": "codex", "texto": "legacy"})
        b = self.call({"para": "codex", "texto": "legacy"})
        self.assertEqual((a[0], b[0]), (200, 200))
        self.assertNotEqual(a[1]["request_id"], b[1]["request_id"])
        self.assertEqual(self.call(dict(REQUEST, texto="legacy", request_id=a[1]["request_id"]))[0], 409)
        self.assertEqual(len(self.history()), 2)

    def test_invalid_id_is_refused_without_creating_a_database(self):
        for invalid in (None, 1, ["x"], "", "app-" + "1" * 32 + "\n"):
            self.assertEqual(self.call(dict(REQUEST, request_id=invalid)),
                             (400, {"state": "NO_DATA", "cause": "request_id_invalid"}))
        self.assertFalse(canales.ruta_canal(self.base).exists())

    def test_reuses_receipt_written_through_configured_registry_adapter(self):
        canales.di("orquesta", "observer", "existing registry", base=self.base)
        fixture = pathlib.Path(__file__).parent / "tests" / "fixtures" / "registry" / "registro.py"
        with mock.patch.dict("os.environ", {"PRECEPTOROS_REGISTRO_PY": str(fixture)}):
            registry = canales._registro().Registro
            with mock.patch.object(canales._registro(), "Registro", wraps=registry) as writer:
                first = self.call()
                self.assertEqual(first[0], 200)
                self.assertEqual(self.call(), first)
                writer.assert_called_once()
        self.assertEqual(len(self.history()), 2)


class Shell(unittest.TestCase):
    def test_talk_reads_the_thread_and_marks_its_own_drafts(self):
        html = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf-8")
        js = (ROOT / "interface/app.js").read_text(encoding="utf-8")
        conv = (ROOT / "interface/conversacion.js").read_text(encoding="utf-8")
        server = (ROOT / "bin/preceptoros-pwa").read_text(encoding="utf-8")
        self.assertIn('<script src="/conversacion.js?v=8"></script>', html)
        self.assertLess(html.index("/insertor.js?v=2"), html.index("/conversacion.js?v=8"))
        self.assertLess(html.index("/conversacion.js?v=8"), html.index("/app.js?v=57"))
        self.assertIn('"/conversacion.js?v=8"', sw)
        self.assertIn('"/conversacion.js": ("conversacion.js",', server)
        self.assertIn('"interface/conversacion.js"', (ROOT / "version.py").read_text(encoding="utf-8"))
        self.assertIn('id="conv-destinos"', html)
        self.assertIn('li.classList.add("local")', js)
        self.assertIn("sync({ replaceLocal: true })", js)
        self.assertIn("conversacion.routes()", js)
        self.assertNotRegex(conv, r"localStorage|sessionStorage|sendBeacon|innerHTML")
        self.assertLess(len(conv.encode()), 10240)

    def test_insertor_cases_pass(self):
        r = subprocess.run(["node", "--test", "tests/insertor_cases.cjs"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 127:
            self.skipTest("NO_DATA: node not installed")
        self.assertEqual(r.returncode, 0, r.stdout[-800:])


if __name__ == "__main__":
    unittest.main()
