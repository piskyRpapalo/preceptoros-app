"""Day D: source-level guard for personal_mvp versus private rack.

This complements tests/dayd_personal_no_rack.browser.cjs, which is the
actual Chromium negative proof. A static string is NEVER authentication.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import orquestador
import test_pwa


ROOT = Path(__file__).resolve().parent
APP = (ROOT / "interface" / "app.js").read_text(encoding="utf-8")
THREAD = (ROOT / "interface" / "conversacion.js").read_text(encoding="utf-8")
HTML = (ROOT / "interface" / "app.html").read_text(encoding="utf-8")
MINI = (ROOT / "mvp-android" / "offline_mini.js").read_text(encoding="utf-8")


class DayDPersonalBoundary(unittest.TestCase):
    def test_empty_station_endpoint_selects_personal_local_model(self):
        variable = test_pwa.PWA._hexelion_proxy.ENDPOINT_ENV
        with mock.patch.dict(os.environ, {variable: ""}):
            self.assertEqual(test_pwa.PWA._talk_mode(), "local_gguf")
        with mock.patch.dict(os.environ, {variable: "http://127.0.0.1:21434"}):
            self.assertEqual(test_pwa.PWA._talk_mode(), "private_hexelion")
        # The server has two modes; it is not allowed to change the user's
        # selected personal profile or infer a grant from environment flags.

    def test_private_chat_mode_guard_precedes_request(self):
        guard = 'talkMode === privateMode && window.PreceptorProfile !== "private_rack"'
        private_request = 'fetch(localTalk ? "/api/charla" : "/api/hexelion/chat"'
        self.assertIn(guard, APP)
        self.assertIn(private_request, APP)
        self.assertLess(APP.index(guard), APP.index(private_request))
        self.assertIn("personal_profile_private_route_denied", APP)
        self.assertIn("localDraft.remove()", APP)
        self.assertIn('$("dicho").value = escrito', APP)

    def test_base_mvp_has_no_privileged_profile_selector(self):
        self.assertIn('window.PreceptorProfile = "personal_mvp"',APP)
        self.assertNotIn('id="app-profile-section"',HTML)
        self.assertNotIn('name="app-profile"',HTML)
        self.assertNotIn('preferred === "private_rack"',APP)
        self.assertIn('personal_profile_private_route_denied',APP)

    def test_shared_thread_reads_and_writes_are_profile_gated(self):
        self.assertIn('async function sync(opts) {\n    if (root.PreceptorProfile !== "private_rack")', THREAD)
        self.assertIn('async function send(para, texto) {\n    // A personal_mvp', THREAD)
        self.assertIn('if (root.PreceptorProfile !== "private_rack") {\n      return { ok: false', THREAD)
        self.assertIn("personal_profile_shared_thread_denied", THREAD)
        self.assertIn('fetch("/api/conversacion"', THREAD)

    def test_mini_cannot_grant_private_authority(self):
        self.assertIn('window.PreceptorProfile = "personal_mvp"',APP)
        self.assertNotIn('value="private_rack"',HTML)
        self.assertIn("on_device_model_unavailable",MINI)
        self.assertIn("remote_effect_not_authorized",MINI)

    def test_closed_intents_and_no_automatic_rag_write(self):
        self.assertEqual(orquestador.INTENTS, frozenset({
            "DEPLOY_BUILDING", "QUERY_STATE", "UPDATE_RAG", "MAP_BRAIN_STATUS",
        }))
        self.assertEqual(orquestador.TOPE_B, 1024)
        self.assertIn("signed frontera.py RAG adapter is not attached",
                      (ROOT / "orquestador.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
