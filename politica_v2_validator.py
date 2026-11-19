"""Policy node v2 validator — proposal-only, deterministic, fail-closed on signatures.

This module validates documents against the closed schema
`preceptoros.politica-nodo/2` defined in
`odd/tasks/politica-nodo-v2-20261107.md`.

Design principles (carried from soberania.py):
- Never raises. Returns `{estado, causa}` on every path.
- Missing signature → PROPUESTA (proposal, never active).
- Invalid signature → RECHAZADA (fail-closed).
- v1 documents read as posture NO_DATA and signature NO_DATA, with no exception.
- Schema is closed: no `auto_stage`, no `requires_hitl`, no silent insertion.

The validator is isolated: real Ed25519 uses optional cryptography and
`customs_agente.ACTIONS` for entry validation. It does not import estado,
soberania, casa, or any runtime gate.
"""

import json

LIMIT = 1024

# Closed schema identifier for v2
SCHEMA_V2 = "preceptoros.politica-nodo/2"
SCHEMA_V1 = "preceptoros.politica-nodo/1"

# The six v1 conditions — unchanged in v2
POLICY_CONDITIONS = frozenset({
    "registro_deudas",
    "freno_hidraulico",
    "fork_politico",
    "colateral_entrada",
    "cooperacion_obligatoria",
    "sandbox_wasmtime",
})

# Posture enum — closed set from the canon
POSTURAS = frozenset({
    "pacifico",
    "hostil",
    "cooperativo",
    "cerrado",
    "abierto",
})

# Entry actions allowed per posture (from the v2 spec table)
# customs_agente.ACTIONS = ("esperar", "recoger", "reparar", "aplazar", "bajar_a")
POSTURA_ENTRADA_DEFAULTS = {
    "pacifico": frozenset({"esperar", "recoger"}),
    "hostil": frozenset({"esperar", "recoger", "bajar_a"}),
    "cooperativo": frozenset({"esperar", "recoger", "reparar"}),
    "cerrado": frozenset({"esperar"}),
    "abierto": frozenset({"esperar", "recoger", "reparar", "aplazar", "bajar_a"}),
}

# All actions from customs_agente (closed set)
ALL_ACTIONS = frozenset({"esperar", "recoger", "reparar", "aplazar", "bajar_a"})

# Closed key set for v2 documents
V2_KEYS = frozenset({
    "esquema",
    "version",
    "nodo",
    "no_data",
    "postura",
    "vigencia",
    "entrada",
    "caravanas",
    "condiciones",
    "firma",
})

# Closed key set for v1 documents (for backward compat reading)
V1_KEYS = frozenset({
    "esquema",
    "version",
    "nodo",
    "no_data",
    "condiciones",
})

# Engine resources for caravan peaje validation.
# The v2 spec references `atlas.oferta/1` which is not yet defined in the codebase.
# This is a closed set of known engine resources; peaje entries must reference one of these.
# NO_DATA(atlas_oferta_not_yet_defined) — this set is a best-effort enumeration from
# existing game state fields (casa.py, estado_app.py references).
ENGINE_RESOURCES = frozenset({
    "madera",
    "piedra",
    "comida",
    "energia",
    "metal",
})


