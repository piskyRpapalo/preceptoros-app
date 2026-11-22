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
