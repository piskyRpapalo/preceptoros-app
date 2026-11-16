"""Private, content-addressed storage for Superbot plans (no authority)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SCHEMA = "preceptoros.plan/1"
MAX_PLAN_BYTES = 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{64}$")


class PlanError(ValueError):
    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PlanError("duplicate_json_key")
        result[key] = value
    return result


def _canonical(document: dict) -> bytes:
    try:
        return json.dumps(document, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError):
        raise PlanError("plan_text_not_canonicalizable") from None


def parse_request(raw: bytes) -> tuple[dict, bytes, str]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PLAN_BYTES:
        raise PlanError("plan_body_out_of_range")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(PlanError("invalid_number")))
    except PlanError:
        raise
    except (UnicodeError, ValueError):
        raise PlanError("invalid_json") from None
    if not isinstance(doc, dict) or set(doc) != {"schema", "title", "text"}:
        raise PlanError("invalid_plan_shape")
    title, text = doc.get("title"), doc.get("text")
    if doc.get("schema") != SCHEMA:
        raise PlanError("unsupported_plan_schema")
    if not isinstance(title, str) or not title.strip() or len(title) > 240:
        raise PlanError("invalid_plan_title")
    if not isinstance(text, str) or not text.strip():
        raise PlanError("invalid_plan_text")
    canonical = _canonical({"schema": SCHEMA, "title": title, "text": text})
    if len(canonical) > MAX_PLAN_BYTES:
        raise PlanError("plan_body_out_of_range")
    return {"schema": SCHEMA, "title": title, "text": text}, canonical, hashlib.sha256(canonical).hexdigest()


def _plans_dir(home: Path) -> Path:
    # The app home is private; create the plan directory with owner-only access.
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = home / "plans"
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise PlanError("plan_store_directory_invalid")
    try:
        path.chmod(0o700)
    except OSError:
        raise PlanError("plan_store_unavailable") from None
    return path


def put(home: Path, raw: bytes) -> dict:
    document, canonical, sha = parse_request(raw)
    directory = _plans_dir(Path(home))
    target = directory / (sha + ".json")
    if target.exists():
        existing = _read_path(target)
        if existing != canonical:
            raise PlanError("content_address_collision")
        return {"plan_sha256": sha, "bytes": len(canonical), "title": document["title"], "created": False}
    fd, temp_name = tempfile.mkstemp(prefix=".plan-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # link is atomic and refuses to replace an existing immutable plan.
            os.link(temp_name, target, follow_symlinks=False)
            created = True
        except FileExistsError:
            created = False
        if not created and _read_path(target) != canonical:
            raise PlanError("content_address_collision")
        return {"plan_sha256": sha, "bytes": len(canonical), "title": document["title"], "created": created}
    except OSError:
        raise PlanError("plan_store_unavailable") from None
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _read_path(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PlanError("plan_blob_unavailable")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(MAX_PLAN_BYTES + 1)
    except OSError:
        raise PlanError("plan_blob_unavailable") from None
    if not raw or len(raw) > MAX_PLAN_BYTES:
        raise PlanError("plan_blob_invalid")
    return raw


def get(home: Path, sha: str) -> tuple[dict, int]:
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise PlanError("invalid_plan_ref")
    raw = _read_path(_plans_dir(Path(home)) / (sha + ".json"))
    if hashlib.sha256(raw).hexdigest() != sha:
        raise PlanError("plan_digest_mismatch")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError):
        raise PlanError("plan_blob_invalid") from None
    if not isinstance(doc, dict) or set(doc) != {"schema", "title", "text"} or doc.get("schema") != SCHEMA:
        raise PlanError("plan_blob_invalid")
    return doc, len(raw)


def flow_reference(messages: list[dict]) -> dict | None:
    """Return the newest store-authored ref; no Talk text can authorize it."""
    for message in reversed(messages):
        if (message.get("voz") != "superbot-plan-store" or message.get("rol") != "system"
                or not isinstance(message.get("texto"), str)):
            continue
        match = re.fullmatch(r"PLAN_REF ([0-9a-f]{64}) ([1-9][0-9]{0,6})", message["texto"])
        if match:
            size = int(match.group(2))
            if size <= MAX_PLAN_BYTES:
                return {"sha": match.group(1), "bytes": size, "written_at": message.get("t")}
    return None
