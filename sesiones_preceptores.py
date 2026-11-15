"""Pure observation contract; no I/O."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import re
from typing import Mapping

SCHEMA = "preceptoros.session-observation/0"
FIELDS = ("session_id", "owner", "host", "repo", "branch", "mission_id",
          "state", "capabilities", "last_receipt", "updated_at")
READ_CAPABILITIES = frozenset({"session.read", "receipt.read", "output.read"})
MAX_INPUT = 65536
MAX_EVENTS = 64
MAX_FRAME = 1023
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:#@/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")
_SECRET = re.compile(r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+|"
                     r"\bBearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                     r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,}))")
CAUSES = frozenset({
    "observation_valid", "identity_binding_unavailable", "session_not_found",
    "owner_mismatch", "preceptor_mismatch", "identity_unverified",
    "source_generation_changed", "invalid_contract", "input_limit_exceeded",
    "execution_not_allowed", "evidence_invalid", "evidence_future",
    "evidence_expired", "evidence_unavailable", "evidence_not_observed",
    "evidence_integrity_mismatch", "lifecycle_unverified", "receipt_missing",
    "receipt_binding_mismatch", "value_invalid", "output_source_unavailable",
    "output_withheld_secret", "sequence_gap", "frame_limit_exceeded",
    "completeness_not_attested", "read_capability_unavailable"})

def no_data(cause):
    if cause not in CAUSES:
        raise ValueError("unknown cause code")
    return {"state": "NO_DATA", "cause": cause}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def _time(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise ValueError("invalid UTC timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def _id(value):
    return isinstance(value, str) and bool(_ID.fullmatch(value)) and ".." not in value

def _secret(text, ctx):
    plain = _ANSI.sub("", text)
    return bool(_SECRET.search(plain) or any(s and s in plain for s in ctx.secrets))

def _contains_secret(value, ctx):
    if isinstance(value, str):
        return _secret(value, ctx)
    if isinstance(value, dict):
        return any(_contains_secret(v, ctx) for v in value.values())
    if isinstance(value, list):
        return any(_contains_secret(v, ctx) for v in value)
    return False

def _clean(text):
    text = _ANSI.sub("", text)
    text = "".join(c for c in text if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127
                   and not 0x80 <= ord(c) <= 0x9f and c not in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"))
    return html.escape(text, quote=True)

@dataclass(frozen=True)
class SessionBinding:
    session_id: str
    owner: str
    preceptor: str
    host: str
    repo: str
    worktree_ref: str
    generation: str
    mission_id: str | None
    capabilities: tuple[str, ...] = ()
    next_sequence: int = 0

@dataclass(frozen=True)
class TrustedContext:
    bindings: Mapping[str, SessionBinding]
    attestations: Mapping[str, str]
    observed_at: str
    allowed_sources: frozenset[str]
    secrets: tuple[str, ...] = ()

def _bounded(value):
    try:
        return len(canonical(value)) <= MAX_INPUT
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return False

def _envelope(cause):
    result = {field: no_data(cause) for field in FIELDS}
    result.update(schema=SCHEMA, cause=cause, observed_at=None,
                  evidence=[], completeness=no_data("completeness_not_attested"))
    return _finish(result)

def _finish(value):
    value["projection_ref"] = "sha256:" + digest(value)
    return value

def _binding(candidate, ctx):
    if not isinstance(ctx, TrustedContext):
        return None, "identity_binding_unavailable"
    bound = ctx.bindings.get(candidate.get("session_id"))
    if not isinstance(bound, SessionBinding):
        return None, "session_not_found"
    if candidate.get("owner") != bound.owner:
        return None, "owner_mismatch"
    if candidate.get("preceptor") != bound.preceptor:
        return None, "preceptor_mismatch"
    if candidate.get("generation") != bound.generation:
        return None, "source_generation_changed"
    if any(candidate.get(k) != getattr(bound, k) for k in ("host", "repo", "worktree_ref")):
        return None, "identity_unverified"
    return bound, None

def _evidence(raw, ctx, now):
    keys = {"id", "source_ref", "origin", "observed_at", "expires_at", "payload", "digest"}
    if not isinstance(raw, dict) or set(raw) != keys:
        return None, "evidence_invalid"
    if not _id(raw["id"]) or raw["source_ref"] not in ctx.allowed_sources:
        return None, "evidence_invalid"
    if raw["origin"] not in ("OBSERVED", "DECLARED", "SIMULATED"):
        return None, "evidence_invalid"
    start, end = _time(raw["observed_at"]), _time(raw["expires_at"])
    if start > now or end < start:
        return None, "evidence_future" if start > now else "evidence_invalid"
    if not isinstance(raw["payload"], dict):
        return None, "evidence_invalid"
    if _contains_secret(raw, ctx):
        return None, "output_withheld_secret"
    unsigned = {k: v for k, v in raw.items() if k != "digest"}
    if digest(unsigned) != raw["digest"]:
        return None, "evidence_integrity_mismatch"
    if ctx.attestations.get(raw["source_ref"]) != raw["digest"]:
        return None, "identity_unverified"
    public = {k: deepcopy(raw[k]) for k in keys - {"payload"}}
    return (raw, public, start, end), None

def _valid_value(field, value, bound):
    if field in ("session_id", "owner", "host", "repo"):
        return value == getattr(bound, field) and _id(value)
    if field == "mission_id":
        return value == bound.mission_id and _id(value)
    if field == "branch":
        return (isinstance(value, dict) and set(value) == {"name", "head_sha"}
                and (value["name"] is None or _id(value["name"]))
                and isinstance(value["head_sha"], str) and bool(_SHA.fullmatch(value["head_sha"])))
    if field == "state":
        return value in ("RUNNING", "EXITED", "INTERRUPTED")
    if field == "capabilities":
        return (isinstance(value, list) and all(isinstance(v, str) for v in value)
                and len(value) == len(set(value)) and set(value) <= READ_CAPABILITIES)
    if field == "updated_at":
        _time(value)
        return True
    if field == "last_receipt":
        return (isinstance(value, dict) and set(value) == {
            "id", "session_id", "generation", "mission_id", "observed_at", "result", "digest"}
            and _id(value["id"]) and value["session_id"] == bound.session_id
            and value["generation"] == bound.generation
            and value["mission_id"] == bound.mission_id
            and value["result"] in ("ok", "failed", "refused")
            and _time(value["observed_at"])
            and value["digest"] == digest({k: v for k, v in value.items() if k != "digest"}))
    return False

def project_session(candidate, evidence, trusted_context, now):
    try:
        return _project_session(candidate, evidence, trusted_context, now)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, UnicodeError):
        return _envelope("invalid_contract")

def _project_session(candidate, evidence, ctx, now):
    clock = _time(now)
    if not isinstance(ctx, TrustedContext):
        return _envelope("identity_binding_unavailable")
    capture = _time(ctx.observed_at)
    if capture > clock:
        return _envelope("evidence_future")
    if not _bounded([candidate, evidence]):
        return _envelope("input_limit_exceeded")
    if not isinstance(candidate, dict):
        return _envelope("invalid_contract")
    if set(candidate) != set(FIELDS) | {"preceptor", "generation", "worktree_ref", "evidence_refs"}:
        return _envelope("execution_not_allowed" if set(candidate) & {
            "command", "stdin", "method", "signal", "restart", "attach", "resize", "exec"
        } else "invalid_contract")
    bound, error = _binding(candidate, ctx)
    if error:
        return _envelope(error)
    if not isinstance(evidence, list) or len(evidence) > 64:
        return _envelope("input_limit_exceeded")
    refs = candidate["evidence_refs"]
    if not isinstance(refs, dict) or set(refs) != set(FIELDS):
        return _envelope("invalid_contract")
    valid, public = {}, []
    for item in evidence:
        checked, error = _evidence(item, ctx, clock)
        if error:
            return _envelope(error)
        raw, visible, start, end = checked
        if raw["id"] in valid:
            return _envelope("evidence_invalid")
        payload = raw["payload"]
        if set(payload) != {"session_id", "generation", "preceptor", "worktree_ref", "values", "event"}:
            return _envelope("evidence_invalid")
        if any(payload[k] != getattr(bound, k) for k in (
                "session_id", "generation", "preceptor", "worktree_ref")):
            return _envelope("identity_unverified")
        if not isinstance(payload["values"], dict) or not set(payload["values"]) <= set(FIELDS):
            return _envelope("evidence_invalid")
        valid[raw["id"]] = checked
        public.append(visible)
    result = {"schema": SCHEMA, "observed_at": ctx.observed_at,
              "evidence": sorted(public, key=lambda e: e["id"]), "cause": "observation_valid",
              "completeness": no_data("completeness_not_attested")}
    for field in FIELDS:
        value, ids = candidate[field], refs[field]
        missing = {"last_receipt": "receipt_missing", "state": "lifecycle_unverified"}.get(field, "evidence_unavailable")
        result[field] = no_data(missing)
        if not isinstance(ids, list) or not all(_id(i) for i in ids) or len(ids) != len(set(ids)):
            return _envelope("invalid_contract")
        if not ids:
            continue
        if any(i not in valid for i in ids):
            return _envelope("evidence_invalid")
        items = [valid[i] for i in ids]
        if any(e[0]["payload"]["values"].get(field) != value for e in items):
            result[field] = no_data("evidence_integrity_mismatch")
            continue
        if not _valid_value(field, value, bound):
            result[field] = no_data("receipt_binding_mismatch" if field == "last_receipt" else "value_invalid")
            continue
        if field == "state" and any(e[0]["payload"]["event"] != value for e in items):
            result[field] = no_data("lifecycle_unverified")
            continue
        if field == "branch" and (not set(ids) & set(refs["repo"]) or any(
                e[0]["payload"]["values"].get("repo") != bound.repo for e in items)):
            result[field] = no_data("identity_unverified")
            continue
        if field == "updated_at" and (value != ctx.observed_at or any(e[0]["observed_at"] != value for e in items)):
            result[field] = no_data("evidence_future" if _time(value) > clock else "value_invalid")
            continue
        if field == "last_receipt" and _time(value["observed_at"]) > clock:
            result[field] = no_data("evidence_future")
            continue
        if field != "last_receipt" and any(e[3] <= clock or (clock-e[2]).total_seconds() > 120 for e in items):
            result[field] = no_data("evidence_expired")
            continue
        origins = {e[0]["origin"] for e in items}
        if origins != {"OBSERVED"}:
            result[field] = no_data("evidence_not_observed")
            continue
        if field == "capabilities":
            value = sorted(set(value) & set(bound.capabilities) & READ_CAPABILITIES)
        result[field] = {"state": "MEASURED", "value": deepcopy(value), "evidence_refs": sorted(ids)}
    if result["state"]["state"] == "MEASURED" and any(
            result[f]["state"] != "MEASURED" for f in ("session_id", "owner", "host")):
        result["state"] = no_data("identity_unverified")
    return _finish(result)

def project_output(events, session_ref, trusted_context):
    try:
        return _project_output(events, session_ref, trusted_context)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, UnicodeError):
        return no_data("invalid_contract")

def _project_output(events, ref, ctx):
    if not isinstance(ctx, TrustedContext):
        return no_data("identity_binding_unavailable")
    if not isinstance(ref, dict) or set(ref) != {"session_id", "generation", "next_sequence"}:
        return no_data("invalid_contract")
    bound = ctx.bindings.get(ref["session_id"])
    if not isinstance(bound, SessionBinding):
        return no_data("session_not_found")
    if ref["generation"] != bound.generation:
        return no_data("source_generation_changed")
    if type(ref["next_sequence"]) is not int or ref["next_sequence"] != bound.next_sequence:
        return no_data("sequence_gap")
    if "output.read" not in bound.capabilities:
        return no_data("read_capability_unavailable")
    if events is None:
        return no_data("output_source_unavailable")
    if not _bounded(events):
        return no_data("input_limit_exceeded")
    if not isinstance(events, list):
        return no_data("invalid_contract")
    clock = _time(ctx.observed_at)
    unique = {}
    keys = {"source_ref", "session_id", "generation", "sequence", "channel", "observed_at", "text", "digest", "origin"}
    for raw in events:
        if not isinstance(raw, dict) or set(raw) != keys:
            return no_data("execution_not_allowed" if isinstance(raw, dict) and "command" in raw else "invalid_contract")
        if raw["origin"] != "OBSERVED":
            return no_data("evidence_not_observed")
        if raw["generation"] != bound.generation:
            return no_data("source_generation_changed")
        if raw["session_id"] != bound.session_id:
            return no_data("identity_unverified")
        if raw["source_ref"] not in ctx.allowed_sources:
            return no_data("identity_unverified")
        if type(raw["sequence"]) is not int or raw["sequence"] < bound.next_sequence:
            return no_data("sequence_gap")
        if raw["channel"] not in ("stdout", "stderr") or not isinstance(raw["text"], str):
            return no_data("invalid_contract")
        if _time(raw["observed_at"]) > clock:
            return no_data("evidence_future")
        if _contains_secret(raw, ctx):
            return no_data("output_withheld_secret")
        event = {k: deepcopy(v) for k, v in raw.items() if k != "digest"}
        event["text"] = _clean(raw["text"])
        fingerprint = digest(event)
        if fingerprint != raw["digest"]:
            return no_data("evidence_integrity_mismatch")
        if ctx.attestations.get(raw["source_ref"]) != fingerprint:
            return no_data("identity_unverified")
        event["digest"] = fingerprint
        if len(canonical(event)) > MAX_FRAME:
            return no_data("frame_limit_exceeded")
        seq = event["sequence"]
        if seq in unique and unique[seq] != event:
            return no_data("sequence_gap")
        unique[seq] = event
    ordered = [unique[s] for s in sorted(unique)]
    if [e["sequence"] for e in ordered] != list(range(bound.next_sequence, bound.next_sequence+len(ordered))):
        return no_data("sequence_gap")
    selected = ordered[:MAX_EVENTS]
    return _finish({"schema": SCHEMA + "/output", "state": "MEASURED",
                    "session_id": bound.session_id, "generation": bound.generation,
                    "observed_at": ctx.observed_at, "events": selected,
                    "next_sequence": bound.next_sequence + len(selected),
                    "has_more": len(ordered) > MAX_EVENTS,
                    "cause": "input_limit_exceeded" if len(ordered) > MAX_EVENTS else "observation_valid"})
