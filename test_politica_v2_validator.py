"""Tests for politica_v2_validator.py — red tests first, as specified in the v2 contract.

This test suite validates the deterministic policy-v2 validator with negative tests
and signature fail-closed semantics. Every test is isolated: no shared state, no
network, no filesystem side effects.

Red tests from the spec (odd/tasks/politica-nodo-v2-20261107.md):
- a v1 file reads as posture NO_DATA and signature NO_DATA, with no exception
- an unknown posture → rejected, with cause `posture_not_in_canon`
- `entrada` wider than the posture default → rejected
- `vigencia` with a clock timestamp (not a whole number) → rejected
- a valid shape without a signature → PROPUESTA, never active
- a signature over a different byte → RECHAZADA
- a document of 1,024 B or more → rejected before parsing
- `cerrado` → the public frame carries no building, no cargo and no pressure key
- a sabotage that accepts `hostil` with completion and no signature → the suite goes red
"""

import hashlib
import json
import unittest

import politica_v2_validator as V


# ---------------------------------------------------------------------------
# Helpers — build valid v2 documents for test fixtures
# ---------------------------------------------------------------------------

def _valid_v2_doc(postura="pacifico", entrada=None, vigencia=None, caravanas=None,
                  condiciones=None, firma=None, nodo=None, no_data=None, version="2.0.0"):
    """Build a minimal valid v2 document dict."""
    if entrada is None:
        entrada = ["esperar"]
    if vigencia is None:
        vigencia = {"desde_ciclo": 0, "hasta_ciclo": 100}
    if caravanas is None:
        caravanas = {"acepta": False, "peaje": [], "contrato": "preceptoros:caravana/1"}
    if condiciones is None:
        condiciones = {
            "registro_deudas": {"activo": True},
            "freno_hidraulico": {"activo": True, "decaimiento_ciclos": 10},
            "fork_politico": {"activo": True},
            "colateral_entrada": {"activo": True, "monto_minimo": 50, "max_edificios_solitario": 1},
            "cooperacion_obligatoria": {"firmas_minimas": 2},
            "sandbox_wasmtime": {"activo": False, "ram_max_mib": 64, "io_directo": False,
                                 "estado": "NO_DATA", "causa": "wasmtime_not_compiled"},
        }
    if nodo is None:
        nodo = None
    if no_data is None:
        no_data = [{"campo": "nodo", "causa": "node identity has not been assigned"}]

    doc = {
        "esquema": "preceptoros.politica-nodo/2",
        "version": version,
        "nodo": nodo,
        "no_data": no_data,
        "postura": postura,
        "vigencia": vigencia,
        "entrada": entrada,
        "caravanas": caravanas,
        "condiciones": condiciones,
    }
    if firma is not None:
        doc["firma"] = firma
    return doc


