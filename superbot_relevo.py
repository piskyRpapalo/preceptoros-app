"""Superbot host adapter · one plan task -> one authorized run on a managed CLI through the native MCP relay.

The chain it binds, and the authority each link needs (both boundaries, never one standing for the other):

  plan_sha256   the plan exists in plan_store, byte for byte
  task_sha256   sha256 of the exact task bytes (preceptoros.superbot-task/1), which cite plan_sha256
  agent_id      the card's agent; it signs the run request (session, goal, run, task) with its linked key
  grant         preceptoros.agent-grant/1 signed by the Sovereign for exactly task_sha256 (agentes_contrato)
                and consumed once, atomically (grant_journal.claim_grant)
  goal_id       a cli_relevo goal of voice `app-superbot`, approved once by the owner at a TTY, covering the session
  run_id        = the relay op_id: ChatGPT Web and the APP read the same identifier
  receipt       the relay's own ack/result events for that op, with their sha256

A GOAL does not authorize a task and a grant does not open the relay: dispatch needs both, checked in that order,
then the grant is consumed and only then the mission is pasted. First version: read-only capabilities only.
No retry, ever. A run whose outcome is unknown blocks new dispatches until a person resolves it at a TTY.
Private APP only: the relay lives on the rack; without it every call is NO_DATA(relay_unavailable).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import agentes_contrato as A
import grant_journal as GJ
import plan_store

TASK_SCHEMA = "preceptoros.superbot-task/1"
REQUEST_SCHEMA = "preceptoros.superbot-request/1"
RUN_SCHEMA = "preceptoros.superbot-run/1"
VOICE = "app-superbot"
READ_ONLY = frozenset({"talk.read", "lab.read_document"})
MAX_INSTRUCTION = 4096
RUN_ID = re.compile(r"^sb-[a-z0-9][a-z0-9-]{2,60}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL = {"RESULT", "FAILED", "REJECTED"}


def _r(state, cause, **extra):
    return {"state": state, "cause": cause, **extra}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── the relay (private rack only) ───────────────────────────────────────────
def load_relay():
    base = Path(os.environ.get("PRECEPTOROS_RELEVO_BIN") or Path.home() / ".local/share/preceptoros-web-mcp/bin")
    path = base / "cli_relevo.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("cli_relevo", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod if all(hasattr(mod, n) for n in ("goal_covers", "goal_send", "claim", "read_events", "settle")) else None


# ── bytes that get signed ───────────────────────────────────────────────────
def task_bytes(plan_sha256: str, agent_id: str, capability: str, instruction: str) -> bytes:
    """The exact task the Sovereign signs a grant for. Any byte changed voids the grant (A3)."""
    if not HEX64.fullmatch(plan_sha256 or ""):
        raise ValueError("plan_ref_invalid")
    if not A.SLUG.fullmatch(agent_id or "") or capability not in A.CAPABILITIES:
        raise ValueError("agent_or_capability_invalid")
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction.encode()) > MAX_INSTRUCTION:
        raise ValueError("instruction_out_of_range")
    return A.canonical_bytes({"schema": TASK_SCHEMA, "plan_sha256": plan_sha256, "agent_id": agent_id,
                              "capability": capability, "instruction": instruction})


def parse_task(raw: bytes) -> dict:
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=A._pairs_no_duplicates)
    except (AttributeError, UnicodeError, ValueError):
        raise ValueError("task_invalid_json") from None
    if not isinstance(doc, dict) or set(doc) != {"schema", "plan_sha256", "agent_id", "capability", "instruction"} \
            or doc["schema"] != TASK_SCHEMA:
        raise ValueError("task_shape_invalid")
    if task_bytes(doc["plan_sha256"], doc["agent_id"], doc["capability"], doc["instruction"]) != raw:
        raise ValueError("task_not_canonical")
    return doc


def request_bytes(run_id: str, task_sha256: str, goal_id: str, session_id: str, agent_id: str) -> bytes:
    """What the agent signs with its linked key: «I am this agent, on this session, taking this run of this task»."""
    return A.canonical_bytes({"schema": REQUEST_SCHEMA, "run_id": run_id, "task_sha256": task_sha256,
                              "goal_id": goal_id, "session_id": session_id, "agent_id": agent_id})


# ── the run ledger: one private file per run_id, created once ───────────────
def _runs(home: Path, create=False) -> Path:
    d = Path(home) / "superbot" / "runs"
    if create:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(d.parent, 0o700)
        os.chmod(d, 0o700)
    if d.is_symlink() or (d.exists() and (d.stat().st_mode & 0o077)):
        raise PermissionError("run_ledger_not_private")
    return d


def _write_run(path: Path, run: dict, exclusive=False):
    data = (json.dumps(run, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _read_run(home: Path, run_id: str) -> dict | None:
    if not RUN_ID.fullmatch(run_id or ""):
        return None
    try:
        return json.loads((_runs(home) / (run_id + ".json")).read_text())
    except (FileNotFoundError, ValueError):
        return None


def runs(home: Path) -> list[dict]:
    d = _runs(home)
    if not d.exists():
        return []
    return [r for r in (_read_run(home, p.stem) for p in sorted(d.glob("sb-*.json"))) if r]


def _unresolved(home: Path) -> list[str]:
    return [r["run_id"] for r in runs(home) if r["state"] == "OUTCOME_UNKNOWN" and not r.get("resolution")]


def envelope(run: dict, instruction: str) -> str:
    return ("[SUPERBOT run=%s task=%s plan=%s capacidad=%s · SOLO LECTURA]\n%s\n"
            "No modifiques archivos ni ejecutes comandos con efectos: esta tarea solo autoriza lectura. "
            "Responde aquí con el resultado." % (run["run_id"], run["task_sha256"][:12], run["plan_sha256"][:12],
                                                  run["capability"], instruction))


# ── dispatch: every check, then consume, then paste ─────────────────────────
def dispatch(home: Path, *, run_id: str, task_raw: bytes, session_id: str, goal_id: str,
             card_raw: bytes, grant_raw: bytes, account: dict, request_signature: str,
             allowed_signers, agent_key_dir, device_id: str, conditions_bytes: bytes,
             journal_db: Path, relay=None, now: dt.datetime | None = None, ttl_s: int = 3600) -> dict:
    home = Path(home)
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if not RUN_ID.fullmatch(run_id or ""):
        return _r("REJECTED", "run_id_invalid")
    try:
        task = parse_task(task_raw)
    except ValueError as e:
        return _r("REJECTED", str(e))
    task_sha = _sha(task_raw)
    try:
        plan_store.get(home, task["plan_sha256"])
    except plan_store.PlanError as e:
        return _r("REJECTED", "plan_" + str(e))                              # A8: no plan, no chain
    if task["capability"] not in READ_ONLY:
        return _r("REJECTED", "capability_not_read_only_in_first_version")
    if _read_run(home, run_id):
        return _r("REJECTED", "run_id_already_used", run=_read_run(home, run_id))   # A4
    blocked = _unresolved(home)
    if blocked:
        return _r("REJECTED", "outcome_unknown_blocks_new_runs", unresolved=blocked)  # A12
    relay = relay or load_relay()
    if relay is None:
        return _r("NO_DATA", "relay_unavailable")
    cause = relay.goal_covers(goal_id, VOICE, session_id)                       # boundary 1: the owner's goal
    if cause:
        return _r("REJECTED", cause)
    request = request_bytes(run_id, task_sha, goal_id, session_id, task["agent_id"])
    verdict = A.evaluate_authorization(                                         # boundary 2: the Sovereign's grant
        card_raw, grant_raw, account=account, message_signature=request_signature, signed_message=request,
        allowed_signers=allowed_signers, agent_key_dir=agent_key_dir, task_bytes=task_raw,
        capability=task["capability"], device_id=device_id, conditions_bytes=conditions_bytes, now=now,
        revoked_grant_ids=GJ.get_revoked_grant_ids(journal_db), consumed_grant_ids=GJ.get_consumed_grant_ids(journal_db))
    if verdict["state"] != "ELIGIBLE_FOR_ATOMIC_CLAIM":
        return _r(verdict["state"], verdict["cause"])
    if verdict["agent_id"] != task["agent_id"]:
        return _r("REJECTED", "task_agent_differs_from_grant")
    run = {"schema": RUN_SCHEMA, "run_id": run_id, "plan_sha256": task["plan_sha256"], "task_sha256": task_sha,
           "agent_id": task["agent_id"], "capability": task["capability"], "grant_id": verdict["grant_id"],
           "grant_sha256": verdict["grant_sha256"], "goal_id": goal_id, "session_id": session_id,
           "device_id": device_id, "request_sha256": _sha(request), "state": "AUTHORIZED",
           "created_at": _iso(now), "events": [], "receipt": None}
    path = _runs(home, create=True) / (run_id + ".json")
    try:
        _write_run(path, run, exclusive=True)
    except FileExistsError:
        return _r("REJECTED", "run_id_already_used")
    claim = GJ.claim_grant(journal_db, verdict["grant_id"], task["agent_id"], device_id, verdict["grant_sha256"],
                           task_sha, task["capability"], verdict["expires_at"], now=now)
    if claim.get("state") != "OK":
        run.update(state="REJECTED", cause="grant_" + claim.get("cause", "claim_failed"))
        _write_run(path, run)
        return _r("REJECTED", run["cause"], run_id=run_id)
    run["journal_n"] = claim["n"]
    lock = relay.claim(session_id, VOICE, min(max(ttl_s, 60), 14400), goal_id)
    if not lock.get("ok"):
        run.update(state="OUTCOME_UNKNOWN", cause="grant_consumed_but_writer_turn_refused:" + lock.get("causa", "?"))
        _write_run(path, run)
        return _r("OUTCOME_UNKNOWN", run["cause"], run_id=run_id)
    sent = relay.goal_send(goal_id, VOICE, session_id, run_id, envelope(run, task["instruction"]), ttl_s)
    op = sent.get("op") or {}
    if op.get("status") != "delivered":
        run.update(state="OUTCOME_UNKNOWN", cause="relay_" + str(sent.get("causa") or op.get("status")))
        _write_run(path, run)
        return _r("OUTCOME_UNKNOWN", run["cause"], run_id=run_id)
    run.update(state="DISPATCHED", mission_sha256=op.get("mission_sha256"), log_from=op.get("log_from"),
               dispatched_at=_iso(dt.datetime.now(dt.timezone.utc)))
    _write_run(path, run)
    return _r("DISPATCHED", "grant_consumed_goal_covered_delivered", run=run)


# ── status: the relay's own receipts, read back for this run_id ─────────────
def status(home: Path, run_id: str, relay=None) -> dict:
    home = Path(home)
    run = _read_run(home, run_id)
    if not run:
        return _r("NO_DATA", "run_unknown")
    if run["state"] in TERMINAL or run["state"] == "AUTHORIZED":
        return _r(run["state"], run.get("cause", "recorded"), run=run)
    relay = relay or load_relay()
    if relay is None:
        return _r("NO_DATA", "relay_unavailable", run=run)
    try:
        page = relay.read_events(run["session_id"], 0, 20)
        events, cursor = list(page.get("events", [])), page.get("next_cursor", 0)
        while page.get("more"):
            page = relay.read_events(run["session_id"], cursor, 20)
            events += page.get("events", [])
            cursor = page.get("next_cursor", cursor)
    except Exception:
        return _r("NO_DATA", "relay_read_failed", run=run)
    mine = [e for e in events if e.get("op_id") == run_id]
    run["events"] = [{"seq": e["seq"], "kind": e["kind"], "ts": e["ts"], "sha256": e["sha256"]} for e in mine]
    kinds = {e["kind"]: e for e in mine}
    if "result" in kinds:
        e = kinds["result"]
        run.update(state="RESULT", outcome="TERMINAL_SETTLED",
                   receipt={"source": "cli_relevo", "session_id": run["session_id"], "op_id": run_id,
                            "seq": e["seq"], "ts": e["ts"], "sha256": e["sha256"], "text": e.get("text", "")[-1500:],
                            "meaning": "what the console showed when it went quiet; not the agent's claim of success"})
    elif "blocked" in kinds or "expired" in kinds:
        e = kinds.get("blocked") or kinds["expired"]
        run.update(state="OUTCOME_UNKNOWN", cause="relay_" + e["kind"],
                   receipt={"source": "cli_relevo", "op_id": run_id, "seq": e["seq"], "sha256": e["sha256"]})
    elif "ack" in kinds:
        run["state"] = "RUNNING"
    _write_run(_runs(home) / (run_id + ".json"), run)
    return _r(run["state"], run.get("cause") or run.get("outcome") or "in_progress", run=run)


def resolve(home: Path, run_id: str, note: str) -> dict:
    """A person closes an unknown outcome at an interactive terminal. Never automatic, never a retry."""
    run = _read_run(Path(home), run_id)
    if not run or run["state"] != "OUTCOME_UNKNOWN":
        return _r("REJECTED", "not_an_unknown_outcome")
    if not sys.stdin.isatty():
        return _r("REJECTED", "resolution_needs_an_interactive_terminal")
    if input("Escribe RESOLVER %s: " % run_id[:12]).strip() != "RESOLVER " + run_id[:12]:
        return _r("REJECTED", "phrase_mismatch")
    run["resolution"] = {"at": _iso(dt.datetime.now(dt.timezone.utc)), "note": str(note)[:300]}
    _write_run(_runs(Path(home)) / (run_id + ".json"), run)
    return _r("RESOLVED", "recorded_by_a_person", run_id=run_id)


# ── Notebook projection: small, no instruction text, no secrets ─────────────
NOTEBOOK_FIELDS = ("run_id", "plan_sha256", "task_sha256", "agent_id", "capability", "grant_id", "goal_id",
                   "session_id", "state", "created_at")


def notebook(home: Path) -> dict:
    rows = []
    for r in runs(Path(home))[-20:]:
        row = {k: r.get(k) for k in NOTEBOOK_FIELDS}
        rec = r.get("receipt") or {}
        row["receipt"] = {k: rec.get(k) for k in ("source", "op_id", "seq", "ts", "sha256", "meaning") if k in rec} or None
        row["result_excerpt"] = rec.get("text", "")[-600:] if r["state"] == "RESULT" else None
        row["say"] = _say(r)
        rows.append(row)
    return {"schema": "preceptoros.superbot-runs/1", "n": len(rows), "runs": rows,
            "limits": "Reads the run ledger and the relay's receipts. It authorizes, retries and dispatches nothing."}


def _say(r):
    s = r["state"]
    if s == "RESULT":
        return "Run %s by %s finished: the console answered and went quiet. Receipt %s." % (
            r["run_id"], r["agent_id"], (r.get("receipt") or {}).get("sha256", "")[:12])
    if s == "OUTCOME_UNKNOWN":
        return "Run %s: outcome unknown (%s). New runs wait until you resolve it." % (r["run_id"], r.get("cause"))
    return "Run %s by %s: %s." % (r["run_id"], r["agent_id"], s.lower().replace("_", " "))


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--home", default=os.environ.get("PRECEPTOROS_HOME") or str(Path.home() / ".preceptoros"))
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("task", help="print the canonical task bytes and their sha256 (what the grant signs)")
    t.add_argument("--plan", required=True); t.add_argument("--agent", required=True)
    t.add_argument("--capability", default="lab.read_document"); t.add_argument("--instruction", required=True)
    t.add_argument("--out", required=True)
    rq = sub.add_parser("request", help="print the request bytes the agent signs")
    for a in ("--run", "--task-sha", "--goal", "--session", "--agent", "--out"):
        rq.add_argument(a, required=True)
    st = sub.add_parser("status"); st.add_argument("run_id")
    rs = sub.add_parser("resolve"); rs.add_argument("run_id"); rs.add_argument("--note", default="")
    sub.add_parser("notebook")
    o = p.parse_args(argv)
    if o.cmd == "task":
        raw = task_bytes(o.plan, o.agent, o.capability, o.instruction)
        Path(o.out).write_bytes(raw)
        out = {"task_sha256": _sha(raw), "bytes": len(raw), "file": o.out}
    elif o.cmd == "request":
        raw = request_bytes(o.run, o.task_sha, o.goal, o.session, o.agent)
        Path(o.out).write_bytes(raw)
        out = {"request_sha256": _sha(raw), "bytes": len(raw), "file": o.out}
    elif o.cmd == "status":
        out = status(Path(o.home), o.run_id)
    elif o.cmd == "resolve":
        out = resolve(Path(o.home), o.run_id, o.note)
    else:
        out = notebook(Path(o.home))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
