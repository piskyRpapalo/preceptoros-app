"""Lisbon Table operator truth gates: the guide is a receipt, not a product claim."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parent
APP=ROOT/"interface/app.html"
SW=ROOT/"interface/sw.js"
GUIDE=ROOT/"docs/LISBON_TABLE_APP_ONEPAGE_20261119.md"
GT=ROOT/"docs/LISBON_TABLE_APP_GROUNDTRUTH_20261119.md"

class LisbonTableOperator(unittest.TestCase):
    def test_one_page_exists_and_meta1_is_human_owned(self):
        s=GUIDE.read_text(encoding="utf8")
        for phrase in (
            "19 November 2026","Meta 1","docs-only Companion HITL",
            "HITL · Companion Declaration", "companions/<your-handle>/DECLARATION.md",
            "companions/<your-handle>/STATE.md", "experiments/<slug>/README.md",
            "NO_DATA(GitHub_account_or_PR_not_created)",
            "The Sovereign retains all admission and signature decisions",
        ):
            self.assertIn(phrase,s)
        self.assertLessEqual(len(s.split()),850,"a café card must stay succinct")

    def test_install_truth_and_minirouter_not_rack(self):
        s=GUIDE.read_text()
        for phrase in (
            "personal_mvp","Use Mini Orchestrator offline", "Hexelion is only on the Sovereign's rack",
            "http://127.0.0.1:8740/app",
            "NO_DATA(model_not_installed_or_verified)", "No model was bundled",
            "The v1.3 downloadable installer has older Ollama guidance",
            "NO_DATA(native_personal_APP_not_verified)",
        ):
            self.assertIn(phrase,s)
        self.assertNotIn("use our Hexelion",s.lower())

    def test_current_app_copy_fits_lisbon_meta1(self):
        html=APP.read_text()
        js=(ROOT/"interface/companion_onboarding.js").read_text()
        sw=SW.read_text()
        old=(ROOT/"docs/DAY_D_4_COLLABORATORS.md").read_text()
        self.assertIn("Prepare a docs-only Companion HITL PR",html.replace("prepare a docs-only","Prepare a docs-only"))
        self.assertIn("At the table, prepare a docs-only Companion HITL PR",js)
        self.assertIn("LISBON_TABLE_APP_ONEPAGE_20261119.md",old)
        self.assertNotIn("Only **after the room**",old)
        self.assertIn("const Cache = \"preceptoros-armazon-v232\"",sw)
        self.assertIn('src="/companion_onboarding.js?v=5"',html)
        self.assertIn('"/companion_onboarding.js?v=5"',sw)

    def test_four_groundtruth_checks_are_not_fake_live(self):
        s=GT.read_text()
        for marker in (
            "Zero hidden telemetry","Explicit Ed25519 HITL",
            "host node's own conditions","atlas.sobre/1",
            "atlas.paquete_mp/1","under 1024 bytes",
        ):
            self.assertIn(marker,s)
        for cause in (
            "NO_DATA(public_web_zero_external_load_not_owned_by_APP)",
            "NO_DATA(ephemeral_ed25519_signed_interaction_E2E_not_verified)",
            "NO_DATA(host_conditions_acceptance_E2E_not_verified)",
            "NO_DATA(signed_window_to_node_packet_E2E_not_verified)",
        ):
            self.assertIn(cause,s)
        self.assertNotIn("groundtruth_E2E_VERIFIED",s)

    def test_feedback_owner_disk_only_and_no_beelink_mailbox(self):
        guide=GUIDE.read_text()
        gt=GT.read_text()
        for text in (guide,gt):
            self.assertIn("node owner's",text)
            self.assertIn("Beelink",text)
            self.assertIn("NO_DATA(",text)
        self.assertIn("NO_DATA(remote_authenticated_feedback_delivery_E2E)",gt)

    def test_l_a2_reusable_no_write_probe_exists(self):
        p=ROOT/"tests/lisbon_personal_live_guard.browser.cjs"
        s=p.read_text()
        self.assertIn("synthetic Lisbon table personal profile proof",s)
        self.assertIn("route.fulfill({status:403",s)
        self.assertIn("result.attempted_posts,0",s)
        self.assertIn("result.private_thread_attempts,0",s)
        self.assertIn("result.external_requests,0",s)
        self.assertNotIn("localStorage.setItem('preceptoros.profile','private_rack')",s)

if __name__=="__main__":
    unittest.main()
