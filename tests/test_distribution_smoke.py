"""Isolated Linux installer/runtime smoke; all writes stay in TemporaryDirectory."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def memory_snapshot(db: Path) -> list[tuple]:
    """Compare durable user records, not SQLite page layout/WAL bytes."""
    import sqlite3

    with sqlite3.connect(db) as connection:
        return connection.execute(
            "select id, what, why, where_ref, learned, origin from engrams order by id"
        ).fetchall()


def assert_memory_preserved(db: Path, expected: list[tuple]) -> None:
    if not db.is_file():
        raise AssertionError("local memory database disappeared")
    actual = memory_snapshot(db)
    if actual != expected:
        raise AssertionError("saved memory records changed")


class DistributionSmoke(unittest.TestCase):
    def test_linux_clean_install_restart_and_reinstall_preserve_memory(self):
        with tempfile.TemporaryDirectory(prefix="preceptoros-dist-smoke-") as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            destination = home / "preceptoros"
            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "PRECEPTOROS_DESTINO": str(destination),
                # Local source only: this exercise does not contact GitHub.
                "PRECEPTOROS_REPO": str(ROOT),
            })

            first = subprocess.run(
                ["bash", str(ROOT / "empaquetado" / "install.sh")],
                cwd=root, env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertTrue((destination / ".git").is_dir())
            self.assertTrue((home / ".local/share/applications/preceptoros.desktop").is_file())
            self.assertTrue((home / ".local/bin/preceptoros-abrir").stat().st_mode & 0o100)

            db = home / ".preceptoros" / "memory.db"
            seed = subprocess.run(
                [sys.executable, "-c", (
                    "import os, memory; p=os.path.join(os.environ['HOME'], '.preceptoros', 'memory.db'); "
                    "memory.crear(p); "
                    "c=memory.abrir(p); "
                    "ctx=c.__enter__(); "
                    "memory.escribir_engrama(ctx, what='synthetic distribution smoke', why='fixture'); "
                    "c.__exit__(None, None, None)"
                )],
                cwd=destination, env={**env, "PYTHONPATH": str(destination)},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
            )
            self.assertEqual(seed.returncode, 0, seed.stdout)
            self.assertTrue(db.is_file())
            before = memory_snapshot(db)
            self.assertEqual(len(before), 1, "synthetic memory fixture was not persisted")

            port = free_loopback_port()
            runtime_env = {
                **env,
                "PRECEPTOROS_PWA_BIND": "127.0.0.1",
                "PRECEPTOROS_PWA_PUERTO": str(port),
                "PYTHONPATH": str(destination),
            }
            with tempfile.TemporaryFile(mode="w+") as log:
                process = subprocess.Popen(
                    [sys.executable, str(destination / "bin/preceptoros-pwa"), "--db", str(db)],
                    cwd=destination, env=runtime_env, stdout=log, stderr=subprocess.STDOUT,
                )
                try:
                    payload = None
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            log.seek(0)
                            self.fail("local app process exited: " + log.read())
                        try:
                            with urlopen(f"http://127.0.0.1:{port}/api/estado", timeout=1) as response:
                                self.assertEqual(response.status, 200)
                                payload = json.loads(response.read().decode("utf-8"))
                            break
                        except Exception:
                            time.sleep(0.1)
                    self.assertIsInstance(payload, dict, "local /api/estado did not answer")
                    self.assertNotIn(str(root), json.dumps(payload), "private temporary path leaked")
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn("text/html", response.headers.get("Content-Type", ""))
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

            second = subprocess.run(
                ["bash", str(ROOT / "empaquetado" / "install.sh")],
                cwd=root, env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            assert_memory_preserved(db, before)

    def test_update_is_fast_forward_only_and_does_not_target_home_data(self):
        sh = (ROOT / "empaquetado/install.sh").read_text(encoding="utf-8")
        ps = (ROOT / "empaquetado/install.ps1").read_text(encoding="utf-8")
        casa = (ROOT / "casa.py").read_text(encoding="utf-8")
        self.assertIn("git -C \"$DESTINO\" pull --ff-only", sh)
        self.assertIn("git -C $Destino pull --ff-only", ps)
        self.assertIn('NOMBRE = ".preceptoros"', casa)
        self.assertNotIn("git reset --hard", sh + ps)
        self.assertNotIn("git clean", sh + ps)
        # The existing updater has no signed release-manifest verification.
        self.assertNotIn("sha256", sh.lower())
        self.assertNotIn("signature", sh.lower())

    def test_platform_limits_do_not_claim_windows_or_native_android_install(self):
        ps = (ROOT / "empaquetado/install.ps1").read_text(encoding="utf-8")
        android = (ROOT / "INSTALL_ANDROID.md").read_text(encoding="utf-8")
        self.assertIn("NO PROBADO", ps)
        self.assertIn("APK", android)
        self.assertIn("does not exist yet", android)

    def test_day_d_installer_does_not_promise_an_unwired_ollama_bridge(self):
        sh = (ROOT / "empaquetado/install.sh").read_text(encoding="utf-8")
        app = (ROOT / "bin/preceptoros-pwa").read_text(encoding="utf-8")
        guide = (ROOT / "docs/DAY_D_4_COLLABORATORS.md").read_text(encoding="utf-8")
        self.assertIn("NO_DATA(ollama_adapter_unverified)", sh)
        self.assertIn("GGUF", sh)
        self.assertIn("no usa Hexelion privado como respaldo", sh)
        self.assertNotIn("curl -fsSL https://ollama.com/install.sh | sh", sh)
        self.assertIn('"private_hexelion" if os.environ.get(', app)
        self.assertIn('else "local_gguf"', app)
        self.assertIn("DECLARATION.md", guide)
        self.assertIn("STATE.md", guide)
        self.assertIn("NO_DATA(user_Ollama_bridge_E2E)", guide)
        self.assertIn("Hexelion runs **only on the founder's private rack**", guide)

    def test_sabotage_deleting_temp_memory_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="preceptoros-dist-sabotage-") as temporary:
            root = Path(temporary)
            home = root / "home"
            destination = home / "preceptoros"
            (destination / ".git").mkdir(parents=True)
            db_dir = home / ".preceptoros"
            db_dir.mkdir(parents=True)
            db = db_dir / "memory.db"
            import sqlite3

            with sqlite3.connect(db) as connection:
                connection.execute(
                    "create table engrams (id integer, what text, why text, where_ref text, learned text, origin text)"
                )
                connection.execute(
                    "insert into engrams values (1, 'fixture', 'why', 'ref', 'learned', 'person')"
                )
            before = memory_snapshot(db)

            source = (ROOT / "empaquetado/install.sh").read_text(encoding="utf-8")
            marker = 'if [ -d "$DESTINO/.git" ]; then'
            self.assertEqual(source.count(marker), 1)
            sabotaged = source.replace(
                marker,
                'rm -f "$HOME/.preceptoros/memory.db"\n' + marker,
                1,
            )
            script = root / "sabotaged-install.sh"
            script.write_text(sabotaged, encoding="utf-8")
            env = {
                **os.environ,
                "HOME": str(home),
                "PRECEPTOROS_DESTINO": str(destination),
                "PRECEPTOROS_REPO": str(ROOT),
            }
            result = subprocess.run(
                ["bash", str(script)], cwd=root, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            with self.assertRaisesRegex(AssertionError, "disappeared"):
                assert_memory_preserved(db, before)


if __name__ == "__main__":
    unittest.main()
