"""Gate de reintento OWNER del hilo existente; pruebas JS sintéticas."""
import subprocess
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
class OwnerThreadRetryGate(unittest.TestCase):
    def test_scope_and_retry(self):
        r = subprocess.run(["node", "--test", "tests/owner_thread_scope_cases.cjs"],
                           cwd=ROOT, capture_output=True, text=True, timeout=35)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-2500:])
        self.assertRegex(r.stdout, r"(?m)^(?:#|ℹ) pass 12$")
        self.assertRegex(r.stdout, r"(?m)^(?:#|ℹ) fail 0$")
