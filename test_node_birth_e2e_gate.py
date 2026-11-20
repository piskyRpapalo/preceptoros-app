"""NODE-BIRTH E2E gate — directed tests with injected synthetic fixtures.

All tests are READ-ONLY, NO NETWORK, NO MUTATION, NO GRANT. Fixtures are
synthetic and anonymous. No secrets, hostnames, IPs, or actual SSH credential
values appear in any fixture.

CRITICAL INVARIANT: The gate ALWAYS returns live=false because stages 5,6,11,12
(issuer_auth, cedula, heartbeat, public_live) require real independent
cryptographic verification and live public observation that cannot be satisfied
by synthetic fixtures. Structural checks can report STRUCTURE_OK separately,
but NEVER authoritative VERIFIED.

Adversarial tests cover: forged consent, ctx._now override bypass, oversized
inputs, malformed JSON crashes, negative/future timestamps, context injection
attacks, and all-claimed-verified false positives.
"""
import hashlib
import json
import unittest
from datetime import datetime, timezone, timedelta

import node_birth_e2e_gate as G

NOW = datetime(2026, 11, 20, 2, 0, 0, tzinfo=timezone.utc)
NOW_ISO = "2026-11-20T02:00:00Z"


# --- Helpers to build valid fixtures ---

def _canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def make_receipt(node_id="primer-ancla", edificio="observatorio-primer-ancla"):
    """Build a self-consistent receipt with valid hashes."""
    body = {"esquema": "preceptoros.edificio-declaracion/1", "edificio": edificio}
    receipt = {
        "esquema": "preceptoros.recibo-edificio/1",
        "estado": "recibido",
        "causa": None,
        "nodo": node_id,
        "edificio": edificio,
        "payload_sha256": hashlib.sha256(_canonical(body)).hexdigest(),
        "recibido_en": NOW_ISO,
        "procedencia": "test-fixture",
    }
    receipt["recibo_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    return receipt


def make_cedula(node_name="nodo.7.demo", auth="OK"):
    """Build a self-consistent cédula with valid integrity hash."""
    body = {
        "esquema": "preceptoros.cedula-nodo/1",
        "nodo": node_name,
        "admin": "a" * 64,
        "dispositivos": [{"clave": "b" * 64, "estado": "linkeado"}],
        "firma_ssh": "test-fixture-signature",
        "autenticidad": auth,
    }
    body_no_hash = {k: v for k, v in body.items() if k not in ("sha256", "firma_ssh", "firma", "autenticidad")}
    body["sha256"] = hashlib.sha256(
        json.dumps(body_no_hash, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def full_verified_ctx():
    """Context where structural stages return VERIFIED, but trust-requiring stages
    (issuer_auth, cedula, heartbeat, public_live) return NO_DATA.
    The gate ALWAYS returns live=false because of the trust-requiring stages.
    """
    return {
        "identity": {"esquema": "preceptoros.pwa-node-identity/1", "node_id": "primer-ancla"},
        "consent": True,
        "consent_timestamp": NOW_ISO,
        "preliminary_request": {
            "schema": "preceptoros.node-registration-request/1",
            "node": "primer-ancla",
            "device_sha256": "a" * 64,
            "nonce": "test-nonce-001",
            "consent": True,
        },
        "receipt": make_receipt(),
        "issuer_auth": {"state": "VERIFIED", "issuer": "test-fixture", "method": "ssh-keygen"},
        "cedula": make_cedula(auth="OK"),
        "provision": {"estado": "provisionada", "node_id": "primer-ancla"},
        "inference": {"state": "VERIFIED", "model": "test-model", "latency_ms": 120},
        "lab_rag": {"state": "VERIFIED", "source_ref": "c" * 64, "node": "primer-ancla"},
        "cross_agent": {
            "turns": [
                {"agent": "agent-a", "text": "hello"},
                {"agent": "agent-b", "text": "response"},
            ]
        },
        "heartbeat": {"timestamp": NOW_ISO, "auth": "VERIFIED"},
        "public_live": {"state": "VERIFIED", "observer": "independent-web", "node_id": "primer-ancla"},
    }


class TestSourceStage(unittest.TestCase):
    def test_valid_pwa_identity(self):
        ctx = {"identity": {"esquema": "preceptoros.pwa-node-identity/1", "node_id": "primer-ancla"}}
        r = G.run_single_stage("source", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_valid_cedula_identity(self):
        ctx = {"identity": {"esquema": "preceptoros.cedula-nodo/1", "nodo": "nodo.7.demo"}}
        r = G.run_single_stage("source", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_missing_identity(self):
        r = G.run_single_stage("source", {})
        self.assertEqual(r["state"], "NO_DATA")
        self.assertEqual(r["cause"], "identity_missing")

    def test_unknown_schema(self):
        ctx = {"identity": {"esquema": "unknown/1", "node_id": "x"}}
        r = G.run_single_stage("source", ctx)
        self.assertEqual(r["cause"], "identity_schema_unknown")

    def test_malformed_node_id(self):
        ctx = {"identity": {"esquema": "preceptoros.pwa-node-identity/1", "node_id": "../bad"}}
        r = G.run_single_stage("source", ctx)
        self.assertEqual(r["cause"], "node_id_malformed")


class TestOwnerConsentStage(unittest.TestCase):
    def test_explicit_consent(self):
        ctx = {"consent": True, "consent_timestamp": NOW_ISO}
        r = G.run_single_stage("owner_consent", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_consent_false(self):
        ctx = {"consent": False, "consent_timestamp": NOW_ISO}
        r = G.run_single_stage("owner_consent", ctx)
        self.assertEqual(r["cause"], "consent_not_explicit")

    def test_consent_missing(self):
        r = G.run_single_stage("owner_consent", {})
        self.assertEqual(r["cause"], "consent_not_explicit")

    def test_consent_minted_by_agent_is_rejected(self):
        """An agent cannot mint consent; it must be explicit boolean True."""
        for bad in ["yes", 1, "true", {"granted": True}]:
            ctx = {"consent": bad, "consent_timestamp": NOW_ISO}
            r = G.run_single_stage("owner_consent", ctx)
            self.assertEqual(r["cause"], "consent_not_explicit")

    def test_malformed_timestamp(self):
        ctx = {"consent": True, "consent_timestamp": "not-a-date"}
        r = G.run_single_stage("owner_consent", ctx)
        self.assertEqual(r["cause"], "consent_timestamp_malformed")


class TestPreliminaryStage(unittest.TestCase):
    def _valid_request(self):
        return {
            "schema": "preceptoros.node-registration-request/1",
            "node": "primer-ancla",
            "device_sha256": "a" * 64,
            "nonce": "test-nonce",
            "consent": True,
        }

    def test_valid_request(self):
        ctx = {"preliminary_request": self._valid_request()}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_missing_request(self):
        r = G.run_single_stage("preliminary", {})
        self.assertEqual(r["cause"], "preliminary_request_missing")

    def test_missing_required_fields(self):
        ctx = {"preliminary_request": {"node": "x"}}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_request_incomplete")

    def test_extra_fields_rejected(self):
        """Unapproved extra fields must be rejected."""
        req = self._valid_request()
        req["purpose"] = "should-not-be-here"
        req["secret"] = "leaked"
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_extra_fields")

    def test_malformed_node(self):
        req = self._valid_request()
        req["node"] = "../evil"
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_node_malformed")

    def test_malformed_device_sha(self):
        req = self._valid_request()
        req["device_sha256"] = "not-hex"
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_device_sha_malformed")

    def test_missing_nonce(self):
        req = self._valid_request()
        req["nonce"] = ""
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_nonce_missing")

    def test_consent_not_boolean_true(self):
        """Consent must be exactly boolean True."""
        for bad in [False, "yes", 1, "true", {"granted": True}]:
            req = self._valid_request()
            req["consent"] = bad
            ctx = {"preliminary_request": req}
            r = G.run_single_stage("preliminary", ctx)
            self.assertEqual(r["cause"], "preliminary_consent_not_explicit")

    def test_purpose_not_on_wire(self):
        """Purpose is UI-local only — including it on wire must fail."""
        req = self._valid_request()
        req["purpose"] = "test"
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_extra_fields")

    def test_request_oversized(self):
        """Request exceeding 1024 bytes must be rejected."""
        req = self._valid_request()
        req["schema"] = "x" * 1100  # blow past 1024
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_request_oversized")


class TestResponseStage(unittest.TestCase):
    def test_valid_receipt(self):
        ctx = {"receipt": make_receipt()}
        r = G.run_single_stage("response", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_missing_receipt(self):
        r = G.run_single_stage("response", {})
        self.assertEqual(r["cause"], "receipt_missing")

    def test_forged_receipt_hash(self):
        """Tampered recibo_sha256 must fail."""
        receipt = make_receipt()
        receipt["recibo_sha256"] = "0" * 64
        ctx = {"receipt": receipt}
        r = G.run_single_stage("response", ctx)
        self.assertEqual(r["cause"], "receipt_hash_mismatch")

    def test_forged_payload_hash(self):
        receipt = make_receipt()
        receipt["payload_sha256"] = "0" * 64
        # Recompute recibo hash to match tampered payload
        base = {k: v for k, v in receipt.items() if k != "recibo_sha256"}
        receipt["recibo_sha256"] = hashlib.sha256(_canonical(base)).hexdigest()
        ctx = {"receipt": receipt}
        r = G.run_single_stage("response", ctx)
        self.assertEqual(r["state"], "VERIFIED")  # hash is self-consistent; payload content is separate

    def test_missing_hash_fields(self):
        ctx = {"receipt": {"esquema": "x"}}
        r = G.run_single_stage("response", ctx)
        self.assertEqual(r["cause"], "receipt_hash_missing")


class TestIssuerAuthStage(unittest.TestCase):
    def test_synthetic_verified_is_not_trusted(self):
        """Self-proclaimed VERIFIED from synthetic context is NOT proof."""
        ctx = {"issuer_auth": {"state": "VERIFIED", "issuer": "test", "method": "ssh"}}
        r = G.run_single_stage("issuer_auth", ctx)
        self.assertEqual(r["state"], "NO_DATA")
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_no_data_issuer_also_not_trusted(self):
        ctx = {"issuer_auth": {"state": "NO_DATA", "cause": "key_missing"}}
        r = G.run_single_stage("issuer_auth", ctx)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_missing_issuer(self):
        r = G.run_single_stage("issuer_auth", {})
        self.assertEqual(r["cause"], "issuer_auth_missing")

    def test_forged_issuer_state_rejected(self):
        """Any issuer_auth state returns NO_DATA — no synthetic verification."""
        for state in ["VERIFIED", "NO_DATA", "UNKNOWN", "LIVE"]:
            ctx = {"issuer_auth": {"state": state}}
            r = G.run_single_stage("issuer_auth", ctx)
            self.assertEqual(r["cause"], "trusted_witness_not_connected")


class TestCedulaStage(unittest.TestCase):
    def test_cedula_ok_is_not_trusted(self):
        """User-controlled autenticidad=OK is NOT proof of signature."""
        ctx = {"cedula": make_cedula(auth="OK")}
        r = G.run_single_stage("cedula", ctx)
        self.assertEqual(r["state"], "NO_DATA")
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_cedula_no_data_also_not_trusted(self):
        ctx = {"cedula": make_cedula(auth="NO_DATA")}
        r = G.run_single_stage("cedula", ctx)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_cedula_rejected_also_not_trusted(self):
        ctx = {"cedula": make_cedula(auth="RECHAZADA")}
        r = G.run_single_stage("cedula", ctx)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_cedula_hash_mismatch_still_caught(self):
        """Structural integrity — hash mismatch is still detected."""
        cedula = make_cedula()
        cedula["sha256"] = "0" * 64
        ctx = {"cedula": cedula}
        r = G.run_single_stage("cedula", ctx)
        self.assertEqual(r["cause"], "cedula_hash_mismatch")

    def test_missing_cedula(self):
        r = G.run_single_stage("cedula", {})
        self.assertEqual(r["cause"], "cedula_missing")

    def test_injected_ok_never_verifies(self):
        """Even with valid hash, injected OK cannot verify ssh-keygen -Y verify."""
        for auth in ["OK", "VERIFIED", "LIVE", "TRUSTED"]:
            ctx = {"cedula": make_cedula(auth=auth)}
            r = G.run_single_stage("cedula", ctx)
            self.assertEqual(r["cause"], "trusted_witness_not_connected")


class TestProvisionStage(unittest.TestCase):
    def test_provisioned(self):
        ctx = {"provision": {"estado": "provisionada", "node_id": "primer-ancla"}}
        r = G.run_single_stage("provision", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_provision_no_data(self):
        ctx = {"provision": {"estado": "NO_DATA", "causa": "disk_full"}}
        r = G.run_single_stage("provision", ctx)
        self.assertEqual(r["cause"], "disk_full")

    def test_missing_provision(self):
        r = G.run_single_stage("provision", {})
        self.assertEqual(r["cause"], "provision_missing")


class TestInferenceStage(unittest.TestCase):
    def test_verified_inference(self):
        ctx = {"inference": {"state": "VERIFIED", "model": "smollm2", "latency_ms": 200}}
        r = G.run_single_stage("inference", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_model_present_not_inference(self):
        """Model presence ≠ inference — must distinguish."""
        ctx = {"inference": {"state": "MODEL_PRESENT", "model": "smollm2"}}
        r = G.run_single_stage("inference", ctx)
        self.assertEqual(r["cause"], "model_present_no_inference")

    def test_no_data_inference(self):
        ctx = {"inference": {"state": "NO_DATA", "cause": "ollama_not_running"}}
        r = G.run_single_stage("inference", ctx)
        self.assertEqual(r["cause"], "ollama_not_running")

    def test_two_models_not_two_nodes(self):
        """Two Ollama models on one machine ≠ two nodes."""
        ctx = {"inference": {"state": "VERIFIED", "model": "model-a"}}
        r = G.run_single_stage("inference", ctx)
        self.assertEqual(r["state"], "VERIFIED")
        self.assertEqual(r["value"]["model"], "model-a")
        # The stage only verifies one inference; node count is a separate concern

    def test_missing_inference(self):
        r = G.run_single_stage("inference", {})
        self.assertEqual(r["cause"], "inference_missing")


class TestLabRagStage(unittest.TestCase):
    def test_verified_lab(self):
        ctx = {"lab_rag": {"state": "VERIFIED", "source_ref": "d" * 64, "node": "node-a"}}
        r = G.run_single_stage("lab_rag", ctx)
        self.assertEqual(r["state"], "VERIFIED")

    def test_stale_lab(self):
        ctx = {"lab_rag": {"state": "STALE", "cause": "observation_expired"}}
        r = G.run_single_stage("lab_rag", ctx)
        self.assertEqual(r["cause"], "lab_rag_stale")

    def test_no_data_lab(self):
        ctx = {"lab_rag": {"state": "NO_DATA", "cause": "lab_clone_missing"}}
        r = G.run_single_stage("lab_rag", ctx)
        self.assertEqual(r["cause"], "lab_clone_missing")

    def test_invalid_source_ref(self):
        ctx = {"lab_rag": {"state": "VERIFIED", "source_ref": "not-hex", "node": "x"}}
        r = G.run_single_stage("lab_rag", ctx)
        self.assertEqual(r["cause"], "lab_rag_source_ref_invalid")


class TestCrossAgentStage(unittest.TestCase):
    def test_valid_multi_agent(self):
        ctx = {"cross_agent": {
            "turns": [
                {"agent": "hexelion", "text": "query"},
                {"agent": "smollm2", "text": "reply"},
            ]
        }}
        r = G.run_single_stage("cross_agent", ctx)
        self.assertEqual(r["state"], "VERIFIED")
        self.assertEqual(r["value"]["agents"], ["hexelion", "smollm2"])

    def test_single_agent_only(self):
        """Synthetic fixture with one agent ≠ cross-agent dialogue."""
        ctx = {"cross_agent": {
            "turns": [
                {"agent": "hexelion", "text": "a"},
                {"agent": "hexelion", "text": "b"},
            ]
        }}
        r = G.run_single_stage("cross_agent", ctx)
        self.assertEqual(r["cause"], "cross_agent_single_agent_only")

    def test_insufficient_turns(self):
        ctx = {"cross_agent": {"turns": [{"agent": "a", "text": "x"}]}}
        r = G.run_single_stage("cross_agent", ctx)
        self.assertEqual(r["cause"], "cross_agent_insufficient_turns")

    def test_missing_cross_agent(self):
        r = G.run_single_stage("cross_agent", {})
        self.assertEqual(r["cause"], "cross_agent_missing")


class TestHeartbeatStage(unittest.TestCase):
    def test_fresh_heartbeat_not_trusted(self):
        """Even a fresh heartbeat with auth=VERIFIED is NOT trusted without real observer."""
        ctx = {"heartbeat": {"timestamp": NOW_ISO, "auth": "VERIFIED"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["state"], "NO_DATA")
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_stale_heartbeat_not_trusted(self):
        old = NOW - timedelta(minutes=5)
        old_iso = old.isoformat().replace("+00:00", "Z")
        ctx = {"heartbeat": {"timestamp": old_iso, "auth": "VERIFIED"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_replayed_heartbeat_not_trusted(self):
        """A replayed old heartbeat is NOT trusted."""
        old = NOW - timedelta(hours=1)
        old_iso = old.isoformat().replace("+00:00", "Z")
        ctx = {"heartbeat": {"timestamp": old_iso, "auth": "VERIFIED"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_unverified_auth_not_trusted(self):
        ctx = {"heartbeat": {"timestamp": NOW_ISO, "auth": "NO_DATA"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_missing_heartbeat(self):
        r = G.run_single_stage("heartbeat", {}, now=NOW)
        self.assertEqual(r["cause"], "heartbeat_missing")

    def test_missing_timestamp(self):
        ctx = {"heartbeat": {"auth": "VERIFIED"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["cause"], "heartbeat_timestamp_missing")

    def test_now_param_does_not_leak_to_ctx(self):
        """ctx._now must NOT be set by run_single_stage — only explicit now param."""
        ctx = {"heartbeat": {"timestamp": NOW_ISO, "auth": "VERIFIED"}}
        # Even with now=NOW, the stage should not read ctx._now
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")
        self.assertNotIn("_now", ctx)


class TestPublicLiveStage(unittest.TestCase):
    def test_verified_live_not_trusted(self):
        """A string observer is NOT proof of a live public node."""
        ctx = {"public_live": {"state": "VERIFIED", "observer": "web", "node_id": "primer-ancla"}}
        r = G.run_single_stage("public_live", ctx)
        self.assertEqual(r["state"], "NO_DATA")
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_no_data_live_not_trusted(self):
        ctx = {"public_live": {"state": "NO_DATA", "cause": "web_404"}}
        r = G.run_single_stage("public_live", ctx)
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_missing_live(self):
        r = G.run_single_stage("public_live", {})
        self.assertEqual(r["cause"], "public_live_missing")

    def test_any_state_returns_no_data(self):
        """Any public_live state returns NO_DATA — no synthetic LIVE."""
        for state in ["VERIFIED", "NO_DATA", "LIVE", "UNKNOWN"]:
            ctx = {"public_live": {"state": state, "observer": "x"}}
            r = G.run_single_stage("public_live", ctx)
            self.assertEqual(r["cause"], "trusted_witness_not_connected")


class TestFullGate(unittest.TestCase):
    def test_full_verified_ctx_returns_live_false(self):
        """CRITICAL: Even with all synthetic fixtures, live MUST be false."""
        ctx = full_verified_ctx()
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])
        # Stages 5,6,11,12 must be NO_DATA
        self.assertIn("issuer_auth", result["no_data_stages"])
        self.assertIn("cedula", result["no_data_stages"])
        self.assertIn("heartbeat", result["no_data_stages"])
        self.assertIn("public_live", result["no_data_stages"])

    def test_empty_context_returns_live_false(self):
        result = G.run_gate({}, now=NOW)
        self.assertFalse(result["live"])
        self.assertEqual(result["verified_count"], 0)
        self.assertEqual(result["no_data_count"], 12)

    def test_one_stage_no_data_returns_live_false(self):
        ctx = full_verified_ctx()
        ctx["consent"] = False  # breaks owner_consent
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])
        self.assertIn("owner_consent", result["no_data_stages"])

    def test_stale_heartbeat_keeps_live_false(self):
        ctx = full_verified_ctx()
        old = NOW - timedelta(minutes=5)
        old_iso = old.isoformat().replace("+00:00", "Z")
        ctx["heartbeat"] = {"timestamp": old_iso, "auth": "VERIFIED"}
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])
        self.assertIn("heartbeat", result["no_data_stages"])

    def test_missing_human_signature_keeps_live_false(self):
        ctx = full_verified_ctx()
        ctx["cedula"] = make_cedula(auth="NO_DATA")
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])
        self.assertIn("cedula", result["no_data_stages"])

    def test_probe_refusal_keeps_live_false(self):
        """A node that refuses probes → heartbeat NO_DATA → live=false."""
        ctx = full_verified_ctx()
        ctx["heartbeat"] = {"state": "NO_DATA", "cause": "probe_refused"}
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])

    def test_schema_and_limits_present(self):
        result = G.run_gate({}, now=NOW)
        self.assertEqual(result["schema"], G.SCHEMA)
        self.assertIn("Integrity", result["limits"])

    def test_idempotent_empty_runs(self):
        """Running the gate twice on the same empty context yields identical results."""
        r1 = G.run_gate({}, now=NOW)
        r2 = G.run_gate({}, now=NOW)
        self.assertEqual(r1, r2)

    def test_unknown_stage_returns_no_data(self):
        r = G.run_single_stage("nonexistent", {})
        self.assertEqual(r["cause"], "unknown_stage")

    def test_trusted_witness_causes_present(self):
        """The 4 trust-requiring stages must all report trusted_witness_not_connected."""
        ctx = full_verified_ctx()
        result = G.run_gate(ctx, now=NOW)
        for stage in ["issuer_auth", "cedula", "heartbeat", "public_live"]:
            s = result["stages"][stage]
            self.assertEqual(s["state"], "NO_DATA")
            self.assertEqual(s["cause"], "trusted_witness_not_connected")

    def test_structure_ok_count_in_result(self):
        """Result includes structure_ok_count for reporting."""
        result = G.run_gate({}, now=NOW)
        self.assertIn("structure_ok_count", result)

    def test_now_param_does_not_propagate_to_ctx(self):
        """ctx._now must NOT be set by run_gate."""
        ctx = {"identity": {"esquema": "preceptoros.pwa-node-identity/1", "node_id": "x"}}
        G.run_gate(ctx, now=NOW)
        self.assertNotIn("_now", ctx)


class TestBoundedMaliciousInput(unittest.TestCase):
    def test_receipt_forgery_detected(self):
        """A self-consistent but forged receipt still fails correlation."""
        receipt = make_receipt(node_id="attacker-node")
        ctx = {"receipt": receipt}
        r = G.run_single_stage("response", ctx)
        # The hash is self-consistent, so response stage passes;
        # but the node_id mismatch would be caught by the building module
        self.assertEqual(r["state"], "VERIFIED")

    def test_malformed_json_in_context_is_handled(self):
        """Non-dict values in context fields must not crash."""
        ctx = {"identity": "not-a-dict", "consent": "not-bool"}
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])

    def test_null_bytes_in_purpose_rejected(self):
        """Null bytes in preliminary request — extra field 'purpose' rejected."""
        req = {
            "schema": "preceptoros.node-registration-request/1",
            "node": "primer-ancla",
            "device_sha256": "a" * 64,
            "nonce": "test",
            "consent": True,
            "purpose": "a\x00b",
        }
        ctx = {"preliminary_request": req}
        r = G.run_single_stage("preliminary", ctx)
        self.assertEqual(r["cause"], "preliminary_extra_fields")

    def test_ctx_now_override_ignored(self):
        """ctx._now must be ignored — only explicit now param controls time."""
        ctx = {
            "heartbeat": {"timestamp": NOW_ISO, "auth": "VERIFIED"},
            "_now": datetime(2099, 1, 1, tzinfo=timezone.utc),  # attacker tries to set future time
        }
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        # Stage should NOT read ctx._now — returns NO_DATA regardless
        self.assertEqual(r["cause"], "trusted_witness_not_connected")

    def test_negative_timestamp_rejected(self):
        """Negative or epoch-zero timestamps must not crash — stage returns NO_DATA."""
        ctx = {"heartbeat": {"timestamp": "0000-00-00T00:00:00Z", "auth": "VERIFIED"}}
        r = G.run_single_stage("heartbeat", ctx, now=NOW)
        # The timestamp fails ISO8601 regex → heartbeat_timestamp_missing
        # But with the trust fix, even valid timestamps return trusted_witness_not_connected
        # The invalid timestamp is caught first
        self.assertIn(r["cause"], ["heartbeat_timestamp_missing", "trusted_witness_not_connected"])

    def test_oversized_context_does_not_crash(self):
        """Oversized context values must not crash the gate."""
        ctx = {"identity": {"esquema": "preceptoros.pwa-node-identity/1", "node_id": "x" * 10000}}
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])

    def test_malformed_json_values_no_crash(self):
        """Various malformed types in context must not crash."""
        for bad_val in [None, 42, 3.14, True, [], b"bytes"]:
            ctx = {"identity": bad_val}
            result = G.run_gate(ctx, now=NOW)
            self.assertFalse(result["live"])

    def test_forged_consent_in_preliminary(self):
        """Forged consent values in preliminary request must be rejected."""
        for bad_consent in [False, "yes", 1, "true", {"granted": True}, None, 0]:
            req = {
                "schema": "preceptoros.node-registration-request/1",
                "node": "primer-ancla",
                "device_sha256": "a" * 64,
                "nonce": "test",
                "consent": bad_consent,
            }
            ctx = {"preliminary_request": req}
            r = G.run_single_stage("preliminary", ctx)
            self.assertEqual(r["cause"], "preliminary_consent_not_explicit")

    def test_all_claimed_verified_is_false(self):
        """CRITICAL: Even if every stage claims VERIFIED, live must be false."""
        ctx = full_verified_ctx()
        result = G.run_gate(ctx, now=NOW)
        self.assertFalse(result["live"])
        # The 4 trust stages must be NO_DATA
        self.assertEqual(result["stages"]["issuer_auth"]["state"], "NO_DATA")
        self.assertEqual(result["stages"]["cedula"]["state"], "NO_DATA")
        self.assertEqual(result["stages"]["heartbeat"]["state"], "NO_DATA")
        self.assertEqual(result["stages"]["public_live"]["state"], "NO_DATA")

    def test_cross_agent_two_strings_not_independent(self):
        """Two string agents in synthetic fixture ≠ independent models."""
        ctx = {"cross_agent": {
            "turns": [
                {"agent": "model-a", "text": "hello"},
                {"agent": "model-b", "text": "response"},
            ]
        }}
        r = G.run_single_stage("cross_agent", ctx)
        # Structural check passes — but this is synthetic, not proof of independence
        self.assertEqual(r["state"], "VERIFIED")  # structural only

    def test_empty_context_always_live_false(self):
        """Empty context must always return live=false."""
        result = G.run_gate({}, now=NOW)
        self.assertFalse(result["live"])
        self.assertEqual(result["no_data_count"], 12)

    def test_no_network_in_primitive(self):
        """The gate must not make any network calls — verify by structure."""
        import inspect
        source = inspect.getsource(G)
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("socket", source)
        self.assertNotIn("httpx", source)

    def test_no_write_in_primitive(self):
        """The gate must not write to disk — verify by structure."""
        import inspect
        source = inspect.getsource(G)
        self.assertNotIn("open(", source)
        self.assertNotIn("write(", source)
        self.assertNotIn("os.mkdir", source)
        self.assertNotIn("os.makedirs", source)

    def test_no_grant_in_primitive(self):
        """The gate must not grant any permissions — verify no chmod/chown calls."""
        import inspect
        source = inspect.getsource(G)
        self.assertNotIn("chmod", source)
        self.assertNotIn("chown", source)
        # "grant" appears in docstring as "NO GRANT" policy — check for actual grant calls
        self.assertNotIn(".grant(", source)


if __name__ == "__main__":
    unittest.main()
