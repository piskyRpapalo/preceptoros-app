"""Owner-consented, local-only projection onto the merged github_bootstrap.propose.

This is an inert filesystem adapter, not another schema, crawler, importer,
GitHub credential store, node grant or background service.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import stat

import github_bootstrap as G

RELATIVE = Path("sources") / "github-owner-snapshot.json"
MAX_BYTES = G.MAX_INPUT_BYTES
STALE_SECONDS = 86400


def _failed(cause):
    return {"schema": G.OUT_SCHEMA, "state": "NO_DATA", "cause": cause,
            "changed": False, "source": "owner_local_optin_only"}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def read(owner_home: str | Path, *, now: dt.datetime | None = None):
    """No network, no auto-create, no mutations, no owner consent inference."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        return _failed("clock_timezone_not_measured")
    now = now.astimezone(dt.timezone.utc)
    path = Path(owner_home) / RELATIVE
    try:
        folder = path.parent.lstat()
        if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.geteuid()
                or folder.st_mode & 0o077):
            return _failed("owner_snapshot_directory_not_private")
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or before.st_nlink != 1 or before.st_mode & 0o077):
            return _failed("owner_snapshot_file_not_private")
        if not 0 < before.st_size <= MAX_BYTES:
            return _failed("owner_snapshot_size_invalid")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as inp:
            current = os.fstat(inp.fileno())
            if ((current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
                    or not stat.S_ISREG(current.st_mode) or current.st_mode & 0o077
                    or current.st_nlink != 1):
                return _failed("owner_snapshot_changed_during_read")
            raw = inp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return _failed("owner_snapshot_size_invalid")
        snapshot = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except FileNotFoundError:
        return _failed("owner_snapshot_not_supplied")
    except (OSError, UnicodeError, ValueError, TypeError):
        return _failed("owner_snapshot_invalid_or_unreadable")
    proposal = G.propose(snapshot)
    if proposal.get("state") != "PROPOSED":
        return proposal
    age = max(0, int(now.timestamp() - before.st_mtime))
    proposal["local_snapshot"] = {
        "state": "STALE" if age > STALE_SECONDS else "OWNER_FILE_PRESENT",
        "local_file_age_s": age,
        "time_basis": "local_file_mtime_not_github_time",
        "remote_head": {"state": "NO_DATA", "cause": "github_live_head_not_checked"},
        "owner_identity": {"state": "NO_DATA", "cause": "github_oauth_not_checked"},
        "consent": "local_file_selection_only_not_a_network_grant",
    }
    return proposal
