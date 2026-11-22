"""Owner-local node lifecycle projection backed by correlated evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request

import node_building
import nodo_app
import nodo_export

SCHEMA = "preceptoros.node-lifecycle/1"
STAGES = ("prepare", "consent", "request", "signature", "approval", "heartbeat",
          "live", "ai", "building", "revoke")
NODE = nodo_app.NOMBRE
HEX = nodo_app.HEX64
INTAKE_URL = "https://api.preceptoros.org/api/v1/deployment-requests"
WORLD_URL = "https://api.preceptoros.org/api/v1/latidos"
CATALOG_URL = "https://api.preceptoros.org/api/v1/cedulas"
REVIEW_KEY_FILE = "PRECEPTOROS_OWNER_REVIEW_KEY_FILE"
FILE_LIMIT = 512 * 1024
UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z")


def _hex(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _time(value):
    if not isinstance(value, str) or not UTC.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _digest(value):
    return hashlib.sha256(node_building._canonical(value)).hexdigest()


def _directory(home, *, create=False):
    path = Path(home) / "node-lifecycle"
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise ValueError("private_lifecycle_directory_required")
    return path


def _private_bytes(path, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
                info.st_uid != os.geteuid() or info.st_size > limit):
            raise ValueError("private_lifecycle_file_required")
        data = file.read(limit + 1)
    if len(data) > limit:
        raise ValueError("lifecycle_file_too_large")
    return data


def _object(raw):
    data = json.loads(raw, object_pairs_hook=node_building._unique_object)
    if not isinstance(data, dict):
        raise ValueError("lifecycle_object_required")
    return data


def _store(home, node, kind, data):
    if not isinstance(node, str) or not NODE.fullmatch(node):
        return False
    try:
        path = _directory(home, create=True)
        raw = node_building._canonical(data)
        if len(raw) > FILE_LIMIT:
            return False
        with tempfile.NamedTemporaryFile(dir=path, delete=False) as file:
            temp = Path(file.name)
            try:
                file.write(raw)
                file.flush()
                os.fsync(file.fileno())
                os.replace(temp, path / f"{node}.{kind}.json")
            finally:
                temp.unlink(missing_ok=True)
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except (OSError, ValueError):
        return False


def record_intake(home, request, receipt):
    return _store(home, request["node"], "intake", {"request": request, "receipt": receipt})


def record_export(home, cedula, receipt):
    return _store(home, cedula["nodo"], "export", {"cedula": cedula, "receipt": receipt})


def _load(home, node, kind):
    return _object(_private_bytes(_directory(home) / f"{node}.{kind}.json", FILE_LIMIT))


def _get(url, headers, limit):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), nodo_export._NoRedirect())
    request = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    with opener.open(request, timeout=4) as response:
        raw = response.read(limit + 1)
        if response.status != 200 or len(raw) > limit:
            raise ValueError("lifecycle_source_invalid")
        return _object(raw)


def _intake(data, node):
    request, receipt = data.get("request"), data.get("receipt")
    if not isinstance(request, dict) or not isinstance(receipt, dict):
        raise ValueError("intake_evidence_invalid")
    ref = _digest(request)
    v1 = {"schema", "node", "consent", "device_sha256", "nonce"}
    v2 = v1 | {"owner_public_key", "alias", "offer"}
    if (not ((set(request) == v1 and request["schema"] == "preceptoros.deployment-request/1") or
             (set(request) == v2 and request["schema"] == "preceptoros.deployment-request/2")) or
            request["node"] != node or
            request["consent"] is not True or not _hex(request["device_sha256"]) or
            not isinstance(request["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", request["nonce"]) or
            receipt.get("schema") != "preceptoros.deployment-request-receipt/1" or
            receipt.get("request_id") != ref or receipt.get("state") != "AWAITING_HUMAN" or
            not _time(receipt.get("received_at"))):
        raise ValueError("intake_evidence_invalid")
    return request, receipt


def _decision(ref, request, review_key_file, fetch):
    key = _private_bytes(review_key_file, 512).decode("ascii").strip()
    if not re.fullmatch(r"[!-~]{32,512}", key):
        raise ValueError("review_key_invalid")
    result = fetch(INTAKE_URL + "/" + ref, {"X-Owner-Review-Key": key}, 4096)
    state = result.get("state")
    if (result.get("schema") != "preceptoros.deployment-request-receipt/1" or
            result.get("request_id") != ref or result.get("receipt_sha256") != ref or
            result.get("node") != request["node"] or result.get("device_sha256") != request["device_sha256"] or
            result.get("consent") is not True or state not in ("AWAITING_HUMAN", "APPROVED", "REJECTED", "REVOKED") or
            (state != "AWAITING_HUMAN" and
             (not _hex(result.get("decision_sha256")) or not _time(result.get("decision_at"))))):
        raise ValueError("d1_review_receipt_mismatch")
    return result


def _signed_export(home, node, request, ref, signers):
    record = _load(home, node, "export")
    cedula, receipt = record["cedula"], record["receipt"]
    if (nodo_app._forma(cedula) or cedula["nodo"] != node or not any(
            d["clave"] == request["device_sha256"] and d["estado"] != "revocado" for d in cedula["dispositivos"])):
        raise ValueError("cedula_claim_mismatch")
    if nodo_app.autenticidad(cedula, signers)[0] != "OK":
        raise ValueError("cedula_signature_unverified")
    response = {"recibo": receipt, "estado": "verificado", "causa": None,
                "recibidos": 1, "paquete": {"pares": [cedula]}}
    if not nodo_export._recibo_corresponde(cedula, response) or not _time(receipt.get("recibido")):
        raise ValueError("export_receipt_mismatch")
    plan = _load(home, node, "plan")
    core = {k: v for k, v in plan.items() if k not in ("firma_ssh", "sha256")}
    signed = {k: v for k, v in plan.items() if k != "sha256"}
    if (set(core) != {"esquema", "accion", "id", "nodo", "admin_sha256", "request_sha256"} or
            core.get("esquema") != "preceptoros.plan-nodo/1" or core.get("accion") != "crear_nodo" or
            core.get("nodo") != node or core.get("admin_sha256") != cedula.get("admin") or
            core.get("request_sha256") != ref or plan.get("sha256") != cedula.get("plan_sha256") or
            _digest(signed) != plan.get("sha256") or
            nodo_app.verificar_ssh(plan.get("firma_ssh"), node_building._canonical(core),
                                   "preceptoros-plan-nodo", signers)[0] != "OK"):
        raise ValueError("signed_plan_intake_binding_unverified")
    return receipt


def _catalogued(catalog, node, admitted):
    rows = catalog.get("cedulas")
    if catalog.get("esquema") != "preceptoros.catalogo-cedulas/1" or not isinstance(rows, list):
        return False
    return any(isinstance(row, dict) and row.get("nodo") == node and row.get("estado") == "verificado" and
               row.get("recibo_sha256") == admitted["recibo_sha256"] for row in rows)


def _seen_live(world, node):
    if (world.get("esquema") != "preceptoros.openworld-estado/2" or
            world.get("cobertura", {}).get("estado") != "MEDIDO"):
        raise ValueError("aduana_projection_unverified")
    rows = world["colonia"]["nodes"]
    if not isinstance(rows, list):
        raise ValueError("aduana_projection_invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == node]
    return len(matches) == 1 and matches[0].get("seal") == "LIVE" and matches[0].get("alive") is True


def admission_identity(home):
    """Read the local identity without treating a public alias as a cédula ID."""
    identity = node_building.leer_identidad(home)
    if identity.get("estado") != "configurada":
        return None, "local_identity_unavailable"
    node = identity["node_id"]
    if not NODE.fullmatch(node):
        return None, "local_identity_not_cedula_namespace"
    return node, None


def read(home, *, review_key_file=None, signers=None, fetch=_get, now=None):
    """Project one selected identity. Missing proof never upgrades another stage."""
    now = now or datetime.now(timezone.utc)
    stages = {name: {"state": "NO_DATA", "cause": cause, "source": source} for name, cause, source in (
        ("prepare", "local_identity_unavailable", "app_local_identity"),
        ("consent", "owner_consent_receipt_unavailable", "app_intake"),
        ("request", "intake_receipt_unavailable", "aduana_intake"),
        ("signature", "signed_export_or_plan_unavailable", "app_ssh_and_aduana_export"),
        ("approval", "owner_review_unavailable", "aduana_owner_review"),
        ("heartbeat", "authenticated_heartbeat_receipt_unavailable", "aduana_heartbeat_receipt"),
        ("live", "bound_public_presence_unverified", "aduana_public_projection"),
        ("ai", "public_node_model_turn_source_unavailable", "public_node_channel"),
        ("building", "authorized_function_invocation_source_unavailable", "public_building_function"),
        ("revoke", "owner_review_unavailable", "aduana_owner_review"),
    )}
    out = {"schema": SCHEMA, "observed_at": now.isoformat().replace("+00:00", "Z"), "node": None, "stages": stages}

    def mark(name, state, cause, *, at=None, ref=None):
        stages[name].update(state=state, cause=cause)
        if at is not None:
            stages[name]["at"] = at
        if ref is not None:
            stages[name]["receipt_ref"] = ref

    node, cause = admission_identity(home)
    if cause:
        mark("prepare", "NO_DATA", cause)
        return out
    out["node"] = node
    mark("prepare", "MEASURED", "local_identity_configured")
    try:
        request, intake = _intake(_load(home, node, "intake"), node)
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return out
    ref, at = intake["request_id"], intake["received_at"]
    mark("consent", "MEASURED", "consented_payload_bound_to_intake", at=at, ref=ref)
    mark("request", "PENDING", "aduana_intake_receipt_verified", at=at, ref=ref)
    try:
        admitted = _signed_export(home, node, request, ref,
                                  signers if signers is not None else Path(home) / "allowed_signers_cedula")
    except (OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError):
        admitted = None
    if admitted is not None:
        mark("signature", "MEASURED", "cedula_and_intake_bound_plan_verified",
             at=admitted["recibido"], ref=admitted["recibo_sha256"])
    if not review_key_file:
        return out
    try:
        decision = _decision(ref, request, review_key_file, fetch)
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        mark("approval", "NO_DATA", "owner_review_unverified")
        mark("revoke", "NO_DATA", "owner_review_unverified")
        return out
    state = decision["state"]
    args = {"at": decision.get("decision_at"), "ref": decision.get("decision_sha256")}
    if state == "REVOKED":
        mark("approval", "REVOKED", "d1_revocation_verified", **args)
        mark("revoke", "REVOKED", "d1_revocation_verified", **args)
        mark("live", "NO_DATA", "node_admission_revoked")
        return out
    if state == "REJECTED":
        mark("approval", "REFUSED", "d1_rejection_verified", **args)
        return out
    if state == "AWAITING_HUMAN":
        mark("approval", "PENDING", "d1_awaiting_owner_review", at=at, ref=ref)
        return out
    mark("approval", "MEASURED", "d1_approval_verified", **args)
    mark("revoke", "PENDING", "d1_approval_active", **args)
    if admitted is None:
        return out
    try:
        if not _catalogued(fetch(CATALOG_URL, {}, FILE_LIMIT), node, admitted):
            mark("live", "NO_DATA", "admission_receipt_absent_from_aduana_catalog")
            return out
        if _seen_live(fetch(WORLD_URL, {}, 16384), node):
            mark("heartbeat", "NO_DATA", "projection_omits_exact_heartbeat_receipt")
            mark("live", "MEASURED", "aduana_live_projection_confirmed",
                 at=out["observed_at"])
        else:
            mark("live", "NO_DATA", "node_absent_from_aduana_live_projection")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        pass
    return out
