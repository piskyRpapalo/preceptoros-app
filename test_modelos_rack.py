"""Rack model picker: host-owned catalog, honest states, one streamed turn, cancel stops the engine."""
import io
import json
import os
import tempfile
import unittest

import modelos_rack as m


class FakeEngine:
    """An Ollama-shaped opener: /api/tags, /api/ps, /api/show and a streamed /api/chat."""
    def __init__(self, loaded=(), chunks=None, down=False, model="qwen3:4b"):
        self.loaded, self.down, self.model, self.closed = set(loaded), down, model, False
        self.chunks = chunks if chunks is not None else [
            {"model": model, "message": {"content": "Hola"}, "done": False},
            {"model": model, "message": {"content": " mundo"}, "done": False},
            {"model": model, "message": {"content": ""}, "done": True, "total_duration": 2_000_000_000,
             "load_duration": 500_000_000, "eval_count": 2}]

    def __call__(self, req, timeout=None):
        if self.down:
            raise OSError("connection refused")
        path = req.full_url.split("11434", 1)[1]
        engine = self

        class R(io.BytesIO):
            def __enter__(s): return s
            def __exit__(s, *a): engine.closed = True
        if path == "/api/tags":
            return R(json.dumps({"models": [
                {"name": "qwen3:4b", "size": 2_500_000_000, "details": {"parameter_size": "4.0B", "quantization_level": "Q4_K_M"}},
                {"name": "nomic-embed-text:latest", "size": 1, "details": {}}]}).encode())
        if path == "/api/ps":
            return R(json.dumps({"models": [{"name": n} for n in self.loaded]}).encode())
        if path == "/api/show":
            name = json.loads(req.data)["model"]
            return R(json.dumps({"capabilities": ["embedding"] if "embed" in name else ["completion", "tools"]}).encode())
        if path == "/api/chat":
            return R(b"".join(json.dumps(c).encode() + b"\n" for c in self.chunks))
        raise AssertionError(path)


class ModelosRack(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.hosts = os.path.join(self.dir, "hosts.json")
        self.e2e = os.path.join(self.dir, "e2e.json")
        json.dump({"hosts": [{"id": "rack-a", "base": "http://100.64.1.2:11434"},
                             {"id": "evil", "base": "http://8.8.8.8:11434"},
                             {"id": "Bad Id", "base": "http://127.0.0.1:11434"}]}, open(self.hosts, "w"))
        m._SHOW_CACHE.clear()

    def test_only_loopback_or_tailnet_hosts_from_the_host_file(self):
        self.assertEqual(m.hosts(self.hosts), [("rack-a", "http://100.64.1.2:11434")])
        self.assertFalse(m.valid_base("http://10.0.0.1:11434"))
        self.assertFalse(m.valid_base("https://100.64.1.2:11434"))
        self.assertFalse(m.valid_base("http://100.64.1.2:11434/x"))

    def test_catalog_states_are_what_the_engine_reports(self):
        c = m.catalog(self.hosts, self.e2e, opener=FakeEngine())
        by = {x["key"]: x for x in c["models"]}
        self.assertEqual(by["rack-a/qwen3:4b"]["state"], "AVAILABLE")
        self.assertTrue(by["rack-a/qwen3:4b"]["chat"])
        self.assertFalse(by["rack-a/nomic-embed-text:latest"]["chat"])
        self.assertIsNone(by["rack-a/qwen3:4b"]["e2e"])
        self.assertEqual(c["local_android"]["state"], "NO_DATA")
        m._SHOW_CACHE.clear()
        loaded = m.catalog(self.hosts, self.e2e, opener=FakeEngine(loaded=["qwen3:4b"]))
        self.assertEqual({x["key"]: x for x in loaded["models"]}["rack-a/qwen3:4b"]["state"], "READY")

    def test_an_unreachable_host_is_offline_and_lists_nothing(self):
        c = m.catalog(self.hosts, self.e2e, opener=FakeEngine(down=True))
        self.assertEqual(c["devices"], [{"id": "rack-a", "state": "OFFLINE", "cause": "host_unreachable"}])
        self.assertEqual(c["models"], [])

    def test_the_browser_names_a_key_never_an_address(self):
        self.assertEqual(m.resolve("rack-a/qwen3:4b", self.hosts), ("http://100.64.1.2:11434", "qwen3:4b"))
        self.assertEqual(m.resolve("evil/qwen3:4b", self.hosts), (None, "model_host_not_configured"))
        self.assertEqual(m.resolve("http://x/y", self.hosts)[0], None)

    def test_messages_are_bounded_and_end_with_the_person(self):
        self.assertIsNone(m.messages([{"role": "assistant", "content": "x"}]))
        self.assertIsNone(m.messages([{"role": "system", "content": "x"}]))
        self.assertIsNone(m.messages([{"role": "user", "content": "x" * 5000}]))
        many = [{"role": "user", "content": str(i)} for i in range(20)]
        self.assertEqual(len(m.messages(many)), m.MAX_TURNS)

    def test_a_streamed_turn_emits_loading_tokens_done_and_a_receipt(self):
        events = []
        r = m.stream("http://100.64.1.2:11434", "qwen3:4b", [{"role": "user", "content": "hola"}],
                     lambda e: events.append(e) or True, opener=FakeEngine())
        self.assertEqual([e["e"] for e in events], ["loading", "token", "token", "done"])
        self.assertEqual(r["state"], "MEASURED")
        self.assertEqual(r["text"], "Hola mundo")
        self.assertEqual(r["tokens"], 2)

    def test_cancel_stops_reading_and_closes_the_engine_stream(self):
        engine, events = FakeEngine(), []
        def emit(e):
            events.append(e)
            return e["e"] != "token"     # the client goes away at the first token
        r = m.stream("http://100.64.1.2:11434", "qwen3:4b", [{"role": "user", "content": "hola"}], emit, opener=engine)
        self.assertEqual(r["state"], "CANCELLED")
        self.assertTrue(engine.closed)
        self.assertNotIn("done", [e["e"] for e in events])

    def test_another_model_answering_or_no_text_is_never_a_reply(self):
        r = m.stream("http://100.64.1.2:11434", "qwen3:4b", [{"role": "user", "content": "hola"}],
                     lambda e: True, opener=FakeEngine(model="other:1b"))
        self.assertEqual(r["cause"], "engine_model_unconfirmed")
        empty = FakeEngine(chunks=[{"model": "qwen3:4b", "message": {"content": ""}, "done": True}])
        r = m.stream("http://100.64.1.2:11434", "qwen3:4b", [{"role": "user", "content": "hola"}],
                     lambda e: True, opener=empty)
        self.assertEqual(r["cause"], "engine_returned_no_text")

    def test_only_a_completed_turn_marks_e2e(self):
        m.record_e2e("rack-a/qwen3:4b", {"at": "2026-11-23T01:00:00Z"}, self.e2e)
        c = m.catalog(self.hosts, self.e2e, opener=FakeEngine())
        self.assertEqual({x["key"]: x for x in c["models"]}["rack-a/qwen3:4b"]["e2e"], {"at": "2026-11-23T01:00:00Z"})


if __name__ == "__main__":
    unittest.main()
