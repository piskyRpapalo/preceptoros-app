"""The chat takes an agent voice only from a loopback CLI with no Origin, never the person's."""
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "bin" / "preceptoros-pwa").read_text(encoding="utf-8")
_PWA = None


def _load_pwa():
    """The server module, loaded once the same way test_pwa does it."""
    global _PWA
    if _PWA is None:
        import importlib.util, sys
        from importlib.machinery import SourceFileLoader
        aqui = Path(__file__).resolve().parent
        sys.path.insert(0, str(aqui))
        ruta = str(aqui / "bin" / "preceptoros-pwa")
        spec = importlib.util.spec_from_loader("preceptoros_pwa_voice", SourceFileLoader("preceptoros_pwa_voice", ruta))
        _PWA = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_PWA)
    return _PWA


class AgentVoice(unittest.TestCase):
    def test_allowlist_and_never_soberano(self):
        self.assertIn('AGENT_VOICES = frozenset({"claude", "codex", "gemini", "mistral"})', SRC)
        self.assertNotIn('"soberano"', SRC.split("AGENT_VOICES = ")[1].split("\n")[0])

    def test_agent_path_uses_di_and_needs_loopback_without_origin(self):
        bloque = SRC[SRC.index('voz = data.get("voz")'):SRC.index('return no_data("agent_voice_refused", 403)')]
        self.assertIn("_canales.di(\"cli\", voz", bloque)   # 2026-11-12: agents ask in their own thread
        self.assertIn("self._es_loopback(self.client_address[0])", bloque)
        self.assertIn('not self.headers.get("Origin")', bloque)

    def test_canales_refuses_soberano_voice(self):
        import canales
        with self.assertRaises(canales.CanalRechazado):
            canales.di("orquesta", "soberano", "x")


if __name__ == "__main__":
    unittest.main()


class TestAgentVoiceDoorLive(unittest.TestCase):
    """The door, walked through the real handler (not only read in the source): the CLI agent gets in."""

    def _walk(self, body, ip="127.0.0.1", origin=None, persona=False):
        import io, json
        from types import SimpleNamespace
        from unittest import mock
        PWA = _load_pwa()
        payload = json.dumps(body, ensure_ascii=False).encode()
        h = PWA.PWA.__new__(PWA.PWA)
        h.path = "/api/hexelion/chat"
        h.headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
        if origin:
            h.headers["Origin"] = origin
        h.rfile = io.BytesIO(payload)
        h.client_address = (ip, 50000)
        h.server = SimpleNamespace(ruta_db="unused")
        got = {}
        h._json = lambda code, b: got.update(code=code, body=b)
        h._nodo_local_autorizado = lambda: persona
        empty = {"esquema": "preceptoros.memory-search/1", "estado": "NO_DATA", "causa": "no_match", "fuentes": []}
        with mock.patch.object(PWA._casa, "raiz", return_value="unused"), \
             mock.patch.object(PWA._canales, "di_soberano") as person, \
             mock.patch.object(PWA._canales, "di") as agent, \
             mock.patch.object(PWA._memory_lookup, "buscar", return_value=empty), \
             mock.patch.object(PWA._indice_rack, "buscar", return_value=empty), \
             mock.patch.object(PWA._hexelion_proxy, "ask") as ask:
            PWA.PWA._hexelion_chat(h)
        return got, person, agent, ask

    def test_cli_agent_with_voice_gets_in_and_speaks_as_itself(self):
        got, person, agent, _ = self._walk({"texto": "caravan states", "voz": "claude"})
        self.assertNotEqual(got.get("body", {}).get("causa"), "local_origin_required", got)
        person.assert_not_called()
        self.assertEqual(agent.call_args.args[:3], ("cli", "claude", "caravan states"))   # own thread since 2026-11-12

    def test_cli_without_voice_never_speaks_as_the_person(self):
        got, person, agent, _ = self._walk({"texto": "hola"})
        self.assertEqual((got["code"], got["body"]["causa"]), (403, "local_origin_required"))
        person.assert_not_called(); agent.assert_not_called()

    def test_remote_caller_is_refused_before_the_body(self):
        got, person, agent, _ = self._walk({"texto": "hola", "voz": "claude"}, ip="203.0.113.9")
        self.assertEqual((got["code"], got["body"]["causa"]), (403, "local_origin_required"))
        person.assert_not_called(); agent.assert_not_called()

    def test_the_window_still_speaks_as_the_person(self):
        got, person, agent, _ = self._walk({"texto": "hola"}, origin="http://127.0.0.1:8742", persona=True)
        person.assert_called_once()
        agent.assert_not_called()

    def test_a_window_cannot_borrow_an_agent_voice(self):
        got, person, agent, _ = self._walk({"texto": "hola", "voz": "claude"}, origin="http://127.0.0.1:8742", persona=True)
        self.assertEqual((got["code"], got["body"]["causa"]), (403, "agent_voice_refused"))
        person.assert_not_called(); agent.assert_not_called()