def _to_bytes(doc):
    """Serialize a document dict to canonical JSON bytes."""
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _make_valid_sig(doc):
    """Sign with an ephemeral genuine Ed25519 key. No persisted private key."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        raise unittest.SkipTest("NO_DATA(cryptography_test_dependency_unavailable)")
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    payload = V._canonical_without_firma(doc)
    return {"clave": public.hex(), "sig": "ed25519:" + private.sign(payload).hex()}


# ---------------------------------------------------------------------------
# Red tests from the spec
# ---------------------------------------------------------------------------

class TestV1BackwardCompat(unittest.TestCase):
    """A v1 file reads as posture NO_DATA and signature NO_DATA, with no exception."""

    def test_v1_document_returns_no_data(self):
        v1_doc = {
            "esquema": "preceptoros.politica-nodo/1",
            "version": "1.0.0",
            "nodo": None,
            "no_data": [{"campo": "nodo", "causa": "node identity has not been assigned"}],
            "condiciones": {
                "registro_deudas": {"activo": True},
                "freno_hidraulico": {"activo": True, "decaimiento_ciclos": 10},
                "fork_politico": {"activo": True},
                "colateral_entrada": {"activo": True, "monto_minimo": 50, "max_edificios_solitario": 1},
                "cooperacion_obligatoria": {"firmas_minimas": 2},
                "sandbox_wasmtime": {"activo": False, "ram_max_mib": 64, "io_directo": False,
                                     "estado": "NO_DATA", "causa": "wasmtime_not_compiled"},
            },
        }
        raw = _to_bytes(v1_doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "NO_DATA")
        self.assertIn("NO_DATA", result["causa"])

    def test_v1_document_no_exception_on_any_call(self):
        """Must not raise, even with repeated calls."""
        v1_doc = {
            "esquema": "preceptoros.politica-nodo/1",
            "version": "1.0.0",
            "nodo": None,
            "no_data": [],
            "condiciones": {
                "registro_deudas": {"activo": True},
                "freno_hidraulico": {"activo": True, "decaimiento_ciclos": 10},
                "fork_politico": {"activo": True},
                "colateral_entrada": {"activo": True, "monto_minimo": 50, "max_edificios_solitario": 1},
                "cooperacion_obligatoria": {"firmas_minimas": 2},
                "sandbox_wasmtime": {"activo": False, "ram_max_mib": 64, "io_directo": False,
                                     "estado": "NO_DATA", "causa": "wasmtime_not_compiled"},
            },
        }
        raw = _to_bytes(v1_doc)
        for _ in range(5):
            result = V.validate(raw)
            self.assertEqual(result["estado"], "NO_DATA")


class TestUnknownPosture(unittest.TestCase):
    """An unknown posture → rejected, with cause `posture_not_in_canon`."""

    def test_unknown_posture_rejected(self):
        doc = _valid_v2_doc(postura="anarquico")
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertEqual(result["causa"], "posture_not_in_canon")

    def test_null_posture_rejected(self):
        doc = _valid_v2_doc(postura=None)
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertEqual(result["causa"], "posture_not_in_canon")

    def test_empty_string_posture_rejected(self):
        doc = _valid_v2_doc(postura="")
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertEqual(result["causa"], "posture_not_in_canon")


class TestEntradaWiderThanDefault(unittest.TestCase):
    """`entrada` wider than the posture default → rejected."""

    def test_pacifico_with_reparar_rejected(self):
        """Pacifico allows esperar, recoger — reparar is outside."""
        doc = _valid_v2_doc(postura="pacifico", entrada=["esperar", "recoger", "reparar"])
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("wider than posture", result["causa"])

    def test_cerrado_with_recoger_rejected(self):
        """Cerrado allows only esperar — recoger is outside."""
        doc = _valid_v2_doc(postura="cerrado", entrada=["esperar", "recoger"])
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("wider than posture", result["causa"])

    def test_entrada_with_unknown_action_rejected(self):
        """An action not in customs_agente.ACTIONS at all."""
        doc = _valid_v2_doc(postura="abierto", entrada=["esperar", "invadir"])
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("outside customs_agente.ACTIONS", result["causa"])


class TestVigenciaClockTimestamp(unittest.TestCase):
    """`vigencia` with a clock timestamp (not a whole number) → rejected."""

    def test_float_timestamp_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": 1700000000.5, "hasta_ciclo": 1700000100.5})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("not a whole number", result["causa"])

    def test_iso_string_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": "2026-11-07T00:00:00Z", "hasta_ciclo": "2026-12-07T00:00:00Z"})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("not a whole number", result["causa"])

    def test_negative_cycle_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": -1, "hasta_ciclo": 100})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("negative", result["causa"])

    def test_desde_greater_than_hasta_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": 100, "hasta_ciclo": 50})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("desde_ciclo > hasta_ciclo", result["causa"])


class TestNoSignature(unittest.TestCase):
    """A valid shape without a signature → PROPUESTA, never active."""

    def test_valid_doc_no_sig_is_propuesta(self):
        doc = _valid_v2_doc()
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "PROPUESTA")
        self.assertIn("proposal", result["causa"])

    def test_valid_doc_no_sig_never_ok(self):
        """PROPUESTA is not OK — a proposal is never active."""
        doc = _valid_v2_doc()
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertNotEqual(result["estado"], "OK")

    def test_valid_doc_no_sig_never_rechazada(self):
        """PROPUESTA is not RECHAZADA — it's a valid proposal."""
        doc = _valid_v2_doc()
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertNotEqual(result["estado"], "RECHAZADA")


class TestSignatureOverDifferentBytes(unittest.TestCase):
    """A signature over a different byte → RECHAZADA."""

    def test_sig_over_modified_doc_rejected(self):
        doc = _valid_v2_doc()
        firma = _make_valid_sig(doc)
        doc["firma"] = firma
        raw = _to_bytes(doc)

        # Tamper with the document bytes after signing
        tampered = raw.replace(b"pacifico", b"hostil")
        result = V.validate(tampered)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("signature does not verify", result["causa"])

    def test_sig_with_wrong_key_rejected(self):
        doc = _valid_v2_doc()
        firma = _make_valid_sig(doc)
        # Use a different key
        firma["clave"] = "b" * 64
        doc["firma"] = firma
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("signature does not verify", result["causa"])


