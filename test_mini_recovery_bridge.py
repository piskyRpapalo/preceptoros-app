"""MINI-RECOVER-01: enforce native importer tests in the APP's canonical gate.

The owner export restores a local project, not a verified owner node. Node test
fixtures use synthetic data, no network and no real Android storage.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent

class MiniRecoveryGate(unittest.TestCase):
    def test_app_and_android_ui_contract(self):
        app=(ROOT/'interface/app.html').read_text(encoding='utf-8')
        native=(ROOT/'mvp-android/app/src/main/java/org/preceptoros/mvp/MainActivity.java').read_text(encoding='utf-8')
        for marker in ('id="mini-recovery-file"','id="mini-recovery-consent"',
                       'id="mini-recovery-state"','id="lab-mini-recovery-state"',
                       '/mini_recovery.js?v=1','/mini_project_guide.js?v=1'):
            self.assertIn(marker,app)
        for marker in ('onShowFileChooser','ACTION_OPEN_DOCUMENT','CATEGORY_OPENABLE',
                       'ownPageReady','START.equals(view.getUrl())','setAllowFileAccess(false)'):
            self.assertIn(marker,native)
        self.assertIn('versionCode mvpVersionCode',(ROOT/'mvp-android/app/build.gradle').read_text())

    @unittest.skipUnless(shutil.which('node'), "Node runtime unavailable: NO_DATA(node_not_installed)")
    def test_export_roundtrip_and_adversarial_node_contract(self):
        scripts=['tests/mini_recovery_cases.cjs',
                 'tests/android_mini_recovery_security_cases.cjs',
                 'tests/public_mini_project_cases.cjs']
        run=subprocess.run(['node','--test',*scripts],cwd=ROOT,
                           capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,(run.stderr+run.stdout)[-2500:])
        self.assertIn('fail 0',run.stdout)
        self.assertIn('pass 36',run.stdout)

if __name__=='__main__':
    unittest.main()
