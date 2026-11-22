"""TRAIN-02 A-07: bounded synthetic station binding tests; never generate on rack."""
import json
import unittest
from unittest import mock

import hexelion_proxy as proxy


DIGEST = "714d86958b6e870a9320e78126ac1ce3477727a1cd9bf7194b8ace0d84c62fd8"


class Response:
    def __init__(self, data):
        self._data = json.dumps(data).encode("utf-8")

    def read(self, max_bytes=None):
        return self._data if max_bytes is None else self._data[:max_bytes]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def transport(*, digest=DIGEST, present=True, wrong_reply=False):
    calls = []

    def open_url(request, timeout=None):
        calls.append((request.get_method(), request.full_url))
        if request.full_url.endswith("/api/tags"):
            return Response({
                "models": [{"name": "gpt-oss:120b", "digest": digest}] if present else []
            })
        if request.full_url.endswith("/api/generate"):
            body = json.loads(request.data)
            assert request.get_method() == "POST"
            assert body["model"] == "gpt-oss:120b"
            return Response({
                "model": "unexpected:latest" if wrong_reply else "gpt-oss:120b",
                "response": "fixture-only text",
                "total_duration": 10_000_000,
                "eval_count": 3,
                "eval_duration": 8_000_000,
            })
        raise AssertionError("unexpected station operation")

    return open_url, calls


def clock():
    return iter((0.0, 0.2)).__next__


def ask(opener, endpoint="http://127.0.0.1:11434"):
    return proxy.ask("offline fixture", endpoint=endpoint, opener=opener, clock=clock())


class StationBindingTests(unittest.TestCase):
    def test_pinned_candidate_accepts_matching_runtime_digest_only(self):
        opener, calls = transport()
        with mock.patch.object(proxy, "MODEL", "gpt-oss:120b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", DIGEST
        ):
            result = ask(opener)
        self.assertEqual(result["estado"], "MEASURED")
        self.assertEqual(result["modelo"], "gpt-oss:120b")
        self.assertEqual(
            result["model_evidence"]["pin_state"], "CATALOG_MATCH_NOT_OWNER_AUTH"
        )
        self.assertEqual([method for method, _ in calls], ["GET", "POST"])

    def test_mismatch_prevents_generate(self):
        opener, calls = transport(digest="f" * 64)
        with mock.patch.object(proxy, "MODEL", "gpt-oss:120b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", DIGEST
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_digest_mismatch")
        self.assertEqual(len(calls), 1)

    def test_unpinned_alternative_prevents_every_network_operation(self):
        opener, calls = transport()
        with mock.patch.object(proxy, "MODEL", "qwen3-coder:30b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", ""
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_digest_pin_missing")
        self.assertEqual(calls, [])

    def test_malformed_digest_prevents_network(self):
        opener, calls = transport()
        with mock.patch.object(proxy, "MODEL", "gpt-oss:120b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", "not-a-sha"
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_digest_pin_invalid")
        self.assertEqual(calls, [])

    def test_unlisted_model_prevents_network(self):
        opener, calls = transport()
        with mock.patch.object(proxy, "MODEL", "unverified:latest"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", DIGEST
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_selection_invalid")
        self.assertEqual(calls, [])

    def test_legacy_missing_alias_keeps_fail_closed_cause(self):
        opener, calls = transport(present=False)
        with mock.patch.object(proxy, "MODEL", "hexelion:latest"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", ""
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_unavailable")
        self.assertEqual(len(calls), 1)

    def test_unexpected_response_model_is_rejected(self):
        opener, calls = transport(wrong_reply=True)
        with mock.patch.object(proxy, "MODEL", "gpt-oss:120b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", DIGEST
        ):
            result = ask(opener)
        self.assertEqual(result["causa"], "station_model_unconfirmed")
        self.assertEqual(len(calls), 2)

    def test_non_loopback_endpoint_is_refused(self):
        opener, calls = transport()
        with mock.patch.object(proxy, "MODEL", "gpt-oss:120b"), mock.patch.object(
            proxy, "MODEL_SHA256_PIN", DIGEST
        ):
            result = ask(opener, endpoint="http://100.125.76.31:11434")
        self.assertEqual(result["causa"], "station_loopback_required")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