class TestDocumentSizeCeiling(unittest.TestCase):
    """A document of 1,024 B or more → rejected before parsing."""

    def test_1024_bytes_rejected(self):
        # Create a document that is exactly 1024 bytes
        doc = _valid_v2_doc()
        # Pad with a long no_data entry to exceed the limit
        doc["no_data"] = [{"campo": "nodo", "causa": "x" * 1000}]
        raw = _to_bytes(doc)
        # Ensure it's at least 1024 bytes
        if len(raw) < 1024:
            raw = raw + b" " * (1024 - len(raw))
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("1024-byte ceiling", result["causa"])

    def test_over_1024_bytes_rejected(self):
        raw = b"{" + b"x" * 2000 + b"}"
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("1024-byte ceiling", result["causa"])


class TestCerradoPosture(unittest.TestCase):
    """`cerrado` → the public frame carries no building, no cargo and no pressure key.

    The validator enforces that `entrada` for `cerrado` is limited to `esperar` only.
    The public frame restriction is an engine concern; the validator ensures the
    posture declaration is consistent.
    """

    def test_cerrado_with_only_esperar_is_propuesta(self):
        doc = _valid_v2_doc(postura="cerrado", entrada=["esperar"])
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "PROPUESTA")

    def test_cerrado_with_recoger_rejected(self):
        doc = _valid_v2_doc(postura="cerrado", entrada=["esperar", "recoger"])
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("wider than posture", result["causa"])


class TestSabotageHostilNoSignature(unittest.TestCase):
    """A sabotage that accepts `hostil` with completion and no signature → the suite goes red.

    This is the critical safety test: `hostil` posture without a signature must
    NEVER return OK. It must return PROPUESTA at best, RECHAZADA at worst.
    """

    def test_hostil_no_sig_never_ok(self):
        """Hostil without signature must not be OK."""
        doc = _valid_v2_doc(postura="hostil")
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertNotEqual(result["estado"], "OK",
                            "SABOTAGE: hostil without signature returned OK")
        self.assertEqual(result["estado"], "PROPUESTA")

    def test_hostil_with_valid_sig_is_unbound(self):
        """Hostil with a real signature is unbound, never authorized."""
        doc = _valid_v2_doc(postura="hostil")
        firma = _make_valid_sig(doc)
        doc["firma"] = firma
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "NO_DATA")


# ---------------------------------------------------------------------------
# Additional coverage — schema, conditions, caravanas, edge cases
# ---------------------------------------------------------------------------

class TestSchemaValidation(unittest.TestCase):
    """Closed schema: no auto_stage, no requires_hitl, no silent insertion."""

    def test_auto_stage_rejected(self):
        """Silently inserting auto_stage must be rejected."""
        doc = _valid_v2_doc()
        doc["auto_stage"] = True
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("unexpected keys", result["causa"])

    def test_requires_hitl_rejected(self):
        """Silently inserting requires_hitl must be rejected."""
        doc = _valid_v2_doc()
        doc["requires_hitl"] = True
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("unexpected keys", result["causa"])

    def test_both_forbidden_keys_rejected(self):
        doc = _valid_v2_doc()
        doc["auto_stage"] = True
        doc["requires_hitl"] = True
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("auto_stage", result["causa"])
        self.assertIn("requires_hitl", result["causa"])


class TestConditionsUnchanged(unittest.TestCase):
    """The six conditions must be unchanged from v1."""

    def test_missing_condition_rejected(self):
        doc = _valid_v2_doc()
        del doc["condiciones"]["sandbox_wasmtime"]
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("condiciones", result["causa"])

    def test_extra_condition_rejected(self):
        doc = _valid_v2_doc()
        doc["condiciones"]["nueva_condicion"] = {"activo": True}
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("condiciones", result["causa"])

    def test_condition_not_dict_rejected(self):
        doc = _valid_v2_doc()
        doc["condiciones"]["registro_deudas"] = True
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")


class TestCaravanasPeaje(unittest.TestCase):
    """Caravan peaje must reference valid engine resources."""

    def test_invalid_resource_rejected(self):
        doc = _valid_v2_doc(caravanas={
            "acepta": True,
            "peaje": [{"resource": "oro", "amount": 10}],
            "contrato": "preceptoros:caravana/1",
        })
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("not in engine resource set", result["causa"])

    def test_negative_amount_rejected(self):
        doc = _valid_v2_doc(caravanas={
            "acepta": True,
            "peaje": [{"resource": "madera", "amount": -5}],
            "contrato": "preceptoros:caravana/1",
        })
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("amount", result["causa"])

    def test_valid_peaje_accepted(self):
        doc = _valid_v2_doc(caravanas={
            "acepta": True,
            "peaje": [{"resource": "madera", "amount": 10}, {"resource": "piedra", "amount": 5}],
            "contrato": "preceptoros:caravana/1",
        })
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "PROPUESTA")


