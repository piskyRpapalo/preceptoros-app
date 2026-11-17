"""MVP face: 3D/video panels retired; four primary tabs; advanced readers remain opt-in."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

R = Path(__file__).resolve().parent
HTML = (R/"interface/app.html").read_text()
JS = (R/"interface/app.js").read_text()
ZONES = (R/"interface/zonas.js").read_text()
SW = (R/"interface/sw.js").read_text()

class Mvp(unittest.TestCase):
    def test_four_visible_tabs_and_four_hidden_advanced(self):
        tabs = re.findall(r'<button id="tab-([^"]+)"([^>]*)>', HTML)
        self.assertEqual(len(tabs), 8)
        core = ["mando", "conversacion", "modelos", "ajustes"]
        advanced = ["gobierno", "cuaderno", "lab", "harness"]
        visible = [name for name, attrs in tabs if " hidden" not in attrs]
        self.assertEqual(visible, core)
        for name, attrs in tabs:
            if name in advanced:
                self.assertIn('data-mvp="advanced"', attrs)
                self.assertIn(" hidden", attrs)
        self.assertNotIn("puerta", re.findall(r'id: "([^"]+)"', ZONES))
    def test_3d_and_video_panels_retired_without_deleting_memory(self):
        self.assertNotIn('id="panel-puerta"', HTML)
        self.assertNotIn('id="tab-puerta"', HTML)
        self.assertNotIn('id="fab-form"', HTML)
        self.assertNotIn("PreceptorFabrika", JS)
        self.assertNotIn("fabrika3d", JS)
        self.assertNotIn('id="panel-video"', HTML)
        self.assertNotIn('id="panel-cinek"', HTML)
        self.assertNotIn('localStorage.removeItem("preceptoros.fabrika3d")', JS)
    def test_navigation_skips_hidden_tabs_but_opens_deep_link(self):
        self.assertIn("function visiblePanelIndices()", JS)
        self.assertIn("visibleNeighbor(n, 1, true)", JS)
        self.assertIn("visibleNeighbor(panelActual, step)", JS)
        self.assertIn('showAdvancedTools(true)', JS)
        self.assertIn('mvp-tabs-changed', JS)
        self.assertIn('aria-expanded="false"', HTML)
        self.assertIn('aria-controls="tab-gobierno tab-cuaderno tab-lab tab-harness"', HTML)
    def test_node_setup_is_existing_read_not_false_deploy(self):
        self.assertIn('id="mvp-open-node"', HTML)
        self.assertIn('id="ajustes-nodo"', HTML)
        self.assertIn('NO_DATA(node_deployment_E2E_not_verified)', HTML)
        self.assertIn('button.click(); // Existing read-only identity operation', JS)
        self.assertNotIn('id="node-deploy"', HTML)
    def test_worker_is_not_stale(self):
        self.assertIn('preceptoros-armazon-v205', SW)
        for path in ('/app.js?v=41', '/app.css?v=31', '/zonas.js?v=2'):
            self.assertIn(path, HTML)
            self.assertIn(path, SW)

if __name__ == "__main__":
    unittest.main()
