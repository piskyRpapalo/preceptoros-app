import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import plan_store as S

ROOT = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_loader(
    "superbot_pwa_plan_store",
    importlib.machinery.SourceFileLoader("superbot_pwa_plan_store", str(ROOT / "bin/preceptoros-pwa")))
PWA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PWA)


def request(title="Plan", text="step", **extra):
    return json.dumps({"schema": S.SCHEMA, "title": title, "text": text, **extra},
                      ensure_ascii=False).encode("utf-8")


class PlanStoreTests(unittest.TestCase):
    def test_long_plan_is_stored_whole_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = request(text="á\n" * 105000)
            result = S.put(pathlib.Path(tmp), raw)
            doc, size = S.get(pathlib.Path(tmp), result["plan_sha256"])
            self.assertEqual(doc["text"], "á\n" * 105000)
            self.assertEqual(size, result["bytes"])
            self.assertEqual(hashlib.sha256(S._canonical(doc)).hexdigest(), result["plan_sha256"])
            self.assertTrue(result["created"])
            again = S.put(pathlib.Path(tmp), raw)
            self.assertFalse(again["created"])
            self.assertEqual(len(list((pathlib.Path(tmp) / "plans").glob("*.json"))), 1)
            self.assertEqual((pathlib.Path(tmp) / "plans").stat().st_mode & 0o777, 0o700)
            self.assertEqual(next((pathlib.Path(tmp) / "plans").glob("*.json")).stat().st_mode & 0o777, 0o600)

    def test_duplicate_keys_unknown_fields_and_nonfinite_numbers_rejected(self):
        for raw in (b'{"schema":"preceptoros.plan/1","schema":"x","title":"x","text":"y"}',
                    request(extra=True), b'{"schema":"preceptoros.plan/1","title":"x","text":"y","x":NaN}'):
            with self.subTest(raw=raw[:40]), self.assertRaises(S.PlanError):
                S.parse_request(raw)

    def test_tampered_blob_and_invalid_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = S.put(pathlib.Path(tmp), request(text="secret content"))
            path = pathlib.Path(tmp) / "plans" / (result["plan_sha256"] + ".json")
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(S.PlanError, "plan_digest_mismatch"):
                S.get(pathlib.Path(tmp), result["plan_sha256"])
            for bad in ("../" + result["plan_sha256"], "A" * 64, "0" * 64):
                with self.assertRaises(S.PlanError):
                    S.get(pathlib.Path(tmp), bad)

    def test_only_person_reference_is_selected_and_proposal_is_not_inferred(self):
        sha = "a" * 64
        msgs = [{"voz": "codex", "rol": "agent", "texto": f"PLAN_REF {sha} 12"},
                {"voz": "superbot-plan-store", "rol": "system", "texto": "PLAN_REF " + "b" * 64 + " 20", "t": "new"},
                {"voz": "superbot-plan-store", "rol": "system", "texto": f"PLAN_REF {sha} 12", "t": "old"}]
        self.assertEqual(S.flow_reference(msgs), {"sha": sha, "bytes": 12, "written_at": "old"})

    def test_http_post_requires_local_origin_and_reuses_channel_ref_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = PWA.PWA.__new__(PWA.PWA)
            h.path = "/api/plan"
            h.client_address = ("127.0.0.1", 1234)
            payload = request(text="private long text")
            h.headers = {"Origin": "http://127.0.0.1:8740", "Host": "127.0.0.1:8740",
                         "Content-Length": str(len(payload)), "Content-Type": "application/json",
                         "Sec-Fetch-Site": "same-origin"}
            h.server = type("Server", (), {"server_port": 8740})()
            h.rfile = io.BytesIO(payload)
            h._json = lambda code, body: (code, body)
            with mock.patch.object(PWA._casa, "raiz", return_value=pathlib.Path(tmp)):
                code, body = h._plan_store_post()
                self.assertEqual(code, 201)
                self.assertEqual(body["authority"], "none")
                events = PWA._canales.lee("orquesta", base=pathlib.Path(tmp))
                self.assertEqual(events["mensajes"][-1]["texto"], f"PLAN_REF {body['plan_sha256']} {body['bytes']}")
                self.assertEqual(events["mensajes"][-1]["voz"], "superbot-plan-store")
                self.assertNotIn("private long text", json.dumps(events))
                h.rfile = io.BytesIO(payload)
                duplicate_code, duplicate_body = h._plan_store_post()
                self.assertEqual(duplicate_code, 200)
                self.assertEqual(duplicate_body["plan_sha256"], body["plan_sha256"])
                self.assertEqual(len(PWA._canales.lee("orquesta", base=pathlib.Path(tmp))["mensajes"]), 1)
                flow = h._plan_flow()[1]
                self.assertEqual(flow["schema"], "preceptoros.plan-flow/1")
                self.assertEqual(flow["proposal"], {"plan_sha256": body["plan_sha256"],
                                  "orchestrator": "NO_DATA", "cause": "proposal_not_built", "tasks": []})
                self.assertEqual(flow["authority"], "none")
                h.headers["Origin"] = "http://evil.example"
                self.assertEqual(h._plan_store_post()[0], 403)

    def test_real_loopback_http_round_trip_for_long_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            class Quiet(PWA.PWA):
                def log_message(self, *_):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = request(title="Long plan", text="x" * 210000)
                origin = f"http://127.0.0.1:{port}"
                with mock.patch.object(PWA._casa, "raiz", return_value=pathlib.Path(tmp)):
                    req = urllib.request.Request(origin + "/api/plan", data=payload, method="POST",
                                                 headers={"Origin": origin, "Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        posted = json.load(response)
                        self.assertEqual(response.status, 201)
                        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                    flow_req = urllib.request.Request(origin + "/api/plan/flow",
                                                      headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"})
                    with urllib.request.urlopen(flow_req, timeout=5) as response:
                        flow = json.load(response)
                    get_req = urllib.request.Request(origin + "/api/plan/" + posted["plan_sha256"],
                                                     headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"})
                    with urllib.request.urlopen(get_req, timeout=5) as response:
                        stored = json.load(response)
                    self.assertEqual(flow["schema"], "preceptoros.plan-flow/1")
                    self.assertEqual(stored["text"], "x" * 210000)
                    self.assertEqual(stored["plan_sha256"], flow["plan"]["plan_sha256"])
                    self.assertEqual(flow["proposal"]["tasks"], [])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
