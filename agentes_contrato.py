"""Fail-closed validation for Superbot agent cards and task grants.

This module validates existing `preceptoros.agent-card/1` declarations and a
task-bound `preceptoros.agent-grant/1`. It creates no keys, grants, storage,
dispatches, or permissions. Cryptographic checks reuse the APP's existing
`cuenta_cangrejo` SSHSIG verifier and the node's private `allowed_signers`
trust file. A card or model-supplied field is never treated as authentication.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import cuenta_cangrejo

CARD_SCHEMA = "preceptoros.agent-card/1"
GRANT_SCHEMA = "preceptoros.agent-grant/1"
GRANT_NAMESPACE = "preceptoros-agent-grant"
CARD_LIMIT = 1024
GRANT_LIMIT = 4096
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
CAPABILITIES = frozenset({"talk.read", "talk.write", "lab.read_document", "lab.propose",
                          "notebook.receipt", "memory.propose"})
RESERVED = frozenset({"soberano", "sovereign", "orquestador", "hexelion-door", "door", "system"})
CARD_AUTHORITY = "none: a card declares and requests; it never grants"
CARD_FIELDS = {"schema", "fixture", "agent", "contributor", "model", "key", "requests", "conditions", "authority"}


def _result(state: str, cause: str, **extra):
    return {"state": state, "cause": cause, **extra}


def canonical_bytes(value) -> bytes:
    """Canonical UTF-8 JSON used only for grant signing and content hashes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate_json_key")
        out[key] = value
    return out