def _canonical_without_firma(doc):
    """Produce the canonical JSON bytes of a v2 doc without the `firma` key.

    This is the payload over which the signature is computed.
    """
    stripped = {k: v for k, v in doc.items() if k != "firma"}
    return json.dumps(stripped, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _verify_ed25519_signature(sig_hex, pubkey_hex, payload):
    """Verify REAL Ed25519 or fail closed. Hashing public data is not a signature."""
    try:
        pubkey = bytes.fromhex(pubkey_hex)
        signature = bytes.fromhex(sig_hex)
    except (ValueError, TypeError):
        return False
    if len(pubkey) != 32 or len(signature) != 64:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pubkey).verify(signature, payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def validate_v2(raw):
    """Validate a policy node v2 document.

    Args:
        raw: bytes — the raw document bytes (canonical JSON).

    Returns:
        dict with keys `estado` and `causa`.
        - estado: "OK" | "PROPUESTA" | "RECHAZADA" | "NO_DATA"
        - causa: str — empty on OK, descriptive cause otherwise.

    Validation order (fixed, from the spec):
    1. bytes < 1,024
    2. valid JSON
    3. closed key set for /2 (v1 files read as posture NO_DATA, signature NO_DATA)
    4. postura in enum
    5. vigencia.desde_ciclo ≤ hasta_ciclo, both whole numbers ≥ 0
    6. entrada ⊆ customs_agente.ACTIONS, and ⊆ posture default
    7. caravanas.peaje holds whole engine resources
    8. the six conditions are unchanged from v1
    9. signature verification (missing → PROPUESTA, invalid → RECHAZADA)
    """
    # 1. Byte ceiling
    if not isinstance(raw, bytes):
        return {"estado": "RECHAZADA", "causa": "payload must be bytes"}
    if len(raw) >= LIMIT:
        return {"estado": "RECHAZADA", "causa": "document reaches the 1024-byte ceiling"}

    # 2. Valid JSON
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"estado": "RECHAZADA", "causa": "document is not valid UTF-8 JSON"}
    if not isinstance(doc, dict):
        return {"estado": "RECHAZADA", "causa": "document root is not an object"}

    # 3. Schema dispatch — v1 vs v2
    esquema = doc.get("esquema")
    if esquema == SCHEMA_V1:
        # v1 document: posture and signature are NO_DATA
        v1_extra = set(doc) - V1_KEYS
        if v1_extra:
            return {
                "estado": "NO_DATA",
                "causa": f"v1 document has unexpected keys: {sorted(v1_extra)}",
            }
        return {
            "estado": "NO_DATA",
            "causa": "v1 document · postura and firma are NO_DATA",
        }

    if esquema != SCHEMA_V2:
        return {
            "estado": "RECHAZADA",
            "causa": f"schema is not {SCHEMA_V2}: {esquema!r}",
        }

    # 3b. Closed key set for v2
    doc_keys = set(doc)
    extra_keys = doc_keys - V2_KEYS
    if extra_keys:
        return {
            "estado": "RECHAZADA",
            "causa": f"unexpected keys in v2 document: {sorted(extra_keys)}",
        }

    # Check required v2 keys (excluding firma which is optional)
    required_v2 = {"esquema", "version", "nodo", "no_data", "postura", "vigencia", "entrada", "caravanas", "condiciones"}
    missing_keys = required_v2 - doc_keys
    if missing_keys:
        return {
            "estado": "RECHAZADA",
            "causa": f"missing required v2 keys: {sorted(missing_keys)}",
        }

    # 4. Postura in enum
    postura = doc.get("postura")
    if not isinstance(postura, str) or postura not in POSTURAS:
        return {
            "estado": "RECHAZADA",
            "causa": "posture_not_in_canon",
        }

    # 5. Vigencia: desde_ciclo ≤ hasta_ciclo, both whole numbers ≥ 0
    vigencia = doc.get("vigencia")
    if not isinstance(vigencia, dict):
        return {
            "estado": "RECHAZADA",
            "causa": "vigencia is not an object",
        }
    desde = vigencia.get("desde_ciclo")
    hasta = vigencia.get("hasta_ciclo")
    # Must be whole numbers (int, not bool, not float, not str)
    for field_name, val in [("desde_ciclo", desde), ("hasta_ciclo", hasta)]:
        if isinstance(val, bool) or not isinstance(val, int):
            return {
                "estado": "RECHAZADA",
                "causa": f"vigencia.{field_name} is not a whole number ≥ 0",
            }
        if val < 0:
            return {
                "estado": "RECHAZADA",
                "causa": f"vigencia.{field_name} is negative",
            }
    if desde > hasta:
        return {
            "estado": "RECHAZADA",
            "causa": "vigencia.desde_ciclo > hasta_ciclo",
        }

    # 6. Entrada ⊆ ALL_ACTIONS and ⊆ posture default
    entrada = doc.get("entrada")
    if not isinstance(entrada, list):
        return {
            "estado": "RECHAZADA",
            "causa": "entrada is not an array",
        }
    if any(not isinstance(action, str) for action in entrada):
        return {"estado": "RECHAZADA", "causa": "entrada actions must be strings"}
    entrada_set = set(entrada)
    if not entrada_set.issubset(ALL_ACTIONS):
        outside = entrada_set - ALL_ACTIONS
        return {
            "estado": "RECHAZADA",
            "causa": f"entrada contains actions outside customs_agente.ACTIONS: {sorted(outside)}",
        }
    posture_default = POSTURA_ENTRADA_DEFAULTS[postura]
    if not entrada_set.issubset(posture_default):
        wider = entrada_set - posture_default
        return {
            "estado": "RECHAZADA",
            "causa": f"entrada wider than posture '{postura}' default: {sorted(wider)}",
        }

    # 7. Caravanas.peaje holds whole engine resources
    caravanas = doc.get("caravanas")
    if not isinstance(caravanas, dict):
        return {
            "estado": "RECHAZADA",
            "causa": "caravanas is not an object",
        }
    peaje = caravanas.get("peaje", [])
    if not isinstance(peaje, list):
        return {
            "estado": "RECHAZADA",
            "causa": "caravanas.peaje is not an array",
        }
    for i, entry in enumerate(peaje):
        if not isinstance(entry, dict):
            return {
                "estado": "RECHAZADA",
                "causa": f"caravanas.peaje[{i}] is not an object",
            }
        resource = entry.get("resource")
        if not isinstance(resource, str) or resource not in ENGINE_RESOURCES:
            return {
                "estado": "RECHAZADA",
                "causa": f"caravanas.peaje[{i}].resource '{resource}' not in engine resource set",
            }
        amount = entry.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            return {
                "estado": "RECHAZADA",
                "causa": f"caravanas.peaje[{i}].amount is not a non-negative integer",
            }

    # 8. Six conditions unchanged from v1
    condiciones = doc.get("condiciones")
    if not isinstance(condiciones, dict):
        return {
            "estado": "RECHAZADA",
            "causa": "condiciones is not an object",
        }
    if set(condiciones) != POLICY_CONDITIONS:
        return {
            "estado": "RECHAZADA",
            "causa": f"condiciones keys do not match the closed six-condition set",
        }
    for cond_name, cond_val in condiciones.items():
        if not isinstance(cond_val, dict):
            return {
                "estado": "RECHAZADA",
                "causa": f"condiciones['{cond_name}'] is not an object",
            }

    # 9. Signature verification
    firma = doc.get("firma")
    if firma is None:
        # No signature → PROPUESTA, never active
        return {
            "estado": "PROPUESTA",
            "causa": "no signature · document is a proposal",
        }
    if not isinstance(firma, dict):
        return {
            "estado": "RECHAZADA",
            "causa": "firma is not an object",
        }
    clave = firma.get("clave")
    sig = firma.get("sig")
    if not isinstance(clave, str) or not isinstance(sig, str):
        return {
            "estado": "RECHAZADA",
            "causa": "firma.clave or firma.sig is not a string",
        }
    # Parse ed25519:<hex> format
    if not sig.startswith("ed25519:"):
        return {
            "estado": "RECHAZADA",
            "causa": "firma.sig does not start with 'ed25519:'",
        }
    sig_hex = sig[len("ed25519:"):]

    # Verify over canonical JSON without firma
    payload = _canonical_without_firma(doc)
    if not _verify_ed25519_signature(sig_hex, clave, payload):
        return {
            "estado": "RECHAZADA",
            "causa": "signature does not verify over canonical JSON without firma",
        }

    # Cryptographic validity is not authorization. Public key has no verified
    # binding to the human owner of this node in the canonical registry.
    return {"estado": "NO_DATA", "causa": "owner_key_binding_to_nodo_not_wired"}


def validate(raw):
    """Public entry point: validate a policy node document (v1 or v2).

    Dispatches to the appropriate validator based on the schema field.
    For v1 documents, returns NO_DATA for posture and signature.
    For v2 documents, runs the full v2 validation pipeline.
    """
    return validate_v2(raw)
