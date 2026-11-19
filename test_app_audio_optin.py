"""APP MVP: navigation audio cannot bypass owner preference."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
class AudioOptIn(unittest.TestCase):
    def test_tab_change_is_quiet_until_owner_consents(self):
        src=(ROOT/"interface/app.js").read_text()
        assert "window.PreceptorAchoSonido?.enabled()" in src
        assert src.index("window.PreceptorAchoSonido?.enabled()") < src.index("window.PreceptorSting.tocar().catch")
    def test_audio_default_is_off(self):
        src=(ROOT/"interface/acho_sonido.js").read_text()
        assert 's.getItem(KEY) === "on"' in src
        assert "if (!enabled(host)) return" in src
