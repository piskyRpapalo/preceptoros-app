"""Plans in the panels (Superbot contract #310): Talk, Command, Notebook, Lab and Harness tell one plan.

Wiring checks; the pure cases live in tests/plan_cases.cjs. No panel is added, no grant is made here: real rows keep
Authorize/Deny disabled until the grant service exists, and SYNTHETIC rows never act. The plan store, proposals,
grants, the journal adapter and the orchestrator choice are Codex's; until they answer every panel says NO_DATA."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULOS = ("plan_flow", "plan_fixture", "plan_panels", "plan_composer")


def leer(ruta):
    return (ROOT / ruta).read_text(encoding="utf-8")


class PlanEnLosPaneles(unittest.TestCase):
    def test_los_casos_en_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("NO_DATA · sin node no se ejecutan los casos del plan. Remedio: instalar Node")
        r = subprocess.run([node, "--test", str(ROOT / "tests" / "plan_cases.cjs")], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^ℹ pass ([1-9]\d*)$")
        self.assertRegex(r.stdout, r"(?m)^ℹ fail 0$")

    def test_cada_modulo_cabe_en_un_mini(self):
        for m in MODULOS:
            self.assertLess(len(leer(f"interface/{m}.js").encode()), 8192, m)

    def test_servidos_cacheados_y_cargados_en_orden(self):
        pwa, sw, html = leer("bin/preceptoros-pwa"), leer("interface/sw.js"), leer("interface/app.html")
        for m in MODULOS:
            self.assertIn(f'"/{m}.js": ("{m}.js",', pwa, m)
            self.assertIn(f'"/{m}.js?v=1"', sw, m)
            self.assertIn(f'<script src="/{m}.js?v=1"></script>', html, m)
        orden = [html.index(f"/{m}.js") for m in ("evidence_chip", "plan_flow", "plan_fixture", "plan_panels")]
        self.assertEqual(orden, sorted(orden), "the grammar and the logic load before the painters")

    def test_ningun_panel_nuevo(self):
        html = leer("interface/app.html")
        self.assertEqual(len(re.findall(r'role="tabpanel"', html)), len(re.findall(r'role="tab"', html)))
        self.assertNotRegex(html, r'id="panel-(superbot|plan)')
        for hogar, ids in {"panel-conversacion": ("talk-plan", "plan-texto", "plan-guardar"),
                           "panel-mando": ("mando-plan-tareas", "mando-plan-estado"),
                           "panel-cuaderno": ("notebook-plans",), "panel-lab": ("lab-runs",),
                           "panel-harness": ("harness-plan-agents",)}.items():
            ini = html.index(f'id="{hogar}"')
            fin = html.find('<section class="panel"', ini + 1)
            trozo = html[ini:fin if fin > 0 else len(html)]
            for i in ids:
                self.assertIn(f'id="{i}"', trozo, f"{i} lives in {hogar}")

    def test_ningun_mensaje_ni_campo_concede(self):
        panels = leer("interface/plan_panels.js")
        self.assertIn("if (!p.synthetic) { yes.disabled = no.disabled = true; }", panels)
        self.assertIn("if (!e.isTrusted) return;", panels)
        self.assertNotRegex(panels, r"fetch\([^)]*method|POST", "the panels only read")
        self.assertIn('a.by === "person"', leer("interface/plan_flow.js"))
        comp = leer("interface/plan_composer.js")
        self.assertNotIn("fetch(", comp, "the composer sends nothing until the plan store exists")
        self.assertNotRegex(comp, r"ta\.value\.(slice|substring|substr)\(|maxlength", "the plan is never cut")

    def test_el_producto_base_no_promete_hexelion(self):
        for m in MODULOS:
            self.assertNotRegex(leer(f"interface/{m}.js"), r"(?i)hexelion", m)


if __name__ == "__main__":
    unittest.main()
