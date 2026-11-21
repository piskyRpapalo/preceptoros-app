"""The OWNER lifecycle gate uses correlated SSH and separate authoritative reads."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock, skipUnless
import json
import shutil
import subprocess

import node_building
import node_lifecycle as L
from test_agent_voice import _load_pwa

NODE = "nodo.42.fixture"
NOW = datetime(2026, 11, 21, 19, 0, tzinfo=timezone.utc)
AT = "2026-11-21T18:59:55Z"
TOKEN = "t" * 40


class LifecycleDoor(TestCase):
    def test_owner_loopback_only_and_cross_site_denied_before_source_access(self):
        pwa = _load_pwa()
        for ip, overrides, status in (
            ("127.0.0.1", {}, 200),
            ("192.0.2.9", {}, 403),
            ("127.0.0.1", {"Sec-Fetch-Site": "cross-site"}, 403),
            ("127.0.0.1", {"Origin": "https://preceptoros.org"}, 403),
            ("127.0.0.1", {"X-Forwarded-Proto": "https"}, 403),
            ("127.0.0.1", {"Host": "outside.example.test"}, 403),
        ):
            with self.subTest(ip=ip, headers=overrides):
                h = pwa.PWA.__new__(pwa.PWA)
                h.path = "/api/nodo/estado"
                h.headers = {"Host": "127.0.0.1:8742", **overrides}
                h.server = SimpleNamespace(server_port=8742)
                h.client_address = (ip, 1234)
                h._json = lambda code, body: (code, body)
                with TemporaryDirectory() as home, mock.patch.object(pwa._casa, "raiz", return_value=home), \
                     mock.patch.object(L, "read", wraps=L.read) as read:
                    actual, body = h.do_GET()
                self.assertEqual(actual, status)
                self.assertEqual(body["schema"], L.SCHEMA)
                self.assertEqual(read.call_count, int(status == 200))


@skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class EvidenceLifecycle(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        node_building.provisionar_identidad(self.home, NODE)
        self.key = self.home / "fixture-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        self.signers = self.home / "allowed_signers_cedula"
        self.signers.write_text("soberano " + self.key.with_suffix(".pub").read_text())
        self.token = self.home / "review-token"
        self.token.write_text(TOKEN)
        self.token.chmod(0o600)
        self.request = {"schema": "preceptoros.deployment-request/1", "node": NODE,
                        "consent": True, "nonce": "a" * 32, "device_sha256": "b" * 64}
        self.ref = L._digest(self.request)
        intake = {"schema": "preceptoros.deployment-request-receipt/1", "request_id": self.ref,
                  "state": "AWAITING_HUMAN", "received_at": AT}
        self.assertTrue(L.record_intake(self.home, self.request, intake))
        self.review = {**intake, "state": "APPROVED", "decision_at": AT,
                       "decision_sha256": "e" * 64, "node": NODE, "consent": True,
                       "device_sha256": self.request["device_sha256"], "receipt_sha256": self.ref}
        self.world = {"esquema": "preceptoros.openworld-estado/2",
                      "colonia": {"nodes": [{"id": NODE, "alive": True, "seal": "LIVE"}],
                                  "buildings": [{"id": "fixture", "node": NODE}]},
                      "cobertura": {"estado": "MEDIDO"}}

    def sign(self, body, namespace):
        target = self.home / "document"
        sig = target.with_suffix(".sig")
        sig.unlink(missing_ok=True)
        target.write_bytes(node_building._canonical(body))
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace,
                        "-f", str(self.key), str(target)], check=True)
        return {**body, "firma_ssh": sig.read_text()}

    def export_evidence(self, request_ref=None):
        plan = self.sign({"esquema": "preceptoros.plan-nodo/1", "accion": "crear_nodo", "id": "fixture",
                          "nodo": NODE, "admin_sha256": "c" * 64, "request_sha256": request_ref or self.ref},
                         "preceptoros-plan-nodo")
        plan["sha256"] = L._digest(plan)
        self.assertTrue(L._store(self.home, NODE, "plan", plan))
        card = self.sign({"esquema": "preceptoros.cedula-nodo/1", "nodo": NODE,
                          "admin": plan["admin_sha256"], "plan_sha256": plan["sha256"],
                          "dispositivos": [{"clave": self.request["device_sha256"], "estado": "linkeado"}]},
                         "preceptoros-cedula")
        card["sha256"] = L._digest(card)
        receipt = {"esquema": "preceptoros.recibo-cedula/1", "node_id": NODE,
                   "admin_sha256": card["admin"], "plan_sha256": plan["sha256"],
                   "credential_sha256": card["sha256"], "estado": "verificado",
                   "causa": None, "recibido": AT}
        receipt["recibo_sha256"] = L._digest(receipt)
        self.assertTrue(L.record_export(self.home, card, receipt))
        self.catalog = {"esquema": "preceptoros.catalogo-cedulas/1", "cedulas": [{
            "nodo": NODE, "estado": "verificado", "recibo_sha256": receipt["recibo_sha256"]}]}

    def fetch(self, url, headers, limit):
        if url == L.INTAKE_URL + "/" + self.ref:
            self.assertEqual(headers, {"X-Owner-Review-Key": TOKEN})
            return self.review
        self.assertEqual(headers, {})
        if url == L.CATALOG_URL:
            return self.catalog
        self.assertEqual(url, L.WORLD_URL)
        return self.world

    def read(self, fetch=None):
        return L.read(self.home, review_key_file=self.token, fetch=fetch or self.fetch, now=NOW)

    def test_pending_has_only_local_consent_and_pending_receipt_no_network(self):
        fetch = mock.Mock()
        result = L.read(self.home, fetch=fetch, now=NOW)
        self.assertEqual(result["stages"]["prepare"]["state"], "MEASURED")
        self.assertEqual(result["stages"]["consent"]["receipt_ref"], self.ref)
        self.assertEqual(result["stages"]["request"]["state"], "PENDING")
        for name in ("signature", "approval", "heartbeat", "live", "ai", "building"):
            self.assertEqual(result["stages"][name]["state"], "NO_DATA")
        fetch.assert_not_called()

    def test_bound_signed_evidence_and_current_aduana_live_projection(self):
        self.export_evidence()
        result = self.read()
        for name in ("signature", "approval", "live"):
            self.assertEqual(result["stages"][name]["state"], "MEASURED")
        for name in ("heartbeat", "ai", "building"):
            self.assertEqual(result["stages"][name]["state"], "NO_DATA")
        raw = json.dumps(result)
        for secret in (TOKEN, self.request["device_sha256"], self.request["nonce"], "BEGIN SSH SIGNATURE"):
            self.assertNotIn(secret, raw)

    def test_invalid_links_revocation_and_disappearance_fail_closed(self):
        self.export_evidence(request_ref="d" * 64)
        self.assertEqual(self.read()["stages"]["live"]["state"], "NO_DATA")
        self.export_evidence()
        self.review["state"] = "REVOKED"
        fetch = mock.Mock(wraps=self.fetch)
        stages = self.read(fetch)["stages"]
        self.assertEqual(stages["revoke"]["state"], "REVOKED")
        self.assertEqual(stages["live"]["state"], "NO_DATA")
        self.assertEqual(fetch.call_count, 1)
        self.review["state"] = "APPROVED"
        self.world["colonia"]["nodes"] = []
        self.assertEqual(self.read()["stages"]["live"]["cause"], "node_absent_from_aduana_live_projection")
        self.review["receipt_sha256"] = "d" * 64
        self.assertEqual(self.read()["stages"]["approval"]["state"], "NO_DATA")
