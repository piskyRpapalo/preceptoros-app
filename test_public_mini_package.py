"""Public-safe deterministic MINI is derived from the approved six-panel APP.
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

    def test_six_main_panels_and_owner_safe_components_derive_from_existing_app(self):
        original = (ROOT / "interface/app.html").read_text(encoding="utf-8")
        projected = module.shell(original)
        keys = ("conversacion", "cuaderno", "lab", "ajustes", "modelos", "settings")
        self.assertEqual(projected.count('role="tab"'), len(keys))
        for name in keys:
            self.assertEqual(projected.count('id="tab-' + name + '"'), 1)
            self.assertEqual(projected.count('id="panel-' + name + '"'), 1)
        self.assertNotIn('role="tab" aria-controls="panel-documentos"', projected)
        # Source-derived, not maintained in a second document/owner template.
        for tag, element_id in (("section","mvp-first-run"),
                                ("section","node-public-template"),
                                ("details","superbot-agent-disclosure"),
                                ("form","node-identity-form"),
                                ("div","talk-processing")):
            self.assertIn(module.extract(original,tag,element_id),projected)
        docs = module.extract(original,"section","notebook-document-editor")
        self.assertIn('id="documentos-guardar"',docs)
        self.assertIn('id="documentos-guardar"',projected)
        for js in ("offline_mini.js","mvp_first_run.js","talk_crab_canvas.js"):
            self.assertIn('src="./'+js+'"',projected)
        self.assertNotIn('src="./app.js"', projected)
        self.assertNotIn('src="./hitl.js"', projected)
        self.assertNotIn("preceptoros-private-mesa", projected)
        self.assertNotIn('href="/api/', projected)

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
                self.assertEqual(manifest["schema"],"preceptoros.public-mini-package/2")
                self.assertEqual(manifest["mode"],"SIX_ZONE_PUBLIC_SAFE_DETERMINISTIC_ONLY")
                self.assertEqual(manifest["source_panels"],
                                 ["conversacion","cuaderno","lab","ajustes","modelos","settings"])
                self.assertTrue(manifest["projection_not_android_apk"])
                self.assertEqual(manifest["approved_app_sw"],"preceptoros-armazon-v235")
                self.assertTrue(manifest["no_model_download"])
                self.assertTrue(manifest["no_rack_connection"])
                self.assertEqual(manifest["public_entry"], "/app/")
                for filename, expected in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(z.read("app/" + filename)).hexdigest(), expected)
                self.assertEqual(z.read("app/offline_mini.js"),
                                 (ROOT / "mvp-android/offline_mini.js").read_bytes())
                for asset in ("mvp_first_run.js","talk_crab_canvas.js",
                              "face/bubble/openworld_crab_body.js"):
                    self.assertEqual(z.read("app/"+asset),(ROOT/"interface"/asset).read_bytes())
                self.assertNotIn("app/app.js", names)
                self.assertNotIn("app/hitl.js", names)
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
            run = subprocess.run(["node", "tests/public_mini_browser.mjs", str(width)],
                                 cwd=ROOT, capture_output=True, text=True, timeout=75)
            # bin/pruebas prints only FAIL/ERROR header lines in CI. Attach
            # bounded synthetic-browser evidence to that header on failure:
            # this never includes live owner data, URLs or credentials.
            browser_failure = ((run.stderr + run.stdout).strip()[-380:]
                               if run.returncode else "none")
            with self.subTest(width=width, browser_failure=browser_failure):
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('"status":"PASS"', run.stdout)
                self.assertIn('"apiRequests":0', run.stdout)

    def test_bad_or_duplicate_source_identity_fails_closed(self):
        original = (ROOT / "interface/app.html").read_text()
        self.assertRaises(ValueError, module.shell, original.replace('id="tab-lab"', 'id="tab-extra"'))
        self.assertRaises(ValueError, module.shell, original.replace('id="tab-settings"', 'id="tab-extra"'))
        self.assertRaises(ValueError, module.shell, original.replace('id="tab-modelos"', 'id="tab-ajustes"'))
        self.assertRaises(ValueError, module.shell, original.replace('id="node-public-template"', 'id="other-template"'))
        self.assertRaises(ValueError, module.shell, original.replace('id="mvp-first-run"', 'id="legacy-intro"'))
        self.assertRaises(ValueError, module.extract, original, "form", "missing-form")
        self.assertRaises(ValueError, module.shell, original.replace('Sign deployment', 'Unsigned cédula POST'))

if __name__ == "__main__":
    unittest.main()
