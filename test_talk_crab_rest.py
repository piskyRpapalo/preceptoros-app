"""Talk crab: at rest it stands still; it moves only while an engine state says a model works."""
import re
import unittest
from pathlib import Path

CSS = Path(__file__).parent.joinpath("interface", "app.css").read_text(encoding="utf-8")
JS = Path(__file__).parent.joinpath("interface", "talk_crab_canvas.js").read_text(encoding="utf-8")


class TalkCrabRest(unittest.TestCase):
    def test_css_crossing_is_paused_unless_a_working_state_runs_it(self):
        block = re.search(r"#talk-processing \.talk-processing-crab \{\s*animation: talk-crab-sidestep[^}]*\}", CSS).group(0)
        self.assertIn("animation-play-state: paused", block)
        running = re.search(r"#talk-processing:is\(([^)]*\)[^{]*)\{\s*animation-play-state: running;", CSS)
        self.assertIsNotNone(running)
        for state in ("LOADING", "GENERATING", "SPEAKING", "PROCESSING"):
            self.assertIn('[data-state="%s"]' % state, running.group(1))
        self.assertNotIn('[data-state="IDLE"]', running.group(1))
        self.assertRegex(CSS, r"prefers-reduced-motion: reduce\)[^}]*\{\s*#talk-processing \.talk-processing-crab \{ animation: none")

    def test_canvas_has_no_idle_walk_or_timed_greeting(self):
        self.assertIn("new Set(['PROCESSING','SIMULATED','LOADING','GENERATING','SPEAKING'])", JS)
        self.assertNotIn("planGreeting", JS)
        self.assertNotIn("scene='walking'", JS)
        self.assertNotIn("setTimeout(", JS)
        self.assertIn("scene=active()?'processing':'rest'", JS)


if __name__ == "__main__":
    unittest.main()
