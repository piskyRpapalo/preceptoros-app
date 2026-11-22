"""Collaborator node owner: the device creates its own SSH key and signs its own plan and cédula.

HEX-NODE3-CLAUDE-04. Closes the step between «request review» and «export» for a desktop APP install:
the owner key is born and stays in `<home>/node-owner/` (0700/0600); only public material leaves.

- `prepare(home)` creates the owner key once and returns its public line.
- `sign_admission(home, node)` reads the consented intake already recorded by `node_registration`,
  signs the scoped plan (`request_sha256` = that intake) and the cédula (device claim = that intake's
  `device_sha256`) with the owner key, stores the plan for the lifecycle, and returns:
    cedula  -> for the existing `/api/nodo/export` (Aduana POST /api/v1/cedulas);
    bundle  -> the PUBLIC `PRECEPTOROS_SIGNED_NODE_PLANS` entry {public_key, plan} for the operator.
This never approves anything: the request still needs the Sovereign's signed APPROVED decision, and
the operator still publishes the bundle. It grants no rack or administrative access.
"""
import hashlib
import os
import stat
import subprocess
import tempfile
from pathlib import Path

import node_building
import node_lifecycle

OWNER_DIR = "node-owner"
KEY_NAME = "owner_ed25519"
PLAN_NS = "preceptoros-plan-nodo"
CEDULA_NS = "preceptoros-cedula"


def _owner_dir(home):
    path = Path(home) / OWNER_DIR
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise ValueError("private_owner_directory_required")
    return path


def prepare(home):
    """Create the owner key once; never overwrite. Returns the public key line."""
    key = _owner_dir(home) / KEY_NAME
    if not key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "preceptoros-node-owner",
                        "-f", str(key)], check=True, capture_output=True, timeout=30)
    if stat.S_IMODE(key.lstat().st_mode) & 0o077 or key.is_symlink():
        raise ValueError("owner_key_not_private")
    public = key.with_suffix(".pub").read_text(encoding="ascii").strip()
    _trust_self(home, public)
    return public


def _trust_self(home, public):
    """A fresh install trusts its own owner for local lifecycle checks. An existing trust file is
    never touched (on the rack it names the Sovereign)."""
    path = Path(home) / "allowed_signers_cedula"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write("soberano " + public + "\n")  # nodo_app verifies principal "soberano" = this install's authority
    return True


def _sign(home, body, namespace):
    key = _owner_dir(home) / KEY_NAME
    with tempfile.TemporaryDirectory(dir=_owner_dir(home)) as tmp:
        target = Path(tmp) / "document"
        target.write_bytes(node_building._canonical(body))
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(key), str(target)],
                       check=True, capture_output=True, timeout=30)
        return {**body, "firma_ssh": target.with_suffix(".sig").read_text(encoding="ascii")}


def sign_admission(home, node):
    if not isinstance(node, str) or not node_lifecycle.NODE.fullmatch(node):
        raise ValueError("node_not_in_cedula_namespace")
    request, _receipt = node_lifecycle._intake(node_lifecycle._load(home, node, "intake"), node)
    public = prepare(home)
    admin = hashlib.sha256(public.encode("ascii")).hexdigest()
    plan = _sign(home, {"esquema": "preceptoros.plan-nodo/1", "accion": "crear_nodo", "id": node, "nodo": node,
                        "admin_sha256": admin, "request_sha256": node_lifecycle._digest(request)}, PLAN_NS)
    plan["sha256"] = node_lifecycle._digest(plan)
    if not node_lifecycle._store(home, node, "plan", plan):
        raise ValueError("plan_not_stored")
    cedula = _sign(home, {"esquema": "preceptoros.cedula-nodo/1", "nodo": node, "admin": admin,
                          "plan_sha256": plan["sha256"],
                          "dispositivos": [{"clave": request["device_sha256"], "estado": "solicitado"}]}, CEDULA_NS)
    cedula["sha256"] = node_lifecycle._digest(cedula)
    return {"cedula": cedula, "bundle": {node: {"public_key": public, "plan": plan}}}


# --- HEX-NODE3 v2: finish admission and heartbeat from the device, with no SSH knowledge needed ---------
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import nodo_export

CEDULAS_URL = "https://api.preceptoros.org/api/v1/cedulas"
KEYS_URL = "https://api.preceptoros.org/api/v1/latidos/llaves"
KEY_NS = "preceptoros-latido-llave"
HEARTBEAT_KEY = "heartbeat.key"
WINDOW = timedelta(hours=23, minutes=50)
ALIAS = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def public_key(home):
    """`ssh-ed25519 <base64>`: the exact public form Aduana's deployment-request/2 accepts."""
    return " ".join(prepare(home).split()[:2])


