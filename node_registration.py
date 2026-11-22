"""Node requests: nonpersistent preview and the consented PWA intake adapter."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import stat
import tempfile

import node_building
import node_lifecycle

SCHEMA = "preceptoros.node-registration-request/1"
NODE = re.compile(r"^nodo\.[0-9]{1,6}\.[a-z0-9][a-z0-9-]{0,30}$")
MAX_BYTES = 1024


def receive_preview(envelope):
    """Return a synthetic node receipt and catalog count; never persist it."""
    try:
        size = len(json.dumps(envelope, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        return 400, {"state": "rejected", "cause": "invalid_json"}
    if size > MAX_BYTES:
        return 413, {"state": "rejected", "cause": "request_too_large"}
    if not isinstance(envelope, dict) or set(envelope) != {"mode", "request"}:
        return 400, {"state": "rejected", "cause": "invalid_envelope"}
    request = envelope["request"]
    if envelope["mode"] != "test_stub_only":
        return 403, {"state": "rejected", "cause": "dry_run_only"}
    if not isinstance(request, dict) or set(request) != {"schema", "node", "signer", "cedula_sha256"}:
        return 400, {"state": "rejected", "cause": "invalid_request"}
    if request["schema"] != SCHEMA or not NODE.fullmatch(str(request["node"])):
        return 422, {"state": "rejected", "cause": "invalid_request"}
    if not re.fullmatch(r"[0-9a-f]{64}", str(request["cedula_sha256"])):
        return 422, {"state": "rejected", "cause": "invalid_request"}
    if request["signer"] != {"state": "stub", "label": "test_only_no_signature"}:
        return 422, {"state": "rejected", "cause": "real_signer_not_implemented"}
    return 200, {
        "state": "received",
        "receipt": "test_stub_only",
        "receipt_id": "test-receipt",
        "cedula_sha256": request["cedula_sha256"],
        "catalog": {"state": "stub_not_published", "count": 1},
        "persisted": False,
    }

# Same preliminary contract as DeploymentRequestPolicy.java. The API never
# treats this installation claim as an authenticated device or a signed node.
PWA_INTAKE_SCHEMA = "preceptoros.pwa-node-deployment-request/1"
# HEX-NODE3 v2: the same consented request plus the alias asked for and the roles offered. The owner
# key is created on this device by node_owner; only its public half enters the request.
PWA_INTAKE_SCHEMA_V2 = "preceptoros.pwa-node-deployment-request/2"
INTAKE_SCHEMA_V2 = "preceptoros.deployment-request/2"
ROLES = ("APP_CLIENT", "SENSOR", "LOCAL_AI", "MODEL_SERVER", "BENCH_WORKER")
ALIAS = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
INTAKE_SCHEMA = "preceptoros.deployment-request/1"
INTAKE_RECEIPT = "preceptoros.deployment-request-receipt/1"
INTAKE_URL = "https://api.preceptoros.org/api/v1/deployment-requests"
NONCE = re.compile(r"[a-f0-9]{32}")
SEED_FILE = "deployment-installation-seed"


def _installation_digest(home):
    """Create the per-installation claim atomically and reuse it after retry."""
    root = Path(home)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_uid != os.geteuid()):
        raise OSError("private_installation_home_required")
    seed_path = root / SEED_FILE
    seed, cause = node_building._read_key(root, key_path=seed_path)
    if cause == "credencial_no_provisionada":
        candidate = secrets.token_hex(32)
        fd, temp = tempfile.mkstemp(prefix=".deployment-seed-", dir=root)
        try:
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(candidate + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                node_building.publish_exclusive(temp, seed_path)
            except FileExistsError:
                pass
            dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            os.unlink(temp)
        seed, cause = node_building._read_key(root, key_path=seed_path)
    if cause:
        raise OSError("installation_seed_unavailable")
    return hashlib.sha256(seed.encode("ascii")).hexdigest()


def submit_preliminary(home, data, *, post=None):
    """Forward an explicitly consented claim and validate the pending receipt."""
    def refused(code, cause):
        return code, {"state": "NO_DATA", "cause": cause}

    v2 = isinstance(data, dict) and data.get("esquema") == PWA_INTAKE_SCHEMA_V2
    keys = {"esquema", "node", "nonce", "consent"} | ({"alias", "roles"} if v2 else set())
    if not isinstance(data, dict) or set(data) != keys:
        return refused(422, "invalid_deployment_request")
    if data["esquema"] not in (PWA_INTAKE_SCHEMA, PWA_INTAKE_SCHEMA_V2) or data["consent"] is not True:
        return refused(422, "explicit_consent_required")
    if v2:
        alias, roles = data["alias"], data["roles"]
        if (alias is not None and (not isinstance(alias, str) or not ALIAS.fullmatch(alias)
                                   or NODE.fullmatch(alias))) \
                or not isinstance(roles, list) or not roles or len(set(roles)) != len(roles) \
                or any(r not in ROLES for r in roles):
            return refused(422, "invalid_alias_or_roles")
    node, nonce = data["node"], data["nonce"]
    if (not isinstance(node, str) or not NODE.fullmatch(node)
            or not isinstance(nonce, str) or not NONCE.fullmatch(nonce)):
        return refused(422, "invalid_node_or_nonce")
    try:
        fingerprint = _installation_digest(home)
    except OSError:
        return refused(503, "installation_seed_unavailable")
    request = {"schema": INTAKE_SCHEMA, "node": node, "nonce": nonce,
               "device_sha256": fingerprint, "consent": True}
    if v2:
        import node_owner  # local import: v1 keeps working without an owner key
        try:
            public = node_owner.public_key(home)
        except (OSError, ValueError, subprocess.SubprocessError):
            return refused(503, "owner_key_unavailable")
        request.update(schema=INTAKE_SCHEMA_V2, owner_public_key=public, alias=alias, offer={"roles": roles})
    body = node_building._canonical(request)
    tracking = hashlib.sha256(body).hexdigest()
    try:
        status, raw, url = (post or node_building._http_post)(
            INTAKE_URL, body, {"Content-Type": "application/json", "Accept": "application/json"}, 8)
    except (OSError, ValueError):
        return refused(503, "intake_transport_unavailable")
    if url != INTAKE_URL or status not in (200, 202):
        return refused(502, "intake_http_refused")
    try:
        if len(raw) > 3072:
            raise ValueError("oversized_receipt")
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=node_building._unique_object)
        if not isinstance(receipt, dict):
            raise ValueError("invalid_receipt")
        received = receipt.get("received_at")
        if not isinstance(received, str) or not re.fullmatch(
                r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z", received):
            raise ValueError("invalid_receipt_time")
        datetime.fromisoformat(received[:-1] + "+00:00")
        if any(receipt.get(key) != value for key, value in {
            "schema": INTAKE_RECEIPT, "request_id": tracking, "state": "AWAITING_HUMAN",
            "authority": "NONE", "credential": "NOT_PROVISIONED",
            "live": "NO_DATA(heartbeat_not_verified)",
            "owner_alert": "NO_DATA(recipient_notification_not_verified)",
        }.items()) or receipt.get("notification") not in ("QUEUED", "SENDING", "DELIVERED"):
            raise ValueError("mismatched_receipt")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return refused(502, "intake_receipt_unverified")
    recorded = node_lifecycle.record_intake(home, json.loads(body), receipt)
    return status, {"state": "PENDING", "contractVerified": True,
                    "preliminaryReceiptValidated": True, "trackingId": tracking,
                    "node": node, "approved": False, "live": False,
                    "lifecycle_recorded": recorded}