class TestSignatureFormats(unittest.TestCase):
    """Signature format validation."""

    def test_sig_without_ed25519_prefix_rejected(self):
        doc = _valid_v2_doc()
        doc["firma"] = {"clave": "a" * 64, "sig": "deadbeef"}
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("ed25519:", result["causa"])

    def test_firma_not_dict_rejected(self):
        doc = _valid_v2_doc()
        doc["firma"] = "just_a_string"
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")

    def test_valid_signature_is_unbound(self):
        doc = _valid_v2_doc()
        firma = _make_valid_sig(doc)
        doc["firma"] = firma
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "NO_DATA")
        self.assertEqual(result["causa"], "owner_key_binding_to_nodo_not_wired")


class TestSignatureForgeryRegressions(unittest.TestCase):
    def test_hash_based_forgery_never_verifies(self):
        doc = _valid_v2_doc()
        key_hex = "ab" * 32
        payload = V._canonical_without_firma(doc)
        forged_digest = hashlib.sha256((key_hex + payload.decode("utf-8")).encode("utf-8")).hexdigest()
        doc["firma"] = {"clave": key_hex, "sig": "ed25519:" + forged_digest}
        result = V.validate(_to_bytes(doc))
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("signature does not verify", result["causa"])

    def test_unhashable_entry_action_is_rejected(self):
        doc = _valid_v2_doc()
        doc["entrada"] = [["esperar"]]
        self.assertEqual(V.validate(_to_bytes(doc))["estado"], "RECHAZADA")

    def test_unhashable_posture_is_rejected(self):
        doc = _valid_v2_doc()
        doc["postura"] = ["hostil"]
        self.assertEqual(V.validate(_to_bytes(doc))["estado"], "RECHAZADA")


class TestNonBytesInput(unittest.TestCase):
    """Validator must handle non-bytes input without raising."""

    def test_string_input_rejected(self):
        result = V.validate('{"esquema":"preceptoros.politica-nodo/2"}')
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("payload must be bytes", result["causa"])

    def test_dict_input_rejected(self):
        result = V.validate({"esquema": "preceptoros.politica-nodo/2"})
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("payload must be bytes", result["causa"])

    def test_none_input_rejected(self):
        result = V.validate(None)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("payload must be bytes", result["causa"])


class TestAllPosturesValid(unittest.TestCase):
    """All five postures are valid when properly formed."""

    def test_all_postures_acceptable(self):
        for postura in ("pacifico", "hostil", "cooperativo", "cerrado", "abierto"):
            doc = _valid_v2_doc(postura=postura)
            raw = _to_bytes(doc)
            result = V.validate(raw)
            self.assertEqual(
                result["estado"], "PROPUESTA",
                f"postura '{postura}' should be PROPUESTA without signature",
            )


class TestMissingRequiredKeys(unittest.TestCase):
    """Missing required v2 keys → RECHAZADA."""

    def test_missing_postura_rejected(self):
        doc = _valid_v2_doc()
        del doc["postura"]
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("postura", result["causa"])

    def test_missing_vigencia_rejected(self):
        doc = _valid_v2_doc()
        del doc["vigencia"]
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("vigencia", result["causa"])

    def test_missing_condiciones_rejected(self):
        doc = _valid_v2_doc()
        del doc["condiciones"]
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("condiciones", result["causa"])


class TestVigenciaBoolRejection(unittest.TestCase):
    """Boolean values in vigencia must be rejected (bool is subclass of int in Python)."""

    def test_bool_desde_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": True, "hasta_ciclo": 100})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("not a whole number", result["causa"])

    def test_bool_hasta_rejected(self):
        doc = _valid_v2_doc(vigencia={"desde_ciclo": 0, "hasta_ciclo": False})
        raw = _to_bytes(doc)
        result = V.validate(raw)
        self.assertEqual(result["estado"], "RECHAZADA")
        self.assertIn("not a whole number", result["causa"])


class TestDeterministicNoRaise(unittest.TestCase):
    """The validator must never raise an exception."""

    def test_garbage_bytes_no_raise(self):
        result = V.validate(b"\x00\x01\x02\xff\xfe")
        self.assertIn("estado", result)
        self.assertIn("causa", result)

    def test_empty_bytes_no_raise(self):
        result = V.validate(b"")
        self.assertIn("estado", result)
        self.assertIn("causa", result)

    def test_json_array_no_raise(self):
        result = V.validate(b"[1, 2, 3]")
        self.assertEqual(result["estado"], "RECHAZADA")

    def test_json_string_no_raise(self):
        result = V.validate(b'"just a string"')
        self.assertEqual(result["estado"], "RECHAZADA")

    def test_json_null_no_raise(self):
        result = V.validate(b"null")
        self.assertEqual(result["estado"], "RECHAZADA")


if __name__ == "__main__":
    unittest.main()
