"""HEX-NODE3: a collaborator's device signs its own plan and cédula; only public material leaves."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import os
import stat

import node_building
import node_lifecycle as L
import node_owner
import nodo_app

NODE = "nodo.904.fixture-collaborator"
AT = "2026-11-22T20:00:00Z"


class Owner(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "app"
        self.home.mkdir(mode=0o700)
        node_building.provisionar_identidad(self.home, NODE)
        self.request = {"schema": "preceptoros.deployment-request/1", "node": NODE, "consent": True,
                        "nonce": "a" * 32, "device_sha256": "d" * 64}
        self.ref = L._digest(self.request)
        self.assertTrue(L.record_intake(self.home, self.request, {
            "schema": "preceptoros.deployment-request-receipt/1", "request_id": self.ref,
            "state": "AWAITING_HUMAN", "received_at": AT}))

    def test_owner_key_is_born_private_and_never_replaced(self):
        first = node_owner.prepare(self.home)
        key = self.home / "node-owner" / "owner_ed25519"
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.home / "node-owner").stat().st_mode), 0o700)
        self.assertEqual(node_owner.prepare(self.home), first)
        self.assertTrue(first.startswith("ssh-ed25519 "))

    def test_existing_trust_file_is_never_touched(self):
        trust = self.home / "allowed_signers_cedula"
        trust.write_text("soberano ssh-ed25519 AAAAexisting\n")
        node_owner.prepare(self.home)
        self.assertEqual(trust.read_text(), "soberano ssh-ed25519 AAAAexisting\n")

    def test_signed_plan_and_cedula_bind_the_recorded_intake_and_verify_locally(self):
        out = node_owner.sign_admission(self.home, NODE)
        card, (node, entry), = out["cedula"], *out["bundle"].items()
        self.assertEqual(node, NODE)
        self.assertEqual(entry["plan"]["request_sha256"], self.ref)
        self.assertEqual(card["dispositivos"], [{"clave": "d" * 64, "estado": "solicitado"}])
        self.assertEqual(card["plan_sha256"], entry["plan"]["sha256"])
        self.assertEqual(nodo_app.autenticidad(card, self.home / "allowed_signers_cedula")[0], "OK")
        # The existing lifecycle accepts it once Aduana returns a matching receipt.
        receipt = {"esquema": "preceptoros.recibo-cedula/1", "node_id": NODE, "admin_sha256": card["admin"],
                   "plan_sha256": card["plan_sha256"], "credential_sha256": card["sha256"],
                   "estado": "verificado", "causa": None, "recibido": AT}
        receipt["recibo_sha256"] = L._digest(receipt)
        self.assertTrue(L.record_export(self.home, card, receipt))
        self.assertEqual(L.read(self.home)["stages"]["signature"]["state"], "MEASURED")

    def test_only_public_material_leaves(self):
        out = json.dumps(node_owner.sign_admission(self.home, NODE))
        private = (self.home / "node-owner" / "owner_ed25519").read_text()
        self.assertNotIn("PRIVATE KEY", out)
        self.assertNotIn(private.splitlines()[1], out)
        self.assertNotIn(self.request["nonce"], out)

    def test_refuses_without_intake_or_outside_cedula_namespace(self):
        with self.assertRaises(ValueError):
            node_owner.sign_admission(self.home, "fixture-alias")
        with self.assertRaises((OSError, ValueError)):
            node_owner.sign_admission(self.home, "nodo.905.no-intake")

    def test_a_tampered_intake_is_refused(self):
        data = L._load(self.home, NODE, "intake")
        data["request"]["device_sha256"] = "e" * 64  # receipt no longer matches the request
        self.assertTrue(L._store(self.home, NODE, "intake", data))
        with self.assertRaises(ValueError):
            node_owner.sign_admission(self.home, NODE)

    def test_refuses_a_shared_owner_directory(self):
        os.chmod(node_owner._owner_dir(self.home), 0o755)
        with self.assertRaises(ValueError):
            node_owner.prepare(self.home)
