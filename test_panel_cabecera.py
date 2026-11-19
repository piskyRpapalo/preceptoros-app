"""Six public panel headers; specialist readers live inside disclosure groups."""
import pathlib
import re
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
HTML = (ROOT / "interface/app.html").read_text(encoding="utf-8")
JS = (ROOT / "interface/app.js").read_text(encoding="utf-8")
PANELS = ["conversacion", "cuaderno", "lab", "modelos", "ajustes", "settings"]
ENGLISH = {"conversacion": "Talk", "cuaderno": "Operations Data",
           "lab": "Lab", "modelos": "Open World", "ajustes": "My node", "settings": "Settings"}
WITH_REFRESH = {"conversacion", "cuaderno", "lab", "ajustes"}
WITH_STATUS = set(PANELS)


class Headers(HTMLParser):
    def __init__(self):
        super().__init__()
        self.panel, self.depth, self.inside, self.found = None, 0, False, {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section" and a.get("role") == "tabpanel":
            self.panel = a["id"].removeprefix("panel-")
            self.found[self.panel] = {"label": a.get("aria-label"), "first": None, "h2": 0, "status": 0, "refresh": []}
            return
        if self.panel is None:
            return
        info = self.found[self.panel]
        if info["first"] is None:
            info["first"] = "header" if tag == "header" and "panel-cabecera" in a.get("class", "") else tag
        if tag == "header" and "panel-cabecera" in a.get("class", "") and not info.get("header_seen"):
            # Nested document editor / operator headers are not a second tab header.
            info["header_seen"] = True
            self.inside, self.depth = True, 0
        elif self.inside:
            if tag == "h2":
                info["h2"] += 1
            if a.get("role") == "status":
                info["status"] += 1
            if tag == "button" and "refrescar" in a.get("class", ""):
                info["refresh"].append(a)

    def handle_endtag(self, tag):
        if tag == "header" and self.inside:
            self.inside = False


class PanelHeader(unittest.TestCase):
    def setUp(self):
        self.p = Headers()
        self.p.feed(HTML)

    def test_every_panel_opens_with_one_header_and_one_title(self):
        self.assertEqual(sorted(self.p.found), sorted(PANELS))
        for panel in PANELS:
            info = self.p.found[panel]
            self.assertEqual(info["first"], "header", panel)
            self.assertEqual(info["h2"], 1, panel)

    def test_status_lines_and_english_names(self):
        for panel in PANELS:
            info = self.p.found[panel]
            begin = HTML.index('id="panel-'+panel+'"')
            end = HTML.find('<section class="panel"', begin+1)
            section = HTML[begin:end if end >= 0 else len(HTML)]
            self.assertIn('role="status"', section, panel)
            self.assertEqual(info["label"], ENGLISH[panel], panel)

    def test_refresh_actions_only_where_loader_exists_and_always_named(self):
        table = re.search(r"const cargadores = \{(.*?)\n\};", JS, re.S).group(1)
        loaders = set(re.findall(r"^  (\w+):", table, re.M))
        self.assertEqual(loaders, WITH_REFRESH | {"gobierno", "harness"})
        for panel in PANELS:
            begin = HTML.index('id="panel-'+panel+'"')
            end = HTML.find('<section class="panel"', begin+1)
            section = HTML[begin:end if end >= 0 else len(HTML)]
            # Nested Memory/Boundary/Harness controls are not the panel's second-row refresh.
            if panel in ("modelos", "settings"):
                self.assertNotIn('data-refrescar="modelos"', section)
            else:
                self.assertIn('data-refrescar="'+panel+'"',section,panel)
                if panel != "cuaderno":
                    self.assertIn('aria-label="Refresh ',section)
            if panel in ("conversacion","cuaderno","lab","ajustes"):
                self.assertIn('class="panel-actions"',section)

    def test_nested_operator_refresh_controls_preserved(self):
        for name in ("gobierno","harness"):
            self.assertIn('data-refrescar="'+name+'"',HTML)
        self.assertIn('id="lab-boundary-group"',HTML)
        self.assertIn('id="lab-harness-group"',HTML)

    def test_opening_and_refreshing_use_the_same_loader(self):
        self.assertIn("cargarPanel(paneles[panelActual].id);", JS)
        self.assertIn('closest("button.refrescar[data-refrescar]")', JS)
        self.assertNotIn('paneles[panelActual].id === "lab") { cargarLab()', JS)


if __name__ == "__main__":
    unittest.main()
