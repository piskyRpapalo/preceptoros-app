"""Atomic, append-only SQLite journal for preceptoros.agent-grant/1 consumption and revocation.

This module provides a host-local, persistent journal that atomically records
grant consumption (claim) and revocation events. It is the missing piece
referenced by agentes_contrato.evaluate_authorization(), which returns
ELIGIBLE_FOR_ATOMIC_CLAIM when all cryptographic and semantic checks pass,
but requires an atomic journal to prevent double-use.

Design principles:
- **Standard library only**: sqlite3, fcntl, json, hashlib, datetime, os, pathlib.
- **Fail closed**: if the journal file is absent, corrupt, or unreadable,
  all operations return REJECTED with cause.
- **Atomic under concurrent processes**: file-level flock + BEGIN IMMEDIATE
  SQLite transaction, following the canales.py pattern.
- **Append-only**: UPDATE and DELETE are blocked by SQLite triggers.
- **No second grant authority**: this journal records consumption/revocation
  only; it never creates grants, alters evaluate_authorization signed bytes,
  or introduces new signing keys.
- **No private user database scan**: tests use synthetic temp-home fixtures only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

# Schema version for migration detection
SCHEMA_VERSION = 1

# Table DDL — append-only via triggers (same pattern as canales.py)
JOURNAL_SCHEMA = """
create table if not exists journal (
    n               integer primary key autoincrement,
    ts              text    not null,
    grant_id        text    not null,
    action          text    not null,
    agent_id        text    not null,
    device_id       text    not null,
    grant_sha256    text    not null,
    task_sha256     text    not null,
    capability      text    not null,
    expires_at      text    not null,
    result          text    not null,
    cause           text    not null
);
create trigger if not exists journal_no_update before update on journal
    begin select raise(abort, 'journal: solo anexar'); end;
create trigger if not exists journal_no_delete before delete on journal
    begin select raise(abort, 'journal: solo anexar'); end;
create table if not exists metadata (
    key   text primary key,
    value text not null
);
"""

ACTION_CONSUME = "consume"
ACTION_REVOKE = "revoke"
RESULT_OK = "ok"
RESULT_REJECTED = "rejected"


def _utc_now() -> str:
    """Current UTC timestamp in ISO 8601 format, no microseconds."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str) -> dt.datetime:
    """Parse an ISO 8601 UTC timestamp."""
    parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=dt.timezone.utc)


class JournalError(Exception):
    """Raised when the journal cannot perform an operation."""


