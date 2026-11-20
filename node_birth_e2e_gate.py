"""NODE-BIRTH E2E boundary verification primitive.

This module verifies the complete node birth chain as a sequence of stages.
Each stage returns VERIFIED, STRUCTURE_OK, or NO_DATA(cause) — never a blanket
PASS or fabricated authority. The primitive is READ-ONLY, NO NETWORK, NO MUTATION,
NO GRANT by default; tests inject sources and transport fixtures.

CRITICAL: Stages 5-6 (issuer_auth, cedula) and 11-12 (heartbeat, public_live)
ALWAYS return NO_DATA(trusted_witness_not_connected) because they require real
independent cryptographic verification and live public observation that cannot
be satisfied by synthetic fixtures. Structural integrity can be reported as
STRUCTURE_OK separately, but NEVER as authoritative VERIFIED.

The final gate ALWAYS returns live=false until real independent cryptographic
verifier plus live public observer are integrated.

Stages:
  1. source          — node identity source and schema (structural)
  2. owner_consent   — explicit human consent (never auto-granted)
  3. preliminary     — preliminary request shape and bounds (wire schema)
  4. response        — response integrity (receipt hash correlation)
  5. issuer_auth     — verified issuer / SSH credential (requires real verifier)
  6. cedula          — signed SSH cédula (requires real signature check)
  7. provision       — local identity provision
  8. inference       — one local model inference witness
  9. lab_rag         — LAB/RAG context provenance
  10. cross_agent    — cross-agent dialogue evidence
  11. heartbeat       — independently authenticated heartbeat (requires real observer)
  12. public_live    — public World LIVE readback (requires real public node)

The final gate ALWAYS returns live=false.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional

# --- Constants ---

SCHEMA = "preceptoros.node-birth-e2e-gate/1"
NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
NODO_NAME_RE = re.compile(r"^nodo\.[0-9]{1,6}\.[a-z0-9][a-z0-9-]{0,30}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ISO8601_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
HEARTBEAT_TTL_S = 120  # independently observed heartbeat must be ≤ 2 min old

STAGES = [
    "source", "owner_consent", "preliminary", "response",
    "issuer_auth", "cedula", "provision", "inference",
    "lab_rag", "cross_agent", "heartbeat", "public_live",
]


def _canonical(value: Any) -> bytes:
    """Canonical JSON bytes — sorted keys, compact, ASCII-escaped."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def verified(value: Any = None) -> Dict[str, Any]:
    """Return a VERIFIED stage result — only for stages that can be verified without external trust."""
    result: Dict[str, Any] = {"state": "VERIFIED"}
    if value is not None:
        result["value"] = value
    return result


def structure_ok(details: Any = None) -> Dict[str, Any]:
    """Return STRUCTURE_OK — structural checks passed but NOT authoritative verification.

    Use for stages where the shape is correct but real cryptographic verification
    or live observation is not yet available. This is NEVER equivalent to VERIFIED.
    """
    result: Dict[str, Any] = {"state": "STRUCTURE_OK"}
    if details is not None:
        result["details"] = details
    return result


def no_data(cause: str, value: Any = None) -> Dict[str, Any]:
    """Return a NO_DATA stage result with a concrete cause."""
    result: Dict[str, Any] = {"state": "NO_DATA", "cause": cause}
    if value is not None:
        result["value"] = value
    return result


# --- Stage checkers — each is a pure function accepting a context dict ---

