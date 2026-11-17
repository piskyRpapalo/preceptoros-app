"""Create the person's private memory from the APP, with the same rule as the terminal onboarding.

The terminal asks once and, on an explicit yes, calls `memory.crear(ruta)`. The APP now offers that same step in
Settings. Same file (`casa.raiz()/memory.db`, or the server's --db), same schema, same function; no second store.

What is stricter here than a terminal yes, because a web page is reachable by more than one hand:
- only a loopback, same-origin request reaches it (the server checks `_nodo_local_autorizado` before calling this);
- the body must be exactly the consent record below: a typed phrase, a true flag and nothing else;
- the state is read again under a lock, right before creating: an existing memory is never recreated, touched or
  reset, whatever the request says; a file this module cannot recognize is refused, not "repaired".

Consent is the person's own decision about their own device. It is not an HITL signature and grants nothing else.

Reading never creates anything: the state is read with a read-only connection.
"""
import os
import sqlite3
import threading

import memory as M

SCHEMA = "preceptoros.memory-onboarding/1"
CONSENT_SCHEMA = "preceptoros.memory-create/1"
PHRASE = "create my memory"
_LOCK = threading.Lock()
# Tables the APP itself may put in the same file before the memory exists: the turn register (captura.py, opened by
# /api/estado on every start) and SQLite's own counter. Measured on a fresh isolated HOME, 2026-11-16. memory.crear only
# adds tables (create if not exists), so these are kept as they are.
APP_OWN = {"turnos", "sqlite_sequence"}

# What the person is told will exist. Each item names a table that memory.crear makes.
WILL_CREATE = (
    "your memories (engrams) and the links between them",
    "your profile: name, language and pace, only what you write",
    "conversation threads, drafts and outputs you approve",
    "a search index over your own memories",
)


def _tables(ruta):
    """Table names, read-only. None when the file is not a database this reader can open."""
    try:
        con = sqlite3.connect("file:" + os.path.abspath(ruta) + "?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _place(ruta):
    """The path as the person can read it: their home folder is shown as ~, nothing else is hidden or invented."""
    home = os.path.expanduser("~")
    full = os.path.abspath(ruta)
    return "~" + full[len(home):] if home and full.startswith(home.rstrip(os.sep) + os.sep) else full


def read(ruta):
    """-> the state of the memory at `ruta`, without creating or changing anything.

    ABSENT      no file: the memory was never created.
    NOT_CREATED a file with no tables, or only the APP's own working tables (APP_OWN): no memory inside yet.
    READY       the memory exists (engrams and links); its counts say whether it is empty.
    UNKNOWN     a file with other tables or unreadable: never touched from here.
    """
    out = {"schema": SCHEMA, "place": _place(ruta), "will_create": list(WILL_CREATE), "phrase": PHRASE}
    if not os.path.exists(ruta):
        return dict(out, state="ABSENT", cause="memory_not_created")
    tables = _tables(ruta)
    if tables is None:
        return dict(out, state="UNKNOWN", cause="memory_file_unreadable")
    if tables <= APP_OWN:
        return dict(out, state="NOT_CREATED", cause="memory_not_created")
    if not {"engrams", "links"} <= tables:
        return dict(out, state="UNKNOWN", cause="memory_file_has_other_tables")
    try:
        est, counts = _counts(ruta)
    except sqlite3.Error:
        return dict(out, state="UNKNOWN", cause="memory_file_unreadable")
    return dict(out, state="READY", memories=counts["engrams"], links=counts["links"],
                archived=counts["archivados"], search="engrams_fts" in tables, empty=est == "VACIA")


def _counts(ruta):
    con = sqlite3.connect("file:" + os.path.abspath(ruta) + "?mode=ro", uri=True)
    try:
        c = {"engrams": con.execute("select count(*) from engrams where status='activo'").fetchone()[0],
             "archivados": con.execute("select count(*) from engrams where status='archivado'").fetchone()[0],
             "links": con.execute("select count(*) from links").fetchone()[0]}
    finally:
        con.close()
    return ("VACIA" if c["engrams"] + c["archivados"] == 0 else "CON_DATOS"), c


def consent_ok(body):
    """The exact consent record, nothing more: {"schema", "confirm": true, "phrase": "create my memory"}."""
    return (isinstance(body, dict) and set(body) == {"schema", "confirm", "phrase"}
            and body.get("schema") == CONSENT_SCHEMA and body.get("confirm") is True
            and isinstance(body.get("phrase"), str) and body["phrase"].strip().lower() == PHRASE)


def create(ruta, body):
    """-> (http code, receipt). Creates only from ABSENT or NOT_CREATED, only with consent, never twice."""
    if not consent_ok(body):
        return 422, dict(read(ruta), outcome="REFUSED", cause="consent_required", changed=False)
    with _LOCK:
        before = read(ruta)
        if before["state"] == "READY":
            return 200, dict(before, outcome="ALREADY_EXISTS", changed=False)
        if before["state"] == "UNKNOWN":
            return 409, dict(before, outcome="REFUSED", changed=False)
        M.crear(ruta)
        after = read(ruta)
    if after["state"] != "READY":
        return 500, dict(after, outcome="NO_DATA", cause="created_but_not_readable", changed=True)
    return 201, dict(after, outcome="CREATED", changed=True, from_state=before["state"])
