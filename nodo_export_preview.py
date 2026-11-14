"""Pure local credential inspection. No sender, signer, policy grant or secret reads.

Unanswered owner policy is a blocked cause even when every field is selected.
The result contains masked field summaries and digests, never transport bytes.
"""
from __future__ import annotations

import hashlib
import json
import re

import nodo_app
import nodo_export

SCHEMA = "preceptoros.node-export-preview/0"
MAX_BYTES = 65536
MAX_DEPTH = 12
MAX_NODES = 512
_REQUIRED = frozenset({"esquema", "nodo", "admin", "dispositivos", "plan_sha256", "sha256", "firma_ssh"})
_OPTIONAL = frozenset({"firma", "autenticidad"})
_DEVICE = frozenset({"clave", "estado", "tipo", "ambito", "caduca"})
_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
POLICY_CAUSES = ("disclosure_policy_unresolved", "consent_authority_unresolved",
                 "revocation_action_policy_unresolved", "replacement_authority_unresolved")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _ref(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _parse(raw):
    if type(raw) not in (str, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("input bound")
    data = raw.encode("utf-8") if type(raw) is str else raw
    if not data or len(data) > MAX_BYTES:
        raise ValueError("input bound")
    text = data.decode("utf-8")
    # Bound nesting before the JSON decoder, ignoring braces within strings.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("depth bound")
        elif char in "]}":
            depth -= 1
    def constant(_value):
        raise ValueError("nonfinite number")
    card = json.loads(text, object_pairs_hook=_pairs, parse_constant=constant)
    if type(card) is not dict:
        raise ValueError("object required")
    pending, nodes = [card], 0
    while pending:
        value = pending.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise ValueError("node bound")
        if type(value) is dict:
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
    return card


def _result(state, causes, **values):
    return {"schema": SCHEMA, "state": state, "causes": sorted(set(causes)),
            "inspection": "AVAILABLE" if state == "BLOCKED" else "UNAVAILABLE",
            "export_allowed": False, "transport": None, "authority": "NOT_GRANTED",
            "may_operate": False, "node_admission": "NO_DATA", **values}


def _describe(card):
    """Enumerate known concrete paths; hide unknown names and every raw value."""
    rows, unknown = [], False
    def add(parts, value, required=False, known=True, present=True):
        nonlocal unknown
        path = "/" + "/".join(str(x) for x in parts)
        signed = parts[0] not in nodo_app.FUERA_DE_LA_FIRMA
        if not known:
            unknown = True
        kind = ("missing" if not present else
                {dict: "object", list: "array", str: "string", bool: "boolean",
                 int: "number", float: "number", type(None): "null"}[type(value)])
        category = "TECHNICAL"
        if not known:
            category = "UNKNOWN"
        elif parts[0] in {"nodo", "admin", "dispositivos"}:
            category = "DEVICE_OR_IDENTITY"
        elif parts[0] in _OPTIONAL:
            category = "UNTRUSTED_METADATA"
        rows.append({"path": path if known else None, "field_ref": _ref(path.encode()),
                     "known": known, "required": required, "present": present,
                     "signed": signed, "credential_digest_covered": parts[0] != "sha256",
                     "kind": kind, "disclosure": category, "selected": False,
                     "display": "withheld", "value_ref": _ref(_canonical(value)) if present else None})
    for key in sorted(_REQUIRED | _OPTIONAL | set(card)):
        if key not in card:
            if key in _REQUIRED:
                add((key,), None, required=True, present=False)
            continue
        value = card[key]
        known = key in _REQUIRED | _OPTIONAL
        add((key,), value, key in _REQUIRED, known)
        if known and key != "dispositivos" and type(value) is not str:
            unknown = True  # nested data under a scalar field is not known schema
        if key == "dispositivos" and type(value) is list:
            for index, device in enumerate(value):
                add((key, index), device, required=True)
                for field in sorted(set(device) | {"clave", "estado"}):
                    if field not in device:
                        add((key, index, field), None, True, present=False)
                        continue
                    child = device[field]
                    add((key, index, field), child, field in {"clave", "estado"}, field in _DEVICE)
                    if field != "ambito" and field in _DEVICE and type(child) is not str:
                        unknown = True
                    if field == "ambito" and (type(child) is not list or any(
                            type(item) is not str or item not in nodo_app.CAPACIDADES_NODO for item in child)):
                        unknown = True
                    if field == "ambito" and type(child) is list:
                        for j, item in enumerate(child):
                            add((key, index, field, j), item)
    return rows, unknown


def preview(raw, selected=(), *, expected_ref=None, generation=0, consent=None,
            revoked=False, recipient=nodo_export.ENDPOINT, purpose="export"):
    """Inspect supplied JSON bytes only. Never call/export or authenticate a key.

    `consent` and generation are proposed local context, never trusted permission.
    There is no READY state while owner questions Q1-Q6 remain unanswered.
    Exact selections include containers (also empty ones) and concrete list paths.
    A digest is correlation evidence, not signer/consent/admission authenticity.
    """
    if (type(generation) is not int or not 0 <= generation < 2**63
            or type(revoked) is not bool or type(recipient) is not str
            or recipient != nodo_export.ENDPOINT or type(purpose) is not str
            or purpose not in ("export", "revocation_notice")
            or (expected_ref is not None and (type(expected_ref) is not str or not _REF.fullmatch(expected_ref)))):
        return _result("REJECTED", ["context_invalid"])
    try:
        card = _parse(raw)
        if nodo_app._forma(card):
            return _result("REJECTED", ["credential_shape_or_integrity_invalid"])
        rows, has_unknown = _describe(card)
        if type(selected) not in (tuple, list) or len(selected) > MAX_NODES:
            return _result("REJECTED", ["selection_invalid"])
        paths = {r["path"] for r in rows if r["known"] and r["present"]}
        if (any(type(p) is not str or len(p) > 128 or p not in paths for p in selected)
                or len(selected) != len(set(selected))):
            return _result("REJECTED", ["selection_invalid"])
        selected = sorted(selected)
        chosen = set(selected)
        causes = list(POLICY_CAUSES) + ["signature_not_verified"]
        if has_unknown:
            causes.append("unknown_field_blocked")
        if any(not r["present"] for r in rows if r["required"]):
            causes.append("required_field_missing")
        for key in ("admin", "plan_sha256"):
            if key in card and (type(card[key]) is not str or not _HEX.fullmatch(card[key])):
                causes.append("receiver_field_invalid")
        if len(card["dispositivos"]) > 128:
            causes.append("receiver_device_limit")
        if "firma_ssh" in card and (type(card["firma_ssh"]) is not str or not card["firma_ssh"]):
            causes.append("signature_missing")
        for row in rows:
            row["selected"] = row["path"] in chosen if row["known"] else False
            if row["present"] and not row["selected"]:
                causes.append("unselected_field")
                if row["required"]:
                    causes.append("required_field_not_selected")
                if row["signed"]:
                    causes.append("signed_field_not_selected")
        if revoked:
            causes.append("consent_revoked")
        if consent is not None:
            causes.append("supplied_consent_not_authority")
        if purpose == "revocation_notice":
            causes.append("revocation_notice_policy_unresolved")
        if any(d["estado"] == "revocado" for d in card["dispositivos"]):
            causes.append("revoked_record_action_unresolved")
        transport_bytes = json.dumps({"cedula": card}, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")
        binding = {"credential_sha256": card["sha256"],
                   "signed_payload_ref": _ref(nodo_app.cuerpo_firmado(card)),
                   "transport_payload_ref": _ref(transport_bytes),
                   "selection_ref": _ref(_canonical(selected)), "selected_paths": selected,
                   "recipient": nodo_export.ENDPOINT, "method": "POST", "generation": generation,
                   "purpose": purpose, "revoked": revoked, "consent_supplied": consent is not None,
                   "policy_state": "UNRESOLVED"}
        reference = _ref(b"preceptoros.node-export-preview/0\0" + _canonical(binding))
        if expected_ref is not None and reference != expected_ref:
            causes.append("preview_binding_mismatch")
        return _result("BLOCKED", causes, fields=rows, binding=binding, preview_ref=reference,
                       required_action="OWNER_POLICY_AND_AUTHORIZED_CREDENTIAL_REVIEW",
                       signature_state="NOT_VERIFIED", consent_state="REVOKED" if revoked else "NO_DATA")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return _result("REJECTED", ["input_invalid_or_limit_exceeded"])