def check_source(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 1: verify the node identity source and schema."""
    identity = ctx.get("identity")
    if not isinstance(identity, dict):
        return no_data("identity_missing")
    schema = identity.get("esquema")
    if schema not in ("preceptoros.pwa-node-identity/1", "preceptoros.cedula-nodo/1"):
        return no_data("identity_schema_unknown")
    node_id = identity.get("node_id") or identity.get("nodo")
    if not isinstance(node_id, str):
        return no_data("node_id_missing")
    if not NODE_ID_RE.fullmatch(node_id) and not NODO_NAME_RE.fullmatch(node_id):
        return no_data("node_id_malformed")
    return verified({"node_id": node_id, "schema": schema})


def check_owner_consent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 2: explicit human consent — never auto-granted."""
    consent = ctx.get("consent")
    if consent is not True:
        return no_data("consent_not_explicit")
    consent_timestamp = ctx.get("consent_timestamp")
    if not isinstance(consent_timestamp, str):
        return no_data("consent_timestamp_missing")
    if not ISO8601_Z.fullmatch(consent_timestamp):
        return no_data("consent_timestamp_malformed")
    return verified({"consent": True, "at": consent_timestamp})


def check_preliminary(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 3: preliminary request shape and bounds.

    Wire schema (from mvp-android/docs/ANDROID_JOIN_R1.md):
    The server accepts exactly: schema, node, device_sha256, nonce, consent:true.
    Purpose is UI-local only — never on the wire.
    Reject unapproved extra fields, malformed node/hash/nonce, and non-boolean consent.
    """
    request = ctx.get("preliminary_request")
    if not isinstance(request, dict):
        return no_data("preliminary_request_missing")
    # Wire schema: exactly these 5 fields — reject extra fields
    allowed = {"schema", "node", "device_sha256", "nonce", "consent"}
    if not set(request).issubset(allowed):
        extra = set(request) - allowed
        return no_data("preliminary_extra_fields", value={"extra": sorted(extra)})
    required = {"schema", "node", "device_sha256", "nonce", "consent"}
    if not required.issubset(set(request)):
        return no_data("preliminary_request_incomplete")
    # schema must be present and valid
    if not isinstance(request.get("schema"), str) or not request["schema"].strip():
        return no_data("preliminary_schema_missing")
    # node must match pattern
    node = request.get("node")
    if not isinstance(node, str) or not NODE_ID_RE.fullmatch(node):
        return no_data("preliminary_node_malformed")
    # device_sha256 must be a valid hex64
    device_sha = request.get("device_sha256")
    if not isinstance(device_sha, str) or not HEX64_RE.fullmatch(device_sha):
        return no_data("preliminary_device_sha_malformed")
    # nonce must be a non-empty string
    nonce = request.get("nonce")
    if not isinstance(nonce, str) or not nonce.strip():
        return no_data("preliminary_nonce_missing")
    # consent must be exactly boolean True — never auto-granted
    if request.get("consent") is not True:
        return no_data("preliminary_consent_not_explicit")
    # Size bound: <= 1024 bytes
    body_bytes = len(_canonical(request))
    if body_bytes > 1024:
        return no_data("preliminary_request_oversized")
    return verified({"node": node, "bytes": body_bytes})


def check_response(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 4: response integrity — receipt hash correlation."""
    receipt = ctx.get("receipt")
    if not isinstance(receipt, dict):
        return no_data("receipt_missing")
    recibo_sha = receipt.get("recibo_sha256")
    if not isinstance(recibo_sha, str) or not HEX64_RE.fullmatch(recibo_sha):
        return no_data("receipt_hash_missing")
    # Recompute: all fields except recibo_sha256
    base = {k: v for k, v in receipt.items() if k != "recibo_sha256"}
    computed = hashlib.sha256(_canonical(base)).hexdigest()
    if computed != recibo_sha:
        return no_data("receipt_hash_mismatch")
    payload_sha = receipt.get("payload_sha256")
    if not isinstance(payload_sha, str) or not HEX64_RE.fullmatch(payload_sha):
        return no_data("payload_hash_missing")
    return verified({"recibo_sha256": recibo_sha, "payload_sha256": payload_sha})


def check_issuer_auth(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 5: verified issuer / auth — requires REAL independent cryptographic verifier.

    A self-proclaimed issuer_auth.state=VERIFIED from synthetic context is NOT proof
    of identity. Only an external verifier (e.g., ssh-keygen -Y verify against a
    trusted public key) can establish this. Until integrated, always NO_DATA.
    Structural shape can be reported as STRUCTURE_OK separately.
    """
    issuer = ctx.get("issuer_auth")
    if not isinstance(issuer, dict):
        return no_data("issuer_auth_missing")
    # Structural check only — never authoritative
    state = issuer.get("state")
    if state in ("VERIFIED", "NO_DATA"):
        return no_data("trusted_witness_not_connected",
                       value={"structure": "present", "note": "requires_real_verifier"})
    return no_data("trusted_witness_not_connected",
                   value={"structure": "present", "note": "requires_real_verifier"})


def check_cedula(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 6: signed SSH cédula / credential — requires REAL signature verification.

    A user-controlled cedula.autenticidad=OK is NOT proof of signature.
    Only an external verifier (e.g., ssh-keygen -Y verify against a trusted
    public key) can establish authenticity. Until integrated, always NO_DATA.
    Structural integrity (hash consistency) can be checked separately.
    """
    cedula = ctx.get("cedula")
    if not isinstance(cedula, dict):
        return no_data("cedula_missing")
    # Structural integrity check — hash consistency only, NOT authenticity
    sha = cedula.get("sha256")
    if not isinstance(sha, str) or not HEX64_RE.fullmatch(sha):
        return no_data("cedula_hash_missing")
    body = {k: v for k, v in cedula.items() if k not in ("sha256", "firma_ssh", "firma", "autenticidad")}
    computed = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if computed != sha:
        return no_data("cedula_hash_mismatch")
    # Structural shape is OK but signature is NOT verified without external verifier
    # Never trust an injected "OK" — that is user-controlled data
    return no_data("trusted_witness_not_connected",
                   value={"structure": "integrity_ok", "note": "requires_real_signature_check"})


def check_provision(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 7: local identity provision — atomic, private, idempotent."""
    provision = ctx.get("provision")
    if not isinstance(provision, dict):
        return no_data("provision_missing")
    estado = provision.get("estado")
    if estado == "provisionada":
        return verified({"node_id": provision.get("node_id")})
    if estado == "NO_DATA":
        return no_data(provision.get("causa", "provision_no_data"))
    return no_data("provision_unexpected_state")


def check_inference(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 8: one local model inference — distinguishes presence vs inference vs agent running."""
    inference = ctx.get("inference")
    if not isinstance(inference, dict):
        return no_data("inference_missing")
    state = inference.get("state")
    if state == "VERIFIED":
        model = inference.get("model")
        if not isinstance(model, str) or not model:
            return no_data("inference_model_missing")
        return verified({"model": model, "latency_ms": inference.get("latency_ms")})
    if state == "MODEL_PRESENT":
        return no_data("model_present_no_inference")
    if state == "NO_DATA":
        return no_data(inference.get("cause", "inference_no_data"))
    return no_data("inference_unexpected_state")


def check_lab_rag(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 9: LAB/RAG context provenance — source ref and freshness."""
    lab = ctx.get("lab_rag")
    if not isinstance(lab, dict):
        return no_data("lab_rag_missing")
    state = lab.get("state")
    if state == "VERIFIED":
        source_ref = lab.get("source_ref")
        if not isinstance(source_ref, str) or not HEX64_RE.fullmatch(source_ref):
            return no_data("lab_rag_source_ref_invalid")
        return verified({"source_ref": source_ref, "node": lab.get("node")})
    if state == "NO_DATA":
        return no_data(lab.get("cause", "lab_rag_no_data"))
    if state == "STALE":
        return no_data("lab_rag_stale")
    return no_data("lab_rag_unexpected_state")


def check_cross_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 10: cross-agent dialogue — evidence of multi-agent turn exchange."""
    dialogue = ctx.get("cross_agent")
    if not isinstance(dialogue, dict):
        return no_data("cross_agent_missing")
    turns = dialogue.get("turns")
    if not isinstance(turns, list) or len(turns) < 2:
        return no_data("cross_agent_insufficient_turns")
    agents = set()
    for t in turns:
        if not isinstance(t, dict):
            return no_data("cross_agent_turn_malformed")
        agent = t.get("agent")
        if not isinstance(agent, str):
            return no_data("cross_agent_agent_missing")
        agents.add(agent)
    if len(agents) < 2:
        return no_data("cross_agent_single_agent_only")
    return verified({"agents": sorted(agents), "turns": len(turns)})


def check_heartbeat(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 11: independently authenticated time-bounded heartbeat.

    Requires a REAL independent observer with cryptographic authentication.
    A supplied heartbeat.auth=VERIFIED string is NOT proof of independent
    authentication. ctx._now is NEVER honored — only the explicit `now`
    parameter in run_gate/run_single_stage controls time. Until a real
    observer is integrated, always NO_DATA.
    """
    hb = ctx.get("heartbeat")
    if not isinstance(hb, dict):
        return no_data("heartbeat_missing")
    # Structural check: timestamp shape
    ts = hb.get("timestamp")
    if not isinstance(ts, str) or not ISO8601_Z.fullmatch(ts):
        return no_data("heartbeat_timestamp_missing")
    # Never trust injected auth=VERIFIED — requires real independent observer
    return no_data("trusted_witness_not_connected",
                   value={"structure": "present", "note": "requires_real_observer"})


def check_public_live(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 12: public World LIVE readback — requires REAL live public observer.

    A string value for public_live.observer is NOT proof of a live public node.
    Only a real, independently operated public observer with cryptographic proof
    can establish LIVE status. Until integrated, always NO_DATA.
    """
    live = ctx.get("public_live")
    if not isinstance(live, dict):
        return no_data("public_live_missing")
    # Structural check only — never authoritative
    return no_data("trusted_witness_not_connected",
                   value={"structure": "present", "note": "requires_real_public_observer"})


# --- Gate orchestrator ---

_STAGE_CHECKERS = {
    "source": check_source,
    "owner_consent": check_owner_consent,
    "preliminary": check_preliminary,
    "response": check_response,
    "issuer_auth": check_issuer_auth,
    "cedula": check_cedula,
    "provision": check_provision,
    "inference": check_inference,
    "lab_rag": check_lab_rag,
    "cross_agent": check_cross_agent,
    "heartbeat": check_heartbeat,
    "public_live": check_public_live,
}


def run_gate(ctx: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run the full E2E gate on the given context.

    Returns a machine-readable result with per-stage evidence and an overall
    ``live`` flag that is ALWAYS ``false`` until real independent cryptographic
    verifier plus live public observer are integrated.

    IMPORTANT: The ``now`` parameter is ONLY for deterministic testing.
    ctx._now is NEVER honored — it cannot be used to override time.
    """
    # NEVER propagate _now into ctx — only the explicit `now` param is trusted
    # Do NOT do: ctx = dict(ctx, _now=now)
    now_ts = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    stages: Dict[str, Dict[str, Any]] = {}
    for stage_name in STAGES:
        checker = _STAGE_CHECKERS[stage_name]
        stages[stage_name] = checker(ctx)

    # Count states for reporting
    verified_count = sum(1 for s in stages.values() if s["state"] == "VERIFIED")
    structure_ok_count = sum(1 for s in stages.values() if s["state"] == "STRUCTURE_OK")
    no_data_stages = [name for name, s in stages.items() if s["state"] == "NO_DATA"]

    # ALWAYS live=false — stages 5,6,11,12 require real external verification
    return {
        "schema": SCHEMA,
        "live": False,
        "observed_at": now_ts,
        "stages": stages,
        "verified_count": verified_count,
        "structure_ok_count": structure_ok_count,
        "no_data_count": len(no_data_stages),
        "no_data_stages": no_data_stages,
        "limits": "Integrity is not authenticity. A receipt is not admission. A snapshot is not LIVE. Structural checks are STRUCTURE_OK, never VERIFIED.",
    }


def run_single_stage(stage: str, ctx: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run a single stage checker for targeted testing.

    The ``now`` parameter is accepted for API compatibility but is NOT propagated
    to stage checkers (they must not rely on ctx._now).
    """
    if stage not in _STAGE_CHECKERS:
        return no_data("unknown_stage")
    # Do NOT propagate _now — stages must not read it
    return _STAGE_CHECKERS[stage](ctx)
