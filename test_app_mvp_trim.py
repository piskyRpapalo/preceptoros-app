"""MVP face: six tabs; Memory/Boundary/Harness are native disclosures."""
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
    def test_six_public_tabs_and_no_advanced_navigation(self):
        tabs = re.findall(r'<button id="tab-([^"]+)"([^>]*)>', HTML)
        self.assertEqual([name for name, _ in tabs],
            ["conversacion", "cuaderno", "lab", "ajustes", "modelos", "settings"])
        self.assertTrue(all(" hidden" not in attrs for _, attrs in tabs))
        self.assertNotIn("data-mvp", HTML)
        self.assertNotIn('id="technical-options-toggle"', HTML)
        self.assertNotIn('id="advanced-mode-toggle"', HTML)
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
    def test_navigation_and_legacy_deep_link_go_to_parent_panel(self):
        self.assertIn("function visiblePanelIndices()", JS)
        self.assertIn("document.querySelectorAll('.pestanas [role=\"tab\"]:not([hidden])')", JS)
        self.assertIn("visibleNeighbor(n, 1, true)", JS)
        self.assertIn("visibleNeighbor(panelActual, step)", JS)
        self.assertIn('mando: "cuaderno"', JS)
        self.assertIn('gobierno: "lab"', JS)
        self.assertIn('harness: "lab"', JS)

    def test_operational_notebook_starts_folded_and_world_stays_embedded(self):
        a = HTML.index('id="panel-cuaderno"')
        b = HTML.index('id="panel-lab"', a)
        notebook = HTML[a:b]
        self.assertEqual(notebook.count('<details class="grupo">'), 7)
        self.assertNotIn('<details class="grupo" open>', notebook)
        self.assertIn('id="notebook-title">Operations Data', notebook)
        self.assertIn('id="openworld-frame"', HTML)
        self.assertIn('id="tab-modelos"', HTML)
        self.assertIn('aria-label="Open World"', HTML)

    def test_editor_memory_boundary_harness_have_one_owner(self):
        notebook = HTML.split('id="panel-cuaderno"',1)[1].split('id="panel-lab"',1)[0]
        lab = HTML.split('id="panel-lab"',1)[1].split('id="panel-modelos"',1)[0]
        for id in ("tab-documentos","panel-documentos","tab-mando","panel-mando",
                   "tab-gobierno","panel-gobierno","tab-harness","panel-harness"):
            self.assertNotIn('id="'+id+'"', HTML)
        for id in ("notebook-document-editor-toggle","notebook-document-editor",
                   "documentos-items","notebook-memory-group","compass-container",
                   "captura-consent","tarjeta-frontera"):
            self.assertIn('id="'+id+'"',notebook)
        for id in ("lab-loops","lab-boundary-group","lab-harness-group","hitl","fleet"):
            self.assertIn('id="'+id+'"',lab)
        self.assertNotIn('id="notebook-loops"',notebook)
        self.assertNotIn('id="advanced-mode-toggle"',HTML)
        self.assertNotIn('id="technical-options-close"',HTML)

    def test_node_setup_is_existing_read_not_false_deploy(self):
        self.assertIn('id="mvp-open-node"', HTML)
        self.assertIn('id="ajustes-nodo"', HTML)
        self.assertIn('NO_DATA(node_deployment_E2E_not_verified)', HTML)
        self.assertIn('button.click(); // Existing read-only identity operation', JS)
        self.assertNotIn('id="node-deploy"', HTML)
    def test_worker_is_not_stale(self):
        self.assertIn('preceptoros-armazon-v249', SW)
        for path in ('/app.js?v=58', '/app.css?v=57', '/zonas.js?v=7'):
            self.assertIn(path, HTML)
            self.assertIn(path, SW)

if __name__ == "__main__":
    unittest.main()