def _post(post, url, body):
    status, raw, final = (post or node_building._http_post)(
        url, node_building._canonical(body), {"Content-Type": "application/json", "Accept": "application/json"}, 8)
    if final != url or len(raw) > 65536:
        raise ValueError("unexpected_reply")
    return status, json.loads(raw.decode("utf-8"), object_pairs_hook=node_building._unique_object)


def submit_admission(home, node, *, post=None):
    """Sign, send {cedula, plan} to Aduana, and keep the receipt only if it binds exactly what was sent."""
    signed = sign_admission(home, node)
    cedula = signed["cedula"]
    plan = signed["bundle"][node]["plan"]
    try:
        status, reply = _post(post, CEDULAS_URL, {"cedula": cedula, "plan": plan})
    except (OSError, ValueError, UnicodeError):
        return {"state": "NO_DATA", "cause": "aduana_unavailable"}
    if status == 409:
        return {"state": "PENDING", "cause": "awaiting_sovereign_approval"}
    if status not in (200, 202) or not nodo_export._recibo_corresponde(cedula, reply):
        return {"state": "NO_DATA", "cause": reply.get("codigo") or "receipt_mismatch"}
    receipt = reply["recibo"]
    recorded = node_lifecycle.record_export(home, cedula, receipt)
    return {"state": "MEASURED" if receipt.get("estado") == "verificado" else "PENDING",
            "cause": receipt.get("causa") or "cedula_verified", "receipt": receipt.get("recibo_sha256"),
            "lifecycle_recorded": recorded}


def heartbeat_key(home, alias, *, post=None, now=None):
    """Create the next heartbeat key HERE, register only its owner-signed hash, then switch to it."""
    if not isinstance(alias, str) or not ALIAS.fullmatch(alias):
        raise ValueError("invalid_alias")
    prepare(home)
    folder = _owner_dir(home)
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    key = secrets.token_hex(32)
    pending = folder / (HEARTBEAT_KEY + ".siguiente")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(key + "\n")
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    record = _sign(home, {"esquema": "preceptoros.latido-llave/1", "nodo": alias,
                          "sha256": hashlib.sha256(key.encode("ascii")).hexdigest(),
                          "desde": (now - timedelta(seconds=60)).strftime(fmt),
                          "hasta": (now + WINDOW).strftime(fmt)}, KEY_NS)
    try:
        status, reply = _post(post, KEYS_URL, record)
    except (OSError, ValueError, UnicodeError):
        return {"state": "NO_DATA", "cause": "aduana_unavailable"}
    if status != 202 or reply.get("estado") != "registrada" or reply.get("nodo") != alias:
        pending.unlink(missing_ok=True)  # the current key, if any, stays in use
        return {"state": "NO_DATA", "cause": reply.get("codigo") or "key_not_registered"}
    os.replace(pending, folder / HEARTBEAT_KEY)
    _write_json(folder / HEARTBEAT_META, {"esquema": META_SCHEMA, "nodo": alias, "sha256": record["sha256"],
                                          "desde": record["desde"], "hasta": record["hasta"]})
    return {"state": "MEASURED", "cause": "owner_key_registered", "until": record["hasta"],
            "key_file": HEARTBEAT_KEY}