def parse_card(raw: bytes):
    if not isinstance(raw, bytes):
        return _result("REJECTED", "card_must_be_bytes")
    if not 0 < len(raw) < CARD_LIMIT:
        return _result("REJECTED", "card_byte_limit")
    try:
        card = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs_no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non_finite_json")))
    except (UnicodeDecodeError, ValueError, TypeError):
        return _result("REJECTED", "card_json_invalid")
    checked = validate_card(card)
    if checked["state"] != "DECLARED":
        return checked
    return _result("DECLARED", "card_validated_as_declaration_only", card=card,
                   card_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def parse_grant(raw: bytes):
    """Parse a private grant without duplicate-key or non-finite JSON ambiguity."""
    if not isinstance(raw, bytes):
        return _result("REJECTED", "grant_must_be_bytes")
    if not 0 < len(raw) <= GRANT_LIMIT:
        return _result("REJECTED", "grant_byte_limit")
    try:
        grant = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non_finite_json")))
    except (UnicodeDecodeError, ValueError, TypeError):
        return _result("REJECTED", "grant_json_invalid")
    checked = validate_grant(grant)
    if checked["state"] != "STRUCTURALLY_VALID":
        return checked
    return _result("STRUCTURALLY_VALID", "grant_bytes_parsed_strictly", grant=grant,
                   grant_file_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def _nodata(value):
    return (isinstance(value, dict) and set(value) == {"state", "cause"} and
            value.get("state") == "NO_DATA" and isinstance(value.get("cause"), str) and
            1 <= len(value["cause"]) <= 120)


def validate_card(card):
    """Check Companion #31 card semantics. Success is DECLARED, never AUTHENTICATED."""
    if not isinstance(card, dict) or set(card) != CARD_FIELDS:
        return _result("REJECTED", "card_fields_invalid")
    if card.get("schema") != CARD_SCHEMA or not isinstance(card.get("fixture"), bool):
        return _result("REJECTED", "card_schema_or_fixture_invalid")
    agent = card.get("agent")
    if not isinstance(agent, dict) or set(agent) != {"id", "name", "kind", "route"}:
        return _result("REJECTED", "agent_identity_invalid")
    aid = agent.get("id")
    if not isinstance(aid, str) or not SLUG.fullmatch(aid) or aid in RESERVED:
        return _result("REJECTED", "agent_id_invalid_or_reserved")
    if not isinstance(agent.get("name"), str) or not (1 <= len(agent["name"]) <= 24):
        return _result("REJECTED", "agent_name_invalid")
    if agent.get("kind") not in {"node", "rack-cli", "private", "external"} or agent.get("route") not in {"thread", "station", "none"}:
        return _result("REJECTED", "agent_route_invalid")
    if not isinstance(card.get("contributor"), str) or not SLUG.fullmatch(card["contributor"]):
        return _result("REJECTED", "contributor_invalid")
    model = card.get("model")
    if not (_nodata(model) or (isinstance(model, dict) and set(model) == {"name", "sha256"} and
                               isinstance(model.get("name"), str) and 1 <= len(model["name"]) <= 60 and
                               isinstance(model.get("sha256"), str) and HEX64.fullmatch(model["sha256"]))):
        return _result("REJECTED", "model_declaration_invalid")
    key = card.get("key")
    if card["fixture"]:
        if not _nodata(key):
            return _result("REJECTED", "fixture_key_must_be_nodata")
    elif not (isinstance(key, dict) and set(key) == {"alg", "public_hex", "registry"} and
              key.get("alg") == "ed25519" and isinstance(key.get("public_hex"), str) and
              HEX64.fullmatch(key["public_hex"]) and isinstance(key.get("registry"), str) and
              re.fullmatch(r"babel registry/keys/[A-Za-z0-9._-]{1,60}", key["registry"])):
        return _result("REJECTED", "real_agent_key_declaration_invalid")
    requests = card.get("requests")
    if (not isinstance(requests, list) or not 1 <= len(requests) <= 6 or
            any(not isinstance(x, str) or x not in CAPABILITIES for x in requests) or
            len(set(requests)) != len(requests)):
        return _result("REJECTED", "requested_capabilities_invalid")
    conditions = card.get("conditions")
    if not (_nodata(conditions) or
            (isinstance(conditions, dict) and set(conditions) == {"ref", "sha256"} and
             isinstance(conditions.get("ref"), str) and 1 <= len(conditions["ref"]) <= 120 and
             isinstance(conditions.get("sha256"), str) and HEX64.fullmatch(conditions["sha256"]))):
        return _result("REJECTED", "conditions_declaration_invalid")
    if card.get("authority") != CARD_AUTHORITY:
        return _result("REJECTED", "card_cannot_assert_authority")
    return _result("DECLARED", "card_is_a_request_not_a_grant")


def _key_material(public_path: Path):
    """Read the raw Ed25519 bytes from an existing OpenSSH .pub key."""
    try:
        fields = public_path.read_text(encoding="ascii").split()
        if len(fields) < 2 or fields[0] != "ssh-ed25519":
            return None
        blob = base64.b64decode(fields[1], validate=True)
        n = int.from_bytes(blob[:4], "big")
        if n != 11 or blob[4:15] != b"ssh-ed25519":
            return None
        m = int.from_bytes(blob[15:19], "big")
        raw = blob[19:19 + m]
        return raw.hex() if m == 32 and len(raw) == 32 else None
    except (OSError, UnicodeError, ValueError):
        return None


def authenticate_message(card, account, signature, payload: bytes, *, allowed_signers, agent_key_dir):
    """Cryptographically authenticate signed bytes to a linked card key.

    Trust is anchored in the existing Sovereign-signed crab account plus its
    host-local key file. A card's registry path and public key are declarations
    only. The caller must provide the host's configured trust paths.
    """
    card_result = validate_card(card)
    if card_result["state"] != "DECLARED":
        return _result("REJECTED", "card_invalid")
    if card.get("fixture"):
        return _result("NO_DATA", "fixture_identity_is_test_only")
    if not isinstance(payload, bytes) or len(payload) >= CARD_LIMIT:
        return _result("REJECTED", "signed_message_byte_limit")
    if not allowed_signers or not Path(allowed_signers).is_file():
        return _result("NO_DATA", "authentication_trust_anchor_unavailable")
    if not agent_key_dir or not Path(agent_key_dir).is_dir():
        return _result("NO_DATA", "agent_key_registry_unavailable")
    account_result = cuenta_cangrejo.verificar_cuenta(account, allowed_signers)
    if account_result.get("estado") != "OK" or account.get("estado") != "linkeado":
        return _result("REJECTED" if account_result.get("estado") == "RECHAZADA" else "NO_DATA",
                       "agent_account_not_authenticated")
    key_file = None
    expected_fp = account.get("clave_publica")
    for candidate in Path(agent_key_dir).glob("*.pub"):
        digest = hashlib.sha256(candidate.read_bytes().strip()).hexdigest()
        if digest == expected_fp:
            key_file = candidate
            break
    if key_file is None:
        return _result("NO_DATA", "agent_public_key_unavailable")
    if _key_material(key_file) != card["key"].get("public_hex"):
        return _result("REJECTED", "card_key_does_not_match_authenticated_account")
    verified = cuenta_cangrejo.verificar_firma(account, signature, payload, key_file)
    if verified.get("estado") != "OK":
        return _result("REJECTED" if verified.get("estado") == "RECHAZADA" else "NO_DATA",
                       "agent_message_signature_invalid")
    return _result("AUTHENTICATED", "signature_and_host_trust_chain_verified",
                   agent_id=card["agent"]["id"], key_fingerprint=expected_fp,
                   payload_sha256=hashlib.sha256(payload).hexdigest())


def validate_grant(grant):
    fields = {"schema", "grant_id", "agent_id", "card_sha256", "key_fingerprint", "task_sha256",
              "capability", "device_id", "scope", "conditions_accepted_sha256", "not_before",
              "expires_at", "nonce", "signature"}
    if not isinstance(grant, dict) or set(grant) != fields:
        return _result("REJECTED", "grant_fields_invalid")
    if grant.get("schema") != GRANT_SCHEMA:
        return _result("REJECTED", "grant_schema_unknown")
    for name in ("grant_id", "card_sha256", "key_fingerprint", "task_sha256", "conditions_accepted_sha256"):
        if not isinstance(grant.get(name), str) or not HEX64.fullmatch(grant[name]):
            return _result("REJECTED", "grant_digest_invalid", field=name)
    if not isinstance(grant.get("agent_id"), str) or not SLUG.fullmatch(grant["agent_id"]):
        return _result("REJECTED", "grant_agent_invalid")
    if grant.get("capability") not in CAPABILITIES or grant.get("scope") != [grant.get("capability")]:
        return _result("REJECTED", "grant_scope_invalid")
    if not isinstance(grant.get("device_id"), str) or not SLUG.fullmatch(grant["device_id"]):
        return _result("REJECTED", "grant_device_invalid")
    if not isinstance(grant.get("nonce"), str) or not HEX64.fullmatch(grant["nonce"]):
        return _result("REJECTED", "grant_nonce_invalid")
    if not isinstance(grant.get("signature"), str) or not grant["signature"].strip():
        return _result("NO_DATA", "grant_signature_missing")
    try:
        start = _parse_time(grant.get("not_before"))
        expiry = _parse_time(grant.get("expires_at"))
    except (TypeError, ValueError):
        return _result("REJECTED", "grant_time_invalid")
    if expiry <= start:
        return _result("REJECTED", "grant_expiry_not_after_start")
    return _result("STRUCTURALLY_VALID", "signature_and_runtime_conditions_still_required")


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("not a timestamp")
    parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=dt.timezone.utc)


def evaluate_authorization(card_raw: bytes, grant_raw: bytes, *, account, message_signature, signed_message: bytes,
                           allowed_signers, agent_key_dir, task_bytes: bytes, capability, device_id,
                           conditions_bytes: bytes, now, revoked_grant_ids,
                           consumed_grant_ids):
    """Verify all bindings and return eligibility; never dispatch or consume a grant.

    `grant_signers`, revocation, and consumption data must be read from the
    private host state by the future APP adapter. Missing host evidence fails
    closed. Atomic consumption is a separate journal operation and is not
    implemented here, so success is ELIGIBLE_FOR_ATOMIC_CLAIM, not RUNNING.
    """
    parsed_card = parse_card(card_raw)
    if parsed_card["state"] != "DECLARED":
        return parsed_card
    card = parsed_card["card"]
    if card.get("fixture"):
        return _result("REJECTED", "card_not_eligible_for_runtime")
    identity = authenticate_message(card, account, message_signature, signed_message,
                                    allowed_signers=allowed_signers, agent_key_dir=agent_key_dir)
    if identity.get("state") != "AUTHENTICATED":
        return _result(identity.get("state", "NO_DATA"), identity.get("cause", "authentication_unverified"))
    parsed_grant = parse_grant(grant_raw)
    if parsed_grant["state"] != "STRUCTURALLY_VALID":
        return parsed_grant
    grant = parsed_grant["grant"]
    g = validate_grant(grant)
    if g["state"] != "STRUCTURALLY_VALID":
        return g
    if not isinstance(allowed_signers, (str, Path)) or not Path(allowed_signers).is_file():
        return _result("NO_DATA", "grant_trust_anchor_unavailable")
    if revoked_grant_ids is None:
        return _result("NO_DATA", "grant_revocation_state_unavailable")
    if consumed_grant_ids is None:
        return _result("NO_DATA", "grant_replay_state_unavailable")
    try:
        instant = now if isinstance(now, dt.datetime) else _parse_time(now)
        if instant.tzinfo is None:
            return _result("REJECTED", "evaluation_time_must_be_timezone_aware")
        instant = instant.astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return _result("REJECTED", "evaluation_time_invalid")
    signed = {k: v for k, v in grant.items() if k != "signature"}
    signer_state, _ = cuenta_cangrejo._verify_signer(canonical_bytes(signed), grant["signature"],
                                                     allowed_signers, "soberano", GRANT_NAMESPACE)
    if signer_state != "OK":
        return _result("REJECTED" if signer_state == "RECHAZADA" else "NO_DATA", "grant_signature_unverified")
    if grant["grant_id"] in revoked_grant_ids:
        return _result("REJECTED", "grant_revoked")
    if grant["grant_id"] in consumed_grant_ids:
        return _result("REJECTED", "grant_replayed_or_consumed")
    if grant["agent_id"] != card["agent"]["id"] or grant["card_sha256"] != parsed_card["card_sha256"]:
        return _result("REJECTED", "grant_card_or_agent_mismatch")
    if identity.get("key_fingerprint") != grant["key_fingerprint"]:
        return _result("REJECTED", "grant_identity_mismatch")
    if not isinstance(task_bytes, bytes) or grant["task_sha256"] != hashlib.sha256(task_bytes).hexdigest():
        return _result("REJECTED", "grant_task_mismatch")
    if grant["capability"] != capability or capability not in card["requests"]:
        return _result("REJECTED", "grant_capability_not_requested_or_mismatched")
    if grant["device_id"] != device_id:
        return _result("REJECTED", "grant_device_mismatch")
    if not isinstance(conditions_bytes, bytes) or not conditions_bytes:
        return _result("NO_DATA", "host_conditions_digest_unavailable")
    if grant["conditions_accepted_sha256"] != hashlib.sha256(conditions_bytes).hexdigest():
        return _result("REJECTED", "grant_conditions_mismatch")
    if instant < _parse_time(grant["not_before"]):
        return _result("REJECTED", "grant_not_yet_valid")
    if instant >= _parse_time(grant["expires_at"]):
        return _result("REJECTED", "grant_expired")
    return _result("ELIGIBLE_FOR_ATOMIC_CLAIM", "verified_grant_matches_exact_task",
                   grant_id=grant["grant_id"], task_sha256=hashlib.sha256(task_bytes).hexdigest(),
                   grant_sha256=hashlib.sha256(grant_raw).hexdigest(),
                   capability=capability, device_id=device_id,
                   agent_id=grant["agent_id"], expires_at=grant["expires_at"],
                   note="no dispatch; an atomic host journal claim is still required")