class TestPrivateTalkServe(unittest.TestCase):
    origin = "https://app.fixture.ts.net"
    owner = "owner@example.test"

    def walk(self, body=None, *, bound="127.0.0.1", peer="127.0.0.1",
             login=(owner,), origin=origin, host="app.fixture.ts.net", proto="https",
             forwarded_host="app.fixture.ts.net", funnel=None, configured=True, station=None,
             site=None, route="/api/hexelion/chat", method="POST"):
        import io
        import json
        from email.message import Message
        from types import SimpleNamespace
        from unittest import mock

        pwa = _load_pwa()
        handler = pwa.PWA.__new__(pwa.PWA)
        handler.path = route
        handler.headers = Message()
        for name, value in (("Host", host), ("Origin", origin), ("X-Forwarded-Proto", proto),
                            ("X-Forwarded-Host", forwarded_host), ("Tailscale-Funnel-Request", funnel),
                            ("Sec-Fetch-Site", site)):
            if value is not None:
                handler.headers[name] = value
        for value in login:
            handler.headers["Tailscale-User-Login"] = value
        raw = json.dumps(body if body is not None else {"texto": "¿Qué dice el archivo?"}).encode()
        handler.headers["Content-Type"] = "application/json"
        handler.headers["Content-Length"] = str(len(raw))
        handler.rfile = io.BytesIO(raw)
        handler.client_address = (peer, 50000)
        handler.server = SimpleNamespace(server_address=(bound, 8742), server_port=8742, ruta_db="unused")
        captured = {}
        handler._json = lambda code, payload: captured.update(code=code, body=payload)
        handler._conversacion_leer = lambda: handler._json(200, {"state": "fixture_history"})
        env = {"PRECEPTOROS_HEXELION_SERVE_ORIGIN": self.origin if configured else "",
               "PRECEPTOROS_HEXELION_SERVE_OWNER": self.owner if configured else ""}
        evidence = {"esquema": "preceptoros.memory-search/1", "estado": "NO_DATA",
                    "causa": "no_match", "fuentes": []}
        prepared = ({"estado": "MEASURED", "fuentes": []}, "fixture prompt")
        with mock.patch.dict("os.environ", env), \
             mock.patch.object(pwa._casa, "raiz", return_value="unused"), \
             mock.patch.object(pwa._canales, "di_soberano", return_value=None) as person, \
             mock.patch.object(pwa._memory_lookup, "buscar", return_value=evidence), \
             mock.patch.object(pwa._indice_rack, "buscar", return_value=evidence), \
             mock.patch.object(pwa._hexelion_book, "construir_prompt", return_value=prepared), \
             mock.patch.object(pwa._hexelion_book, "formato_citas", return_value=None), \
             mock.patch.object(pwa._hexelion_proxy, "ask", return_value=station) as ask, \
             mock.patch.object(pwa._hexelion_acciones, "ejecuta") as action:
            if method == "GET":
                handler.do_GET()
            else:
                handler.do_POST()
        action.assert_not_called()
        return captured, handler.rfile.tell(), person, ask

    def test_missing_transport_config_is_no_data_before_reading(self):
        for case in ({"configured": False}, {"bound": "0.0.0.0"}, {"peer": "192.0.2.1"}):
            with self.subTest(case=case):
                got, read, person, ask = self.walk(**case)
                self.assertEqual((got["code"], got["body"]["stage"], read), (503, "connection", 0))
                person.assert_not_called()
                ask.assert_not_called()

    def test_wrong_identity_or_origin_is_refused_before_reading(self):
        for case in ({"login": ()}, {"login": ("visitor@example.test",)},
                     {"login": (self.owner, self.owner)}, {"origin": None},
                     {"origin": "https://visitor.example.test"}, {"host": "127.0.0.1:8742"},
                     {"proto": "http"}, {"funnel": "?1"}, {"forwarded_host": None}):
            with self.subTest(case=case):
                got, read, person, ask = self.walk(**case)
                self.assertEqual((got["code"], got["body"]["stage"], read), (403, "authentication", 0))
                person.assert_not_called()
                ask.assert_not_called()

    def test_private_talk_rejects_agent_voice_and_actions(self):
        for body in ({"texto": "Hola", "voz": "codex"}, {"texto": "/estado"},
                     {"texto": "¿cómo está el rack?"}):
            with self.subTest(body=body):
                got, _, person, ask = self.walk(body)
                self.assertEqual((got["code"], got["body"]["causa"]),
                                 (403, "private_talk_conversation_only"))
                person.assert_not_called()
                ask.assert_not_called()

    def test_authenticated_turn_distinguishes_station_connection_and_model(self):
        for cause, stage in (("station_unavailable", "connection"),
                             ("station_model_unavailable", "model")):
            with self.subTest(cause=cause):
                got, _, person, ask = self.walk(station={"estado": "NO_DATA", "causa": cause})
                self.assertEqual((got["code"], got["body"]["stage"], got["body"]["causa"]),
                                 (503, stage, cause))
                person.assert_called_once_with("orquesta", "¿Qué dice el archivo?", base="unused")
                ask.assert_called_once_with("fixture prompt")

    def test_serve_history_requires_owner_even_without_origin(self):
        for path in ("/api/conversacion", "/api/canales?canal=orquesta", "/api/notebook", "/api/lab"):
            with self.subTest(path=path):
                got, read, person, ask = self.walk(route=path, method="GET", origin=None, login=())
                self.assertEqual((got["code"], got["body"]["causa"], read),
                                 (403, "private_talk_owner_auth_required", 0))
                person.assert_not_called()
                ask.assert_not_called()
        got, _, _, _ = self.walk(route="/api/conversacion", method="GET", origin=None, site="same-origin")
        self.assertEqual((got["code"], got["body"]["state"]), (200, "fixture_history"))
        got, _, _, _ = self.walk(route="/api/conversacion", method="GET", origin=None, site="cross-site")
        self.assertEqual(got["code"], 403)

    def test_serve_rejects_other_post_before_reading(self):
        for path in ("/api/charla", "/api/conversacion", "/api/nodo/identity", "/api/hitl/1"):
            with self.subTest(path=path):
                got, read, person, ask = self.walk(route=path)
                self.assertEqual((got["code"], got["body"]["causa"], read),
                                 (403, "private_talk_conversation_only", 0))
                person.assert_not_called()
                ask.assert_not_called()