def _check_path_security(db_path: Path) -> None:
    """Reject symlinks and non-regular files to avoid path races.

    Raises JournalError if the path is a symlink, does not exist (and is not
    a new file to be created), or is not a regular file.
    """
    # If the path exists, refuse to follow symlinks
    if db_path.exists() or db_path.is_symlink():
        if db_path.is_symlink():
            raise JournalError("journal path is a symlink: rejected for security")
        # Use os.stat with O_NOFOLLOW when available to avoid TOCTOU
        try:
            fd = os.open(str(db_path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                st = os.fstat(fd)
            finally:
                os.close(fd)
            import stat as _stat
            if not _stat.S_ISREG(st.st_mode):
                raise JournalError("journal path is not a regular file: rejected for security")
        except OSError as e:
            raise JournalError(f"journal path security check failed: {e}")


def _check_file_permissions(db_path: Path) -> None:
    """Ensure the journal file has restrictive permissions (0600).

    Raises JournalError if the file exists with insecure permissions.
    """
    if db_path.exists():
        st = db_path.stat()
        import stat as _stat
        mode = _stat.S_IMODE(st.st_mode)
        # Must be 0600 (owner read/write only)
        if mode != 0o600:
            raise JournalError(
                f"journal file has insecure permissions {oct(mode)}: expected 0o600"
            )


def open_journal(db_path: Path) -> sqlite3.Connection:
    """Open or create the journal database, initializing schema if needed.

    Returns a new connection. Caller must close it.
    Raises JournalError if the file cannot be opened or schema is incompatible.
    """
    if fcntl is None:
        raise JournalError("platform lacks fcntl: journal cannot guarantee atomicity")
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Security: reject symlinks and non-regular files
    _check_path_security(db_path)

    # Security: check existing file permissions
    if db_path.exists():
        _check_file_permissions(db_path)

    con = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    try:
        # Check existing schema version before writing — fail closed on tamper.
        # The metadata table may not exist yet (new DB), so catch OperationalError.
        try:
            existing_version_row = con.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
        except sqlite3.OperationalError:
            existing_version_row = None
        if existing_version_row is not None:
            existing_version = int(existing_version_row[0])
            if existing_version != SCHEMA_VERSION:
                con.close()
                raise JournalError(
                    f"journal schema version mismatch: have {existing_version}, "
                    f"expected {SCHEMA_VERSION} — incompatible, failing closed"
                )
        con.executescript(JOURNAL_SCHEMA)
        # Record schema version (only on new DB or matching version)
        con.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        return con
    except sqlite3.Error:
        con.close()
        raise JournalError("journal database is corrupt or unreadable")


def _acquire_lock(db_path: Path):
    """Acquire an exclusive file lock. Returns (fd, con) for caller to release.

    Follows the canales.py pattern: flock on the file descriptor, then a separate
    sqlite3 connection to the same path with BEGIN IMMEDIATE.
    Rejects symlinks and non-regular files using O_NOFOLLOW when available.
    """
    if fcntl is None:
        raise JournalError("platform lacks fcntl")
    # Security: reject symlinks before opening
    if db_path.is_symlink():
        raise JournalError("journal path is a symlink: rejected for security")
    if not db_path.is_file():
        raise JournalError("journal file absent")
    # Open with O_NOFOLLOW when available to avoid TOCTOU
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(db_path), flags, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    con = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    return fd, con


def _release_lock(fd: int):
    """Release file lock and close file descriptor."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _require_tz_aware(now: dt.datetime) -> None:
    """Reject naive datetimes — only timezone-aware values are accepted.

    Raises JournalError if the datetime has no tzinfo.
    """
    if now.tzinfo is None:
        raise JournalError("naive datetime rejected: provide a timezone-aware datetime")


def claim_grant(
    db_path: Path,
    grant_id: str,
    agent_id: str,
    device_id: str,
    grant_sha256: str,
    task_sha256: str,
    capability: str,
    expires_at: str,
    now: dt.datetime | None = None,
) -> dict:
    """Atomically claim (consume) a grant.

    Returns a dict with keys: state, cause, n (row id on success).
    Exactly one claim succeeds per grant_id; subsequent claims return REJECTED.

    Fail-closed conditions:
    - Journal file absent or corrupt → REJECTED
    - Grant already consumed → REJECTED
    - Grant already revoked → REJECTED
    - Grant expired (expires_at <= now) → REJECTED
    - Naive datetime passed → REJECTED
    """
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    # Security: reject naive datetimes
    try:
        _require_tz_aware(now)
    except JournalError as e:
        return {"state": "REJECTED", "cause": str(e)}
    ts = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Check expiry before acquiring lock (fast path)
    try:
        expiry = _parse_time(expires_at)
    except (TypeError, ValueError):
        return {"state": "REJECTED", "cause": "claim_expiry_malformed"}
    if now >= expiry:
        return {"state": "REJECTED", "cause": "claim_grant_expired"}

    try:
        fd, con = _acquire_lock(db_path)
    except JournalError as e:
        return {"state": "REJECTED", "cause": str(e)}

    try:
        con.execute("BEGIN IMMEDIATE")
        # Check if already consumed or revoked
        existing = con.execute(
            "SELECT action, result FROM journal WHERE grant_id = ? ORDER BY n DESC LIMIT 1",
            (grant_id,),
        ).fetchone()
        if existing is not None:
            action, result = existing
            if action == ACTION_CONSUME and result == RESULT_OK:
                return {"state": "REJECTED", "cause": "grant_already_consumed"}
            if action == ACTION_REVOKE:
                return {"state": "REJECTED", "cause": "grant_revoked"}
        # Atomic insert
        cur = con.execute(
            "INSERT INTO journal (ts, grant_id, action, agent_id, device_id, grant_sha256, "
            "task_sha256, capability, expires_at, result, cause) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ts, grant_id, ACTION_CONSUME, agent_id, device_id, grant_sha256,
             task_sha256, capability, expires_at, RESULT_OK, "claim_successful"),
        )
        rowid = cur.lastrowid
        con.execute("COMMIT")
        return {"state": "OK", "cause": "grant_consumed", "n": rowid}
    except sqlite3.Error as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        return {"state": "REJECTED", "cause": f"journal_sqlite_error_{type(e).__name__}"}
    finally:
        con.close()
        _release_lock(fd)


def revoke_grant(
    db_path: Path,
    grant_id: str,
    agent_id: str,
    device_id: str,
    grant_sha256: str,
    task_sha256: str,
    capability: str,
    expires_at: str,
    now: dt.datetime | None = None,
) -> dict:
    """Atomically revoke a grant.

    Returns a dict with keys: state, cause, n (row id on success).
    A revoked grant cannot be consumed, and a consumed grant cannot be revoked
    (the consumption record stands).

    Naive datetime → REJECTED.
    """
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    # Security: reject naive datetimes
    try:
        _require_tz_aware(now)
    except JournalError as e:
        return {"state": "REJECTED", "cause": str(e)}
    ts = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        fd, con = _acquire_lock(db_path)
    except JournalError as e:
        return {"state": "REJECTED", "cause": str(e)}

    try:
        con.execute("BEGIN IMMEDIATE")
        # Check if already consumed
        existing = con.execute(
            "SELECT action, result FROM journal WHERE grant_id = ? ORDER BY n DESC LIMIT 1",
            (grant_id,),
        ).fetchone()
        if existing is not None:
            action, result = existing
            if action == ACTION_CONSUME and result == RESULT_OK:
                return {"state": "REJECTED", "cause": "grant_already_consumed"}
            if action == ACTION_REVOKE:
                return {"state": "REJECTED", "cause": "grant_already_revoked"}
        cur = con.execute(
            "INSERT INTO journal (ts, grant_id, action, agent_id, device_id, grant_sha256, "
            "task_sha256, capability, expires_at, result, cause) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ts, grant_id, ACTION_REVOKE, agent_id, device_id, grant_sha256,
             task_sha256, capability, expires_at, RESULT_OK, "revocation_successful"),
        )
        rowid = cur.lastrowid
        con.execute("COMMIT")
        return {"state": "OK", "cause": "grant_revoked", "n": rowid}
    except sqlite3.Error as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        return {"state": "REJECTED", "cause": f"journal_sqlite_error_{type(e).__name__}"}
    finally:
        con.close()
        _release_lock(fd)


def get_consumed_grant_ids(db_path: Path) -> set | None:
    """Return the set of grant_ids that have been successfully consumed.

    Returns None if the journal is absent or corrupt (fail-closed sentinel
    for evaluate_authorization). Symlinks are rejected.
    """
    try:
        if db_path.is_symlink():
            return None
        if not db_path.is_file():
            return None
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute(
                "SELECT grant_id FROM journal WHERE action = ? AND result = ?",
                (ACTION_CONSUME, RESULT_OK),
            ).fetchall()
            return {row[0] for row in rows}
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return None


def get_revoked_grant_ids(db_path: Path) -> set | None:
    """Return the set of grant_ids that have been revoked.

    Returns None if the journal is absent or corrupt. Symlinks are rejected.
    """
    try:
        if db_path.is_symlink():
            return None
        if not db_path.is_file():
            return None
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute(
                "SELECT grant_id FROM journal WHERE action = ? AND result = ?",
                (ACTION_REVOKE, RESULT_OK),
            ).fetchall()
            return {row[0] for row in rows}
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return None


def journal_exists(db_path: Path) -> bool:
    """Check whether the journal file exists and is a regular file (not a symlink)."""
    if db_path.is_symlink():
        return False
    return db_path.is_file()


def journal_path(base: Path | None = None) -> Path:
    """Default journal location under the given base directory.

    If base is None, uses ~/.preceptoros/journal.db.
    """
    if base is None:
        base = Path.home() / ".preceptoros"
    return base / "registro" / "grant_journal.db"


def init_journal(db_path: Path | None = None) -> Path:
    """Create the journal database if it doesn't exist. Returns the path.

    The returned connection is properly closed. New files are created with
    mode 0600 (owner read/write only).
    """
    if db_path is None:
        db_path = journal_path()
    con = open_journal(db_path)
    # Security: ensure new file has restrictive permissions
    if db_path.exists():
        os.chmod(str(db_path), 0o600)
    con.close()
    return db_path


def read_journal_entries(db_path: Path, limit: int = 100) -> list | None:
    """Read the most recent journal entries for audit. Returns None if unreadable.
    Symlinks are rejected.
    """
    try:
        if db_path.is_symlink():
            return None
        if not db_path.is_file():
            return None
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute(
                "SELECT n, ts, grant_id, action, agent_id, device_id, result, cause "
                "FROM journal ORDER BY n DESC LIMIT ?",
                (limit,),
            ).fetchall()
            entries = []
            for row in rows:
                entries.append({
                    "n": row[0], "ts": row[1], "grant_id": row[2],
                    "action": row[3], "agent_id": row[4], "device_id": row[5],
                    "result": row[6], "cause": row[7],
                })
            return entries
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return None
