"""Linux uninstaller (empaquetado/uninstall.sh): removes only what the installer created, keeps the person's data.
All writes stay in a TemporaryDirectory used as HOME. No network, no docker (the container E2E is tests/ubuntu_e2e)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "empaquetado" / "uninstall.sh"


def tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(path)).encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


class Uninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="uninstall-")
        self.home = Path(self.tmp.name)
        env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.env = env
        # an upstream with one commit carrying bin/preceptoros-pwa, and a clean clone of it as the installed tree
        up = self.home / "upstream"
        (up / "bin").mkdir(parents=True)
        (up / "bin" / "preceptoros-pwa").write_text("#!/bin/sh\n")
        (up / "bin" / "preceptoros-pwa").chmod(0o755)
        for c in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "u"]):
            subprocess.run(["git", "-C", str(up), *c], check=True, env=env)
        subprocess.run(["git", "clone", "-q", str(up), str(self.home / "preceptoros")], check=True, env=env)
        self.made = [self.home / ".local/share/applications/preceptoros.desktop", self.home / ".local/bin/preceptoros-abrir",
                     self.home / ".local/share/icons/hicolor/256x256/apps/preceptoros.png"]
        for f in self.made:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("x")
        self.data = self.home / ".preceptoros"
        (self.data / "canales").mkdir(parents=True)
        (self.data / "canales" / "eventos.db").write_bytes(b"conversation")
        (self.data / "identidad").mkdir()
        (self.data / "identidad" / "nodo.json").write_text("{}")
        self.data_before = tree_hash(self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], env=dict(self.env, **(env or {})), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30)

    def test_removes_app_keeps_data(self):
        r = self.run_it("--si")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for f in self.made:
            self.assertFalse(f.exists(), f)
        self.assertFalse((self.home / "preceptoros").exists())
        self.assertEqual(tree_hash(self.data), self.data_before)
        self.assertIn("datos conservados", r.stdout)

    def test_never_deletes_data_without_a_terminal(self):
        r = self.run_it("--si", "--borrar-datos")
        self.assertEqual(tree_hash(self.data), self.data_before)
        self.assertIn("exige terminal", r.stdout + r.stderr)

    def test_without_terminal_and_without_si_changes_nothing(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 2)
        self.assertTrue(all(f.exists() for f in self.made))
        self.assertTrue((self.home / "preceptoros").exists())

    def test_keeps_a_tree_with_your_changes(self):
        (self.home / "preceptoros" / "mine.txt").write_text("mine")
        self.run_it("--si")
        self.assertTrue((self.home / "preceptoros" / "mine.txt").exists())
        self.assertEqual(tree_hash(self.data), self.data_before)

    def test_keeps_a_tree_with_unpushed_commits(self):
        t = self.home / "preceptoros"
        (t / "local.txt").write_text("l")
        subprocess.run(["git", "-C", str(t), "add", "-A"], check=True, env=self.env)
        subprocess.run(["git", "-C", str(t), "commit", "-qm", "mine"], check=True, env=self.env)
        self.run_it("--si")
        self.assertTrue(t.exists())

    def test_does_not_touch_a_folder_that_is_not_preceptoros(self):
        other = self.home / "other"
        other.mkdir()
        (other / "f").write_text("keep")
        r = self.run_it("--si", env={"PRECEPTOROS_DESTINO": str(other)})
        self.assertTrue((other / "f").exists(), r.stdout)


if __name__ == "__main__":
    unittest.main()
