"""Public MINI is a reproducible projection of the existing four-zone APP.
Tests use only local files and synthetic browser data. No network.
"""
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("public_mini_builder", ROOT / "bin/package_public_mini.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class PublicMiniPackage(unittest.TestCase):
    def test_first_time_project_guide_behaviour(self):
        p = subprocess.run(["node", "--test", "tests/public_mini_project_cases.cjs"],
                           cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("pass 12", p.stdout)
        self.assertIn("fail 0", p.stdout)

    def test_four_main_zones_are_projection_of_existing_app(self):
        original = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        shell = module.shell(original)
        self.assertEqual(shell.count('role="tab"'), 4)
        for name in ("conversacion", "documentos", "lab", "ajustes"):
            self.assertEqual(shell.count('id="tab-' + name + '"'), 1)
            self.assertEqual(shell.count('id="panel-' + name + '"'), 1)
        # Real APP Documents markup and form-chat from source, not a second clone.
        self.assertIn(module.extract(original, "section", "panel-documentos"), shell)
        self.assertIn('src="./offline_mini.js"', shell)
        self.assertNotIn('src="./app.js"', shell)
        self.assertNotIn("preceptoros-private-mesa", shell)
        self.assertNotIn('href="/api/', shell)

    def test_bundle_is_offline_reproducible_and_source_hashed(self):
        with tempfile.TemporaryDirectory(prefix="preceptoros-public-mini-") as d:
            root = pathlib.Path(d)
            out = root / "build"
            first = module.build(out)
            archive = pathlib.Path(first["zip"])
            binary = archive.read_bytes()
            self.assertEqual(hashlib.sha256(binary).hexdigest(), first["sha256"])
            with zipfile.ZipFile(archive) as z:
                names = z.namelist()
                self.assertEqual(len(names), len(set(names)))
                self.assertIn("app/index.html", names)
                manifest = json.loads(z.read("app/package-manifest.json"))
                self.assertTrue(manifest["no_model_download"])
                self.assertTrue(manifest["no_rack_connection"])
                self.assertEqual(manifest["public_entry"], "/app/")
                for filename, expected in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(z.read("app/" + filename)).hexdigest(), expected)
                self.assertEqual(z.read("app/offline_mini.js"),
                                 (ROOT / "mvp-android/offline_mini.js").read_bytes())
                self.assertNotIn("app/app.js", names)
            second = module.build(out)
            self.assertEqual(second["sha256"], first["sha256"])
            self.assertEqual(archive.read_bytes(), binary)

    def test_package_no_implicit_external_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="preceptoros-public-mini-gate-") as d:
            result = module.build(pathlib.Path(d) / "out")
            app = pathlib.Path(d) / "out/app"
            scripts = [(p.name, p.read_text()) for p in app.glob("*.js")]
            names = [name for name, _ in scripts]
            for forbidden in ("app.js", "conversacion.js", "hitl.js", "energy_ui.js",
                              "mcp.js", "gateway.js", "node_runtime.js"):
                self.assertNotIn(forbidden, names)
            sw = (app / "sw.js").read_text()
            self.assertIn("event.request", sw)
            self.assertIn("url.origin!==self.location.origin", sw)
            self.assertIn("'/api/'", sw)
            manifest = json.loads((app / "manifest.webmanifest").read_text())
            self.assertEqual(manifest["id"], "/app/")
            self.assertEqual(manifest["scope"], "/app/")
            self.assertNotIn("127.0.0.1:21434", str(scripts))
            self.assertNotIn("/api/charla", (app / "index.html").read_text())
            self.assertFalse(any(p.suffix in {".gguf", ".onnx", ".bin"} for p in app.rglob("*")))
            self.assertGreater(result["size"], 10000)
            self.assertLess(result["size"], 800000)

    @unittest.skipUnless(shutil.which("google-chrome"), "headless Chrome absent in runner")
    def test_real_mobile_browser_360_and_420_offline(self):
        # The real browser uses a disposable Chrome profile and loopback-only
        # server. It never touches the installed S110 application.
        module.build(ROOT / "dist/public-mini-app")
        for width in (360, 420):
            with self.subTest(width=width):
                run = subprocess.run(["node", "tests/public_mini_browser.mjs", str(width)],
                                     cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('"status":"PASS"', run.stdout)
                self.assertIn('"apiRequests":0', run.stdout)

    def test_bad_or_duplicate_source_identity_fails_closed(self):
        original = (ROOT / "interface/app.html").read_text()
        self.assertRaises(ValueError, module.shell, original.replace('id="tab-lab"', 'id="tab-extra"'))
        self.assertRaises(ValueError, module.extract, original, "form", "missing-form")
        self.assertRaises(ValueError, module.shell, original.replace('Sign deployment', 'Unsigned cédula POST'))

if __name__ == "__main__":
    unittest.main()
