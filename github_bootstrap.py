"""Pure owner-GitHub snapshot -> proposed local context, never an importer or grant.

PreceptorOS APP MVP · APP-GH-BOOT-01. The caller obtains a deliberately
selected public GitHub REST response; this module performs NO network, shell,
clone, disk, MCP, model, database or device operation. It cannot authenticate
the owner, validate remote HEAD, create memory, deploy a node or start a loop.
Those need independent human consent, grants and E2E receipts.

Reuse memory_onboarding.py for the owner's actual local SQLite creation,
federado.py for measured node metadata, exportar_contexto.py for scrubbed
cloud summaries and the Companion contract for any signed node admission.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

IN_SCHEMA = "preceptoros.github-owner-snapshot/1"
OUT_SCHEMA = "preceptoros.github-bootstrap-proposal/1"
MAX_INPUT_BYTES = 65536
MAX_REPOS = 100
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-/]{0,126}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
SNAPSHOT_KEYS = frozenset({"schema", "owner", "source", "repositories"})
REPO_KEYS = frozenset({
    "name", "full_name", "html_url", "private", "fork", "archived",
    "default_branch", "head_sha",
})
ROLES = {
    "preceptoros-app": "APP_SOURCE",
    "preceptoros-web": "PUBLIC_WINDOW_SOURCE",
    "preceptoros-companion": "COMPANION_TEMPLATE",
    "preceptoros-public-mesa": "PUBLIC_MESA_TEMPLATE",
    "lab": "LAB_TEMPLATE",
    "study": "GOVERNANCE_REFERENCE",
    "babel": "PROTOCOL_REFERENCE",
}


def _missing(cause):
    return {"state": "NO_DATA", "cause": cause}


def _safe_owner(owner):
    return (isinstance(owner, str) and bool(LOGIN.fullmatch(owner))
            and "--" not in owner)


def _safe_repo_name(name):
    return (isinstance(name, str) and bool(REPO.fullmatch(name))
            and name not in {".", ".."} and not name.startswith(".")
            and not name.endswith(".git"))


def _url_matches(owner, name, url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == "github.com"
            and parsed.path == "/" + owner + "/" + name
            and not parsed.query and not parsed.fragment
            and not parsed.username and not parsed.password)


def _fail(cause):
    return {"schema": OUT_SCHEMA, **_missing(cause), "changed": False}


def propose(snapshot):
    """Build an inert, bounded proposal from owner-supplied public metadata.

    Only structured snapshot dictionaries are accepted, not raw URLs or user
    instructions. The digest binds these bytes, NOT provider provenance or HITL.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_KEYS:
        return _fail("snapshot_shape_invalid")
    try:
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        return _fail("snapshot_json_invalid")
    if len(canonical) > MAX_INPUT_BYTES:
        return _fail("snapshot_byte_limit")
    owner = snapshot["owner"]
    if not _safe_owner(owner):
        return _fail("owner_login_invalid")
    if snapshot["schema"] != IN_SCHEMA or snapshot["source"] != "github.com":
        return _fail("snapshot_source_invalid")
    rows = snapshot["repositories"]
    if not isinstance(rows, list) or len(rows) > MAX_REPOS:
        return _fail("repository_limit")
    public, seen, private_count = [], set(), 0
    for row in rows:
        if not isinstance(row, dict) or not set(row) <= REPO_KEYS:
            return _fail("repository_shape_invalid")
        if not {"name", "full_name", "html_url", "private", "fork",
                "archived", "default_branch"} <= set(row):
            return _fail("repository_fields_missing")
        name = row["name"]
        if not _safe_repo_name(name) or row["full_name"] != owner + "/" + name:
            return _fail("repository_identity_invalid")
        if not _url_matches(owner, name, row["html_url"]):
            return _fail("repository_url_invalid")
        if any(type(row[k]) is not bool for k in ("private", "fork", "archived")):
            return _fail("repository_flags_invalid")
        branch = row["default_branch"]
        if not isinstance(branch, str) or not BRANCH.fullmatch(branch) or ".." in branch:
            return _fail("repository_branch_invalid")
        if row.get("head_sha") is not None and (
                not isinstance(row["head_sha"], str) or
                not SHA.fullmatch(row["head_sha"])):
            return _fail("repository_revision_invalid")
        key = name.casefold()
        if key in seen:
            return _fail("repository_duplicate")
        seen.add(key)
        if row["private"]:
            # Private inventory cannot escape merely because a JSON row was sent.
            private_count += 1
            continue
        public.append({
            "repo": row["full_name"],
            "url": row["html_url"],
            "purpose_hint": ROLES.get(name.lower(), "OWNER_PROJECT"),
            "source_type": "FORK" if row["fork"] else "ORIGINAL",
            "archived": row["archived"],
            "branch": branch,
            "head": ({"state": "OWNER_SUPPLIED_UNVERIFIED", "sha": row["head_sha"]}
                     if row.get("head_sha") else _missing("head_revision_not_supplied")),
        })
    public.sort(key=lambda r: r["repo"].casefold())
    roles = {x["purpose_hint"] for x in public if not x["archived"]}
    next_steps = [
        {"id": "MEMORY-01", "state": "PROPOSED",
         "action": "Offer existing memory_onboarding.create only after local explicit consent",
         "requires": "owner-confirmed APP-local invocation"},
        {"id": "CONTRACT-01", "state": "PROPOSED",
         "action": "Read public AGENTS.md / Companion / Study, with source revisions",
         "requires": "authenticated source fetch and licence check"},
        {"id": "TOOLS-01", "state": "PROPOSED",
         "action": "Inventory actual local MCPs, CLI capabilities and tool grants",
         "requires": "per-tool owner approval; no inherited rack access"},
        {"id": "BENCH-01", "state": "PROPOSED",
         "action": "Measure local system inventory and two model prompts as Lab receipts",
         "requires": "owner hardware/model permission and real local tests"},
        {"id": "A11Y-01", "state": "PROPOSED",
         "action": "Compare one Acho state across text, screen reader and machine form",
         "requires": "real accessible E2E measurements"},
        {"id": "SWARM-01", "state": "PROPOSED",
         "action": "Prepare per-agent Markdown profiles with contract revisions",
         "requires": "owner-scoped grants and supervised execution"},
    ]
    return {
        "schema": OUT_SCHEMA, "state": "PROPOSED", "changed": False,
        "source": "OWNER_SUPPLIED_UNVERIFIED",
        "source_integrity_sha256": hashlib.sha256(canonical).hexdigest(),
        "owner": owner,
        "owner_authentication": _missing("github_owner_identity_not_authenticated"),
        "private_repositories": {"count_only": private_count,
                                  "access": _missing("private_repo_grant_not_checked")},
        "public_repositories": public,
        "capabilities": {
            "lab_source": "DECLARED" if "LAB_TEMPLATE" in roles else "NO_DATA",
            "companion_source": "DECLARED" if "COMPANION_TEMPLATE" in roles else "NO_DATA",
            "live_node": _missing("signed_admission_and_fresh_heartbeat_not_verified"),
            "local_model": _missing("local_model_runtime_not_measured"),
            "github_private_access": _missing("owner_oauth_or_app_grant_not_verified"),
            "active_automations": _missing("scheduler_and_owner_consent_not_verified"),
            "lora_training": _missing("consented_corpus_and_model_benchmark_not_verified"),
        },
        "next_steps": next_steps,
    }
