"""Round 5 · 44 px touch targets (pure, CI-safe). Real Chromium proof: tests/app_touch_targets.browser.cjs."""
from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSS = (ROOT / "interface/app.css").read_text(encoding="utf8")


class TouchTargets(unittest.TestCase):
    def test_measured_short_controls_get_44px(self):
        block = CSS.split("/* Round 5 · touch targets", 1)[1]
        for rule in (".fila-switch { min-height: 44px; }",
                     ".panel button.switch[role=\"switch\"] { box-sizing: content-box; border: 10px solid transparent;",
                     "#panel-cuaderno summary, #panel-lab summary, #panel-ajustes summary { min-height: 44px;",
                     "#compass-modo-camino, #compass-modo-detalle, #nodo-export-send { min-height: 44px; }",
                     "#lab-rack-enlace:not([hidden]) { display: inline-flex;"):
            self.assertIn(rule, block)

    def test_served_versions_aligned(self):
        html = (ROOT / "interface/app.html").read_text(encoding="utf8")
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf8")
        self.assertIn('href="/app.css?v=57"', html)
        self.assertIn('"/app.css?v=57"', sw)
        self.assertIn('const Cache = "preceptoros-armazon-v249"', sw)


if __name__ == "__main__":
    unittest.main()
