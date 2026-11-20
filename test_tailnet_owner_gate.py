"""Synthetic Tailscale Serve owner-model-chat acceptance and negative gates.

No tailnet, device, key, real owner, model or MCP action is touched.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import tailnet_owner_gate as G

HOST = "rack.example-tail.ts.net"
OWNER = "owner@example.invalid"
ORIGIN = "https://" + HOST

def headers(**overrides):
    value = {
        "Host": HOST, "Origin": ORIGIN,
        "Tailscale-User-Login": OWNER, "Sec-Fetch-Site": "same-origin",
        "Content-Type": "application/json",
    }
    value.update(overrides)
    return value


class PureOwnerGate(unittest.TestCase):
    def ask(self, h=None, peer="127.0.0.1", host=HOST, login=OWNER, bind="127.0.0.1"):
        return G.authorize(h if h is not None else headers(), peer,
                           host=host, owner_login=login, backend_bind=bind)

    def test_exact_owner_browser_through_loopback_proxy(self):
        self.assertEqual(self.ask(), (True, "serve_identity_header_matches_owner_config"))
        self.assertTrue(self.ask(peer="::1", bind="::1")[0])

    def test_default_off_without_private_owner_config(self):
        for host, login in ((None, None), ("", OWNER), (HOST, None),
                            ("somewhere.invalid", OWNER), (HOST, "")):
            with self.subTest(host=host, login=bool(login)):
                self.assertFalse(self.ask(host=host, login=login)[0])

    def test_remote_lan_and_wildcard_listener_denied(self):
        for peer, bind in (("192.0.2.1", "127.0.0.1"),
                           ("100.64.0.10", "127.0.0.1"),
                           ("127.0.0.1", "0.0.0.0"),
                           ("127.0.0.1", "192.0.2.1"),
                           ("bad-ip", "::1")):
            with self.subTest(peer=peer, bind=bind):
                self.assertFalse(self.ask(peer=peer, bind=bind)[0])

    def test_refuse_forged_or_missing_login(self):
        for login in ("other@example.invalid", None, "", "owner@example.invalid\nOther: yes"):
            with self.subTest(login=bool(login)):
                self.assertFalse(self.ask(h=headers(**{"Tailscale-User-Login": login}))[0])

    def test_origin_and_cross_site_rejections(self):
        for header, value in (
            ("Origin", "https://someone-else.example-tail.ts.net"),
            ("Origin", "http://" + HOST),
            ("Origin", "null"),
            ("Origin", None),
            ("Host", "evil.example-tail.ts.net"),
            ("Host", HOST + ":443"),
            ("Sec-Fetch-Site", "cross-site"),
            ("Sec-Fetch-Site", None),
            ("Sec-Fetch-Site", "same-site"),
        ):
            with self.subTest(header=header, value=value):
                self.assertFalse(self.ask(h=headers(**{header: value}))[0])

    def test_non_email_identity_and_non_tailnet_host_denied(self):
        self.assertFalse(self.ask(login="human")[0])
        self.assertFalse(self.ask(host="example.com")[0])
        self.assertFalse(self.ask(host="rack.example-tail.ts.net.evil")[0])

    def test_no_general_origin_or_remote_mcp_grant(self):
        source = (Path(__file__).parent / "bin" / "preceptoros-pwa").read_text()
        self.assertEqual(source.count("self._tailnet_chat_owner()"), 1)
        self.assertIn("remote_model_only_tool_denied", source)
        self.assertIn('if remote_model_only and data.get("voz") is not None', source)
        self.assertIn('local_persona = self._nodo_local_autorizado()', source)
        self.assertIn('ruta == "/api/hexelion/chat"', source)


class ExistingPwaChatGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parent / "bin" / "preceptoros-pwa"
        loader = importlib.machinery.SourceFileLoader("pwa_tailnet_gate_test", str(path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        cls.PWA = module

    def handler(self, request):
        h = object.__new__(self.PWA.PWA)
        body = json.dumps(request).encode("utf-8")
        h.client_address = ("127.0.0.1", 40000)
        h.server = SimpleNamespace(server_address=("127.0.0.1", 8742),
                                   server_port=8742)
        h.headers = headers(**{"Content-Length": str(len(body))})
        h.rfile = io.BytesIO(body)
        h._json = mock.Mock()
        h._nodo_local_autorizado = mock.Mock(return_value=False)
        return h

    def test_remote_grammar_action_rejected_before_thread_or_mcp(self):
        h = self.handler({"texto": "/estado"})
        with mock.patch.dict(os.environ, {
                "PRECEPTOROS_CHAT_TAILNET_HOST": HOST,
                "PRECEPTOROS_CHAT_OWNER_LOGIN": OWNER}), \
             mock.patch.object(self.PWA._canales, "di_soberano") as writes, \
             mock.patch.object(self.PWA._hexelion_acciones, "ejecuta") as executes:
            h._hexelion_chat()
            self.assertEqual(h._json.call_args.args[0], 403)
            self.assertEqual(h._json.call_args.args[1]["causa"], "remote_model_only_tool_denied")
            writes.assert_not_called()
            executes.assert_not_called()

    def test_remote_cli_voice_rejected_before_thread(self):
        h = self.handler({"texto": "Explain what LAB can measure", "voz": "codex"})
        with mock.patch.dict(os.environ, {
                "PRECEPTOROS_CHAT_TAILNET_HOST": HOST,
                "PRECEPTOROS_CHAT_OWNER_LOGIN": OWNER}), \
             mock.patch.object(self.PWA._canales, "di_soberano") as writes:
            h._hexelion_chat()
            self.assertEqual(h._json.call_args.args[0], 403)
            self.assertEqual(h._json.call_args.args[1]["causa"], "remote_chat_voice_not_authorized")
            writes.assert_not_called()

    def test_wrong_owner_does_not_reach_model(self):
        h = self.handler({"texto": "Hello"})
        h.headers["Tailscale-User-Login"] = "stranger@example.invalid"
        with mock.patch.dict(os.environ, {
                "PRECEPTOROS_CHAT_TAILNET_HOST": HOST,
                "PRECEPTOROS_CHAT_OWNER_LOGIN": OWNER}), \
             mock.patch.object(self.PWA._hexelion_proxy, "ask") as ask:
            h._hexelion_chat()
            self.assertEqual(h._json.call_args.args[0], 403)
            ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
