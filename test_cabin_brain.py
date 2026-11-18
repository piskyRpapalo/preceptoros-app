"""HEXELION V1 cabin (Talk): the Brain band and each answer's provenance.

Wiring checks; the pure cases live in tests/cabin_brain_cases.cjs. The band reads /api/cerebro (no new endpoint),
the signatures stay in Boundary (the cabin only links there), heads stay NO_DATA until their contract exists."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def leer(ruta):
    return (ROOT / ruta).read_text(encoding="utf-8")


class Cabina(unittest.TestCase):
    def test_la_banda_vive_en_talk_antes_del_hilo(self):
        html = leer("interface/app.html")
        talk = html[html.index('id="panel-conversacion"'):]
        self.assertLess(talk.index('id="cabina-brain"'), talk.index('id="hilo"'))
        for ident in ("brain-uso", "brain-opciones", "brain-heads", "brain-firmas"):
            self.assertIn(f'id="{ident}"', talk)
        self.assertIn('role="radiogroup"', talk[:talk.index('id="hilo"')])

    def test_sin_endpoint_nuevo_y_sin_firmar_fuera_de_boundary(self):
        conv = leer("interface/conversacion.js") + leer("interface/cabin_brain.js")
        self.assertEqual(set(re.findall(r'fetch\("(/api/[a-z/]+)', conv)), {"/api/cerebro", "/api/conversacion"})
        self.assertNotIn("/api/hitl", conv)
        self.assertNotIn("X-Hitl-Token", conv)
        self.assertIn("[data-panel=\"gobierno\"]", conv.replace("'", '"'))

    def test_las_palabras_visibles_son_inglesas(self):
        conv = leer("interface/conversacion.js")
        cab = leer("interface/cabin_brain.js")
        # the translation table's keys are the server's own words (data in, never shown): left out of the scan
        cab = cab[:cab.index("const reasons = {")] + cab[cab.index("};", cab.index("const reasons = {")):]
        bloque = conv[conv.index("function provenance"):conv.index("function row(")] + cab
        visibles = [s for s in re.findall(r'"([^"\n]*[A-Za-z][^"\n]*)"', bloque) if not s.startswith("/")]
        self.assertIn("Brain · ", visibles)
        for v in visibles:
            self.assertNotRegex(v, r"(?i)\b(cerebro|firma|sin datos|elegido)\b", v)

    def test_objetivos_de_44px_y_forced_colors(self):
        css = leer("interface/app.css")
        self.assertRegex(css, r"\.brain-op, \.cabina-brain \.brain-firmas \{ min-height: 44px; min-width: 44px")
        self.assertIn("@media (forced-colors: active) { .cabina-brain", css)

    def test_version_y_cache(self):
        html = leer("interface/app.html")
        self.assertIn('<script src="/conversacion.js?v=7"></script>', html)
        self.assertLess(html.index("/evidence_chip.js?v=3"), html.index("/cabin_brain.js?v=1"))
        self.assertIn('"/cabin_brain.js": ("cabin_brain.js"', leer("bin/preceptoros-pwa"))
        self.assertIn('"/cabin_brain.js?v=1"', leer("interface/sw.js"))
        self.assertLess(len(leer("interface/cabin_brain.js").encode()), 8192)
        sw = leer("interface/sw.js")
        self.assertIn('"/conversacion.js?v=7"', sw)
        self.assertIn("preceptoros-armazon-v214", sw)

    @unittest.skipUnless(shutil.which("node"), "node no esta")
    def test_casos_puros(self):
        r = subprocess.run([shutil.which("node"), str(ROOT / "tests" / "cabin_brain_cases.cjs")], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"ok":true', r.stdout)


if __name__ == "__main__":
    unittest.main()
