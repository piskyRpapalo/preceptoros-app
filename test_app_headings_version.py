"""Round 2 · Objective 4 contract (pure, CI-safe). Real Chromium proof: tests/app_headings_version.browser.cjs."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "interface/app.html").read_text(encoding="utf8")
CSS = (ROOT / "interface/app.css").read_text(encoding="utf8")


class HeadingsAndVersion(unittest.TestCase):
    def test_five_duplicate_titles_hidden_visually_kept_semantically(self):
        for h2, name in (("notebook-title", "Operations Data"), ("h-lab", "Lab"), ("h-modelos", "Open World"),
                         ("h-ajustes", "My node"), ("h-settings", "Settings")):
            m = re.search(r'<header class="panel-cabecera sr"><h2[^>]*id="%s">%s</h2></header>' % (h2, name), HTML)
            self.assertIsNotNone(m, h2)
        self.assertIn('<h2 id="h-conversacion" class="sr">Talk</h2>', HTML)  # Talk untouched
        self.assertIn(".panel-cabecera.sr { margin: 0; padding: 0; border: 0; }", CSS)

    def test_release_names_come_only_from_versioncode(self):
        self.assertIn("7: 'PreceptorOS APP 1.0 · Android build 7', 8: 'PreceptorOS APP 1.1 · Android build 8'", HTML)
        self.assertIn("'PreceptorOS APP · Shell ' + shellText + ' · NO_DATA(release_manifest_unverified)'", HTML)
        self.assertNotIn("navigator.userAgent", HTML)
        line = re.search(r'<p class="pie settings-version" id="settings-version"[^>]*>', HTML).group(0)
        self.assertNotIn("role=", line)
        self.assertNotIn("aria-live", line)  # the Talk version line is the only live announcement

    def test_served_versions_aligned(self):
        sw = (ROOT / "interface/sw.js").read_text(encoding="utf8")
        self.assertIn('href="/app.css?v=57"', HTML)
        self.assertIn('"/app.css?v=57"', sw)
        self.assertIn('const Cache = "preceptoros-armazon-v243"', sw)


if __name__ == "__main__":
    unittest.main()
