"""Fleet in Harness: one hexagon per node the app can read, one fact per side, the same facts as a list in words.

Wiring checks; the pure cases live in tests/fleet_map_cases.cjs. Reads /api/estado only (no new endpoint); other
nodes stay NO_DATA until the fleet contract exists; synthetic nodes appear only with ?fleet=synthetic."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def leer(ruta):
    return (ROOT / ruta).read_text(encoding="utf-8")


class Flota(unittest.TestCase):
    def test_la_flota_abre_harness_antes_del_equipo(self):
        html = leer("interface/app.html")
        h = html[html.index('id="panel-harness"'):html.index('id="panel-puerta"')]
        self.assertLess(h.index('id="fleet"'), h.index('id="team"'))
        self.assertIn('id="fleet-estado" role="status" aria-live="polite"', h)

    def test_solo_lee_estado_y_el_dibujo_esta_oculto_al_lector(self):
        js = leer("interface/fleet_map.js")
        self.assertEqual(set(re.findall(r'fetch\("(/api/[a-z/]+)', js)), {"/api/estado"})
        self.assertIn('svg.setAttribute("aria-hidden", "true")', js)
        self.assertNotIn("method:", js)

    def test_lo_sintetico_solo_con_su_bandera(self):
        js = leer("interface/fleet_map.js")
        self.assertIn("fleet=synthetic", js)
        self.assertEqual(js.count("cells.push(...synthetic())"), 1)

    def test_tamano_version_y_cache(self):
        self.assertLess(len(leer("interface/fleet_map.js").encode()), 8192)
        html = leer("interface/app.html")
        self.assertLess(html.index("/evidence_chip.js?v=1"), html.index("/fleet_map.js?v=1"))
        self.assertIn('"/fleet_map.js": ("fleet_map.js"', leer("bin/preceptoros-pwa"))
        sw = leer("interface/sw.js")
        self.assertIn('"/fleet_map.js?v=1"', sw)
        self.assertIn("preceptoros-armazon-v196", sw)

    def test_forced_colors_y_44px(self):
        css = leer("interface/app.css")
        self.assertIn(".fleet-list summary { min-height: 44px;", css)
        self.assertIn("@media (forced-colors: active) { .fleet-side", css)

    @unittest.skipUnless(shutil.which("node"), "node no esta")
    def test_casos_puros(self):
        r = subprocess.run([shutil.which("node"), str(ROOT / "tests" / "fleet_map_cases.cjs")], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"ok":true', r.stdout)


if __name__ == "__main__":
    unittest.main()