# --- HEX-NODE3-07: the desktop APP sends its own heartbeat, once, on the owner's request --------------------
# Same wire contract as Android's HeartbeatOncePolicy (preceptoros.latido/1 → preceptoros.recibo-latido/1).
# The key is read here and goes only into the x-heartbeat-key header; never into a result, a log or the page.
HEARTBEAT_URL = "https://api.preceptoros.org/api/v1/latidos"
HEARTBEAT_META = "heartbeat.json"           # public: alias, key hash, validity window
HEARTBEAT_STATE = "heartbeat-state.json"    # public: last accepted sequence and receipt digest
META_SCHEMA = "preceptoros.heartbeat-key-meta/1"
HEARTBEAT_SCHEMA = "preceptoros.latido/1"
RECEIPT_SCHEMA = "preceptoros.recibo-latido/1"
_CAUSE = re.compile(r"^[a-z0-9_]{1,96}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _write_json(path, value):
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None


def _http_get(url, timeout=8):
    import urllib.error
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        response = urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read(262145), response.geturl()


def _receipt_ok(receipt, body, sent):
    """The receipt must name exactly this heartbeat and carry Aduana's own two digests."""
    if not isinstance(receipt, dict) or receipt.get("esquema") != RECEIPT_SCHEMA:
        return False
    if any(receipt.get(k) != body[k] for k in ("nodo", "secuencia", "medido_en")):
        return False
    if receipt.get("payload_sha256") != hashlib.sha256(sent).hexdigest():
        return False
    unsigned = {k: v for k, v in receipt.items() if k != "recibo_sha256"}
    if set(unsigned) != {"esquema", "nodo", "secuencia", "medido_en", "recibido", "payload_sha256"}:
        return False
    return receipt.get("recibo_sha256") == hashlib.sha256(node_building._canonical(unsigned)).hexdigest()


def _public_listing(alias, get):
    """Independent read of the public map. Only says whether the alias is listed; never declares LIVE."""
    try:
        status, raw, final = (get or _http_get)(HEARTBEAT_URL)
        if status != 200 or final != HEARTBEAT_URL:
            return "NO_DATA"
        nodes = json.loads(raw.decode("utf-8"))["colonia"]["nodes"]
        return "LISTED" if any(n.get("id") == alias for n in nodes) else "NOT_LISTED"
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        return "NO_DATA"


def heartbeat_once(home, *, post=None, get=None, now=None):
    """Send ONE heartbeat with the key born on this device; report Aduana's verified answer and cause."""
    folder = Path(home) / OWNER_DIR
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    try:
        key = (folder / HEARTBEAT_KEY).read_text(encoding="ascii").strip()
    except OSError:
        return {"state": "NO_DATA", "cause": "no_heartbeat_key"}
    meta = _read_json(folder / HEARTBEAT_META)
    if (not re.fullmatch(r"[0-9a-f]{64}", key) or not isinstance(meta, dict) or meta.get("esquema") != META_SCHEMA
            or meta.get("sha256") != hashlib.sha256(key.encode("ascii")).hexdigest()
            or not isinstance(meta.get("nodo"), str) or not ALIAS.fullmatch(meta["nodo"])):
        return {"state": "NO_DATA", "cause": "heartbeat_key_record_invalid"}
    alias = meta["nodo"]
    try:
        until = datetime.strptime(meta["hasta"], _FMT).replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return {"state": "NO_DATA", "cause": "heartbeat_key_record_invalid"}
    if now >= until:
        return {"state": "NO_DATA", "cause": "heartbeat_key_expired", "node": alias}
    last = _read_json(folder / HEARTBEAT_STATE) or {}
    previous = last.get("secuencia") if last.get("nodo") == alias and isinstance(last.get("secuencia"), int) else -1
    body = {"esquema": HEARTBEAT_SCHEMA, "nodo": alias, "secuencia": max(previous + 1, int(now.timestamp())),
            "medido_en": now.strftime(_FMT)}
    sent = node_building._canonical(body)
    try:
        status, raw, final = (post or node_building._http_post)(
            HEARTBEAT_URL, sent, {"Content-Type": "application/json", "Accept": "application/json",
                                  node_building.KEY_HEADER: key}, 8)
        reply = json.loads(raw.decode("utf-8")) if final == HEARTBEAT_URL else None
    except (OSError, ValueError, UnicodeError):
        return {"state": "NO_DATA", "cause": "aduana_unavailable", "node": alias}
    if not isinstance(reply, dict):
        return {"state": "NO_DATA", "cause": "unexpected_reply", "node": alias}
    receipt = reply.get("recibo")
    if status in (200, 202) and reply.get("estado") == "recibido" and _receipt_ok(receipt, body, sent):
        _write_json(folder / HEARTBEAT_STATE, {"nodo": alias, "secuencia": body["secuencia"],
                                               "recibo_sha256": receipt["recibo_sha256"],
                                               "recibido": receipt["recibido"]})
        return {"state": "MEASURED", "cause": "heartbeat_receipt_verified", "node": alias,
                "sequence": body["secuencia"], "received": receipt["recibido"],
                "receipt": receipt["recibo_sha256"], "key_until": meta["hasta"],
                "public_map": _public_listing(alias, get)}
    code = reply.get("codigo") if isinstance(reply.get("codigo"), str) and _CAUSE.fullmatch(reply["codigo"]) else None
    return {"state": "NO_DATA", "cause": code or ("receipt_mismatch" if status in (200, 202) else "http_%d" % status),
            "node": alias, "http": status}
