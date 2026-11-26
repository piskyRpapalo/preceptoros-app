"""ONLINE3 · Talk private route selector contract (pure, CI-safe).

The real Chromium proof is tests/app_private_talk_route.browser.cjs (bridges are test doubles).
Interface contract: odd/tasks/online3-private-talk.md (Codex). This suite pins what the page may
and may not do; it does not measure the APK, Tailscale or a Hexelion inference.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GATE = (ROOT / "interface/browser_mini_gate.js").read_text(encoding="utf8")
PRIVATE = GATE[GATE.index("Online3 · private Talk route selector"):]


class PrivateTalkRoute(unittest.TestCase):
    def test_only_with_the_owner_bridge_and_no_network_or_storage_of_its_own(self):
        self.assertIn("root.PreceptorPrivateTalkNative", PRIVATE)
        self.assertIn("typeof native.postMessage !== 'function'", PRIVATE)
        for banned in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "indexedDB",
                       "sendBeacon", "WebSocket", ".ts.net", "100.", "http://", "https://"):
            self.assertNotIn(banned, PRIVATE, banned)

    def test_messages_follow_the_contract(self):
        self.assertIn("{ op: 'status' }", PRIVATE)
        self.assertIn("{ op: 'configure' }", PRIVATE)
        self.assertIn("{ op: 'send', texto: text }", PRIVATE)
        self.assertIn("padStart(2, '0')", PRIVATE)
        self.assertIn("new Uint8Array(16)", PRIVATE)  # 32 hex ids
        timeout = int(re.search(r"replyWaitMs = (\d+)", PRIVATE).group(1))
        self.assertGreaterEqual(timeout, 145000)
        self.assertIn("connection|authentication|model|context|request", PRIVATE)

    def test_measured_needs_model_time_sources_and_text(self):
        for need in ("r.estado === 'MEASURED'", "answer.estado === 'MEASURED'", "Number(machine.ms) > 0",
                     "answer.fuentes.length", "clean(answer.texto, 4000)"):
            self.assertIn(need, PRIVATE)
        self.assertIn("Not your on-device model.", PRIVATE)

    def test_local_stays_default_and_private_is_explicit(self):
        self.assertIn("let privateOn = false;", PRIVATE)
        self.assertIn("if (event.target !== form || !privateOn) return;", PRIVATE)
        self.assertIn("doc.addEventListener('submit'", PRIVATE)  # before offline Mini's form listener
        self.assertIn("input.value = text; // keep the words", PRIVATE)

    def test_one_state_for_eye_reader_and_machine(self):
        self.assertIn("setAttribute('role', 'status')", PRIVATE)
        self.assertIn("setAttribute('aria-live', 'polite')", PRIVATE)
        for key in ("dataset.state", "dataset.acho", "dataset.cause", "dataset.stage", "'acho:event'"):
            self.assertIn(key, PRIVATE)
        self.assertIn("aria-pressed", PRIVATE)
        self.assertEqual(PRIVATE.count("minHeight = '44px'"), 1)
        self.assertIn("minWidth = '44px'", PRIVATE)

    def test_served_version_is_aligned(self):
        html = (ROOT / "interface/app.html").read_text(encoding="utf8")
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf8")
        self.assertIn('src="/browser_mini_gate.js?v=3"', html)
        self.assertIn('"/browser_mini_gate.js?v=3"', sw)
        self.assertIn('const Cache = "preceptoros-armazon-v251"', sw)


if __name__ == "__main__":
    unittest.main()
