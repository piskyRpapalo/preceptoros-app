"""Your private memory, created from the APP (Settings), with the terminal's rule: only on an explicit consent.

Two levels, both real:
- the module (memory_onboarding.py) against temporary files;
- the real server (bin/preceptoros-pwa) as a separate process with an isolated HOME, through HTTP, including a
  restart. The person's own memory is never opened: HOME points at a temporary folder for every server here.

Cases: fresh install, consent refused (each way it can be wrong), consent given, existing memory (empty and with
data), second attempt, restart, a file the APP does not recognize, remote and cross-site requests, and the fact that
reading never creates. Update and uninstall keep the file: the installer updates by fast-forward of the code folder
and never touches ~/.preceptoros; the uninstaller that proves it on a real machine lives in #309 (NO_DATA here until
it is merged; its own tests cover `--borrar-datos`)."""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import memory  # noqa: E402
if os.environ.get("PRECEPTOROS_SABOTAGE_MODULE"):  # tests/memory_onboarding_sabotage.py loads a broken copy
    import importlib.util
    _spec = importlib.util.spec_from_file_location("memory_onboarding", os.environ["PRECEPTOROS_SABOTAGE_MODULE"])
    MO = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(MO)
else:
    import memory_onboarding as MO  # noqa: E402

YES = {"schema": "preceptoros.memory-create/1", "confirm": True, "phrase": "create my memory"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def with_memory(path, text="the lighthouse keeper is Marisol"):
    memory.crear(path)
    with memory.abrir(path) as c:
        c.execute("insert into engrams (what, why) values (?, ?)", (text, "test"))


class Module(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, ".preceptoros", "memory.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_install_reads_absent_and_reading_creates_nothing(self):
        r = MO.read(self.db)
        self.assertEqual((r["state"], r["cause"]), ("ABSENT", "memory_not_created"))
        self.assertFalse(os.path.exists(self.db))
        self.assertFalse(os.path.exists(os.path.dirname(self.db)))

    def test_each_wrong_consent_is_refused_and_creates_nothing(self):
        wrong = [None, {}, "yes", ["create my memory"], dict(YES, confirm=False), dict(YES, confirm="true"),
                 dict(YES, confirm=1), dict(YES, phrase="yes"), dict(YES, phrase="create memory"),
                 dict(YES, schema="preceptoros.memory-create/2"), dict(YES, extra=True),
                 {k: v for k, v in YES.items() if k != "phrase"}]
        for body in wrong:
            with self.subTest(body=body):
                code, r = MO.create(self.db, body)
                self.assertEqual((code, r["outcome"], r["changed"]), (422, "REFUSED", False))
                self.assertFalse(os.path.exists(self.db))

    def test_consent_creates_the_same_memory_the_terminal_creates(self):
        code, r = MO.create(self.db, dict(YES, phrase="  Create My Memory "))
        self.assertEqual((code, r["outcome"], r["state"], r["from_state"]), (201, "CREATED", "READY", "ABSENT"))
        self.assertTrue(r["empty"])
        terminal = os.path.join(self.tmp.name, "terminal.db")
        memory.crear(terminal)
        tables = lambda p: sorted(x[0] for x in sqlite3.connect(p).execute("select name from sqlite_master"))
        self.assertEqual(tables(self.db), tables(terminal), "one schema, the one memory.crear makes")
        self.assertEqual(memory.estado(self.db)[0], "VACIA")
        if os.name == "posix":
            self.assertEqual(os.stat(self.db).st_mode & 0o777, 0o600)

    def test_existing_memory_is_never_touched_and_the_second_attempt_changes_nothing(self):
        with_memory(self.db)
        before = digest(self.db)
        for _ in range(3):
            code, r = MO.create(self.db, YES)
            self.assertEqual((code, r["outcome"], r["changed"], r["memories"]), (200, "ALREADY_EXISTS", False, 1))
        self.assertEqual(digest(self.db), before)

    def test_a_file_with_only_the_apps_own_tables_is_completed_and_they_are_kept(self):
        os.makedirs(os.path.dirname(self.db))
        sqlite3.connect(self.db).close()  # no tables at all
        self.assertEqual(MO.read(self.db)["state"], "NOT_CREATED")
        import captura
        with memory.abrir(self.db) as c:  # what /api/estado leaves on a fresh home: the turn register
            captura.recuento(c)
        self.assertTrue({"turnos"} <= {r[0] for r in sqlite3.connect(self.db).execute("select name from sqlite_master")})
        self.assertEqual(MO.read(self.db)["state"], "NOT_CREATED")
        code, r = MO.create(self.db, YES)
        self.assertEqual((code, r["from_state"], r["state"]), (201, "NOT_CREATED", "READY"))
        self.assertIn("turnos", {x[0] for x in sqlite3.connect(self.db).execute("select name from sqlite_master")})

    def test_a_file_it_does_not_recognize_is_refused_untouched(self):
        os.makedirs(os.path.dirname(self.db))
        con = sqlite3.connect(self.db); con.execute("create table notes (x)"); con.execute("insert into notes values (1)"); con.commit(); con.close()
        before = digest(self.db)
        code, r = MO.create(self.db, YES)
        self.assertEqual((code, r["outcome"], r["cause"]), (409, "REFUSED", "memory_file_has_other_tables"))
        self.assertEqual(digest(self.db), before)
        Path(self.db).write_bytes(b"not a database at all")
        code, r = MO.create(self.db, YES)
        self.assertEqual((code, r["state"]), (409, "UNKNOWN"))
        self.assertEqual(Path(self.db).read_bytes(), b"not a database at all")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class RealServer(unittest.TestCase):
    """The real server, separate process, isolated HOME. Restart included."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="memory-onboarding-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.db = os.path.join(self.home, ".preceptoros", "memory.db")
        self.proc = None
        self.start()

    def tearDown(self):
        self.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self):
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if not k.startswith("PRECEPTOROS_")}
        env.update(HOME=self.home, PRECEPTOROS_PWA_PUERTO=str(self.port), PRECEPTOROS_PWA_BIND="127.0.0.1")
        server = os.environ.get("PRECEPTOROS_SABOTAGE_SERVER") or str(ROOT / "bin" / "preceptoros-pwa")
        env["PYTHONPATH"] = str(ROOT)  # a sabotaged copy of the server lives outside the repository
        self.proc = subprocess.Popen([sys.executable, server], cwd=self.tmp, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close(); return
            except OSError:
                time.sleep(0.05)
        self.fail("NO_DATA · the server did not open its port")

    def stop(self):
        if self.proc:
            self.proc.terminate(); self.proc.wait(10); self.proc = None

    def call(self, method, body=None, origin=True, host=None, ctype="application/json"):
        base = "http://127.0.0.1:%d" % self.port
        req = urllib.request.Request(base + "/api/memoria/inicio", method=method,
                                     data=None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode()))
        req.add_header("Host", host or "127.0.0.1:%d" % self.port)
        if origin:
            req.add_header("Origin", origin if isinstance(origin, str) else base)
        if body is not None:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_the_whole_journey_through_the_real_server_with_a_restart(self):
        code, r = self.call("GET", origin=False)
        self.assertEqual((code, r["state"], r["place"]), (200, "ABSENT", "~/.preceptoros/memory.db"))
        code, r = self.call("POST", dict(YES, confirm=False))
        self.assertEqual((code, r["outcome"]), (422, "REFUSED"))
        self.assertFalse(os.path.exists(self.db))
        code, r = self.call("POST", YES)
        self.assertEqual((code, r["outcome"], r["state"]), (201, "CREATED", "READY"))
        with memory.abrir(self.db) as c:  # the person writes one memory, as /api/anidar would
            c.execute("insert into engrams (what, why) values ('kept', 'test')")
        before = digest(self.db)
        code, r = self.call("POST", YES)
        self.assertEqual((code, r["outcome"], r["memories"]), (200, "ALREADY_EXISTS", 1))
        self.stop(); self.start()  # restart: the state is read again from the file
        code, r = self.call("GET", origin=False)
        self.assertEqual((code, r["state"], r["memories"]), (200, "READY", 1))
        code, r = self.call("POST", YES)
        self.assertEqual((code, r["outcome"]), (200, "ALREADY_EXISTS"))
        self.assertEqual(digest(self.db), before, "no request changed the existing memory")

    def test_cross_site_foreign_host_and_wrong_type_are_refused_and_create_nothing(self):
        for kw in ({"origin": "https://evil.example"}, {"origin": False}, {"host": "evil.example"},
                   {"ctype": "text/plain"}):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                code, r = self.call("POST", YES, **kw)
                self.assertIn(code, (403, 415))
                self.assertFalse(os.path.exists(self.db))
        code, _ = self.call("GET", origin="https://evil.example")
        self.assertEqual(code, 403)

    def test_each_unauthorized_origin_is_refused_by_name_and_creates_nothing(self):
        base = "http://127.0.0.1:%d" % self.port
        cases = {
            "another_site": {"origin": "https://evil.example"},
            "opaque_null_origin": {"origin": "null"},
            "same_host_other_port": {"origin": "http://127.0.0.1:%d" % (self.port + 1)},
            "https_instead_of_http": {"origin": "https://127.0.0.1:%d" % self.port},
            "origin_with_a_path": {"origin": base + "/app"},
            "origin_with_credentials": {"origin": "http://user:pw@127.0.0.1:%d" % self.port},
            "no_origin_on_a_write": {"origin": False},
            "dns_rebinding_host": {"origin": "http://evil.example:%d" % self.port, "host": "evil.example:%d" % self.port},
        }
        for name, kw in cases.items():
            with self.subTest(name):
                code, r = self.call("POST", YES, **kw)
                self.assertEqual((code, r.get("causa")), (403, "origen_local_no_autorizado"), name)
                self.assertFalse(os.path.exists(self.db), name)

    def test_consent_is_not_a_signature(self):
        code, r = self.call("POST", YES)
        self.assertEqual(code, 201)
        words = json.dumps(r).lower()
        for w in ("hitl", "signature", "signed", "grant", "firma", "token"):
            self.assertNotIn(w, words, "the receipt of a consent never speaks as an authorization")
        html = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        self.assertIn("It is not a signature and authorizes nothing else.", html)

    def test_a_talk_message_saying_yes_does_not_create_it(self):
        base = "http://127.0.0.1:%d" % self.port
        req = urllib.request.Request(base + "/api/conversacion", method="POST",
                                     data=json.dumps({"para": "claude", "texto": "yes, create my memory"}).encode())
        req.add_header("Origin", base); req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except urllib.error.HTTPError:
            pass
        self.assertEqual(self.call("GET", origin=False)[1]["state"], "ABSENT")


class Interface(unittest.TestCase):
    def test_wired_once_cached_and_loaded(self):
        html = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf-8")
        pwa = (ROOT / "bin/preceptoros-pwa").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="memoria-inicio"'), 1)
        settings = html[html.index('id="panel-ajustes"'):]
        self.assertIn('id="memoria-inicio"', settings[:settings.find('<section class="panel"', 1) if '<section class="panel"' in settings[1:] else None])
        self.assertIn('<script src="/memory_onboarding.js?v=1"></script>', html)
        self.assertIn('"/memory_onboarding.js?v=1"', sw)
        self.assertIn('"/memory_onboarding.js": ("memory_onboarding.js",', pwa)
        self.assertLess(len((ROOT / "interface/memory_onboarding.js").read_bytes()), 8192)

    def test_the_button_needs_a_real_gesture_the_tick_and_the_phrase(self):
        js = (ROOT / "interface/memory_onboarding.js").read_text(encoding="utf-8")
        self.assertIn("if (!e.isTrusted || btn.disabled) return;", js)
        self.assertIn('btn.disabled = busy || !ok.checked || phrase.value.trim().toLowerCase() !== want;', js)
        self.assertEqual(js.count('method: "POST"'), 1)
        html = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        self.assertIn('id="memoria-inicio-boton" disabled', html)



class Sabotage(unittest.TestCase):
    def test_every_way_to_break_it_is_caught(self):
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "memory_onboarding_sabotage.py")], cwd=ROOT,
                           capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["sabotage"], "caught")


if __name__ == "__main__":
    unittest.main()
