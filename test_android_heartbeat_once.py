"""Native heartbeat proof: compile exact policy and run deterministic, synthetic vectors.
Never reads an owner key, touches Android phones, or calls the public Worker.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
JAVA = ROOT / "mvp-android/app/src/main/java/org/preceptoros/mvp/HeartbeatOncePolicy.java"
PROBE = ROOT / "mvp-android/tests/HeartbeatOncePolicyTest.java"
SERVICE_POLICY = ROOT / "mvp-android/app/src/main/java/org/preceptoros/mvp/HeartbeatServicePolicy.java"
SERVICE_PROBE = ROOT / "mvp-android/tests/HeartbeatServicePolicyTest.java"

class AndroidHeartbeatOnce(unittest.TestCase):
    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"),
                         "NO_DATA(java_toolchain_unavailable)")
    def test_native_worker_wire_policy(self):
        with tempfile.TemporaryDirectory(prefix="preceptor-heartbeat-policy-") as folder:
            build = subprocess.run(
                ["javac", "-d", folder, str(JAVA), str(PROBE)],
                cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                ["java", "-cp", folder, "org.preceptoros.mvp.HeartbeatOncePolicyTest"],
                cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS 32/32", run.stdout)

    @unittest.skipUnless(shutil.which("node"), "NO_DATA(node_toolchain_unavailable)")
    def test_native_only_owner_gesture_and_machine_a11y(self):
        run = subprocess.run(
            ["node", "--test", "mvp-android/tests/android_heartbeat_once.test.cjs"],
            cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("pass 6", run.stdout)
        self.assertIn("fail 0", run.stdout)

    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"),
                         "NO_DATA(java_toolchain_unavailable)")
    def test_recurring_service_interval_and_consent_policy(self):
        with tempfile.TemporaryDirectory(prefix="preceptor-heartbeat-service-policy-") as folder:
            build = subprocess.run(
                ["javac", "-d", folder, str(SERVICE_POLICY), str(SERVICE_PROBE)],
                cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                ["java", "-cp", folder, "org.preceptoros.mvp.HeartbeatServicePolicyTest"],
                cwd=ROOT, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS 7/7", run.stdout)
