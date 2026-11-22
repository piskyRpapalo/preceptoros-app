"""HEX-NODE3: three admitted identities stay independent in the OWNER lifecycle.

Fixture names only. No real node, key, cell or Aduana request is used or created.
Each node has its own APP home and its own owner key, as Aduana scoped plans (#41) do.
"""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import json
import subprocess

import node_building
import node_lifecycle as L

NOW = datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc)
AT = "2026-11-22T18:59:55Z"
TOKEN = "r" * 40
# Fixture cédula IDs. The real ones need the Sovereign's word (HITL); none is invented here.
NODES = ("nodo.901.fixture-host", "nodo.902.fixture-client-a", "nodo.903.fixture-client-b")
PUBLIC_ALIAS = "fixture-anchor"


class Node:
    """One device: its own home, owner key, consented intake and signed export."""

    def __init__(self, root, node, index):
        self.node = node
        self.home = Path(root) / node
        self.home.mkdir()
        node_building.provisionar_identidad(self.home, node)
        self.key = self.home / "owner-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        self.signers = self.home / "allowed_signers_cedula"
        # The APP verifies principal "soberano" (nodo_app.py); isolation comes from one signers file per home.
        self.signers.write_text("soberano " + self.key.with_suffix(".pub").read_text())
        self.token = self.home / "review-token"
        self.token.write_text(TOKEN)
        self.token.chmod(0o600)
        self.request = {"schema": "preceptoros.deployment-request/1", "node": node, "consent": True,
                        "nonce": "abc"[index - 1] * 32, "device_sha256": "def"[index - 1] * 64}
        self.ref = L._digest(self.request)
        intake = {"schema": "preceptoros.deployment-request-receipt/1", "request_id": self.ref,
                  "state": "AWAITING_HUMAN", "received_at": AT}
        assert L.record_intake(self.home, self.request, intake)
        self.review = {**intake, "state": "APPROVED", "decision_at": AT, "decision_sha256": f"{index}" * 64,
                       "node": node, "consent": True, "device_sha256": self.request["device_sha256"],
                       "receipt_sha256": self.ref}
        self.receipt = self._export()

    def _sign(self, body, namespace):
        target = self.home / "document"
        sig = target.with_suffix(".sig")
        sig.unlink(missing_ok=True)
        target.write_bytes(node_building._canonical(body))
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", str(self.key), str(target)],
                       check=True)
        return {**body, "firma_ssh": sig.read_text()}

    def _export(self):
        plan = self._sign({"esquema": "preceptoros.plan-nodo/1", "accion": "crear_nodo", "id": self.node,
                           "nodo": self.node, "admin_sha256": "c" * 64, "request_sha256": self.ref},
                          "preceptoros-plan-nodo")
        plan["sha256"] = L._digest(plan)
        assert L._store(self.home, self.node, "plan", plan)
        card = self._sign({"esquema": "preceptoros.cedula-nodo/1", "nodo": self.node,
                           "admin": plan["admin_sha256"], "plan_sha256": plan["sha256"],
                           "dispositivos": [{"clave": self.request["device_sha256"], "estado": "linkeado"}]},
                          "preceptoros-cedula")
        card["sha256"] = L._digest(card)
        receipt = {"esquema": "preceptoros.recibo-cedula/1", "node_id": self.node,
                   "admin_sha256": card["admin"], "plan_sha256": plan["sha256"],
                   "credential_sha256": card["sha256"], "estado": "verificado", "causa": None, "recibido": AT}
        receipt["recibo_sha256"] = L._digest(receipt)
        assert L.record_export(self.home, card, receipt)
        return receipt


class ThreeIdentities(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.nodes = [Node(tmp.name, node, i + 1) for i, node in enumerate(NODES)]
        self.catalog = {"esquema": "preceptoros.catalogo-cedulas/1", "cedulas": [
            {"nodo": n.node, "estado": "verificado", "recibo_sha256": n.receipt["recibo_sha256"]}
            for n in self.nodes]}
        self.world = {"esquema": "preceptoros.openworld-estado/2", "cobertura": {"estado": "MEDIDO"},
                      "colonia": {"nodes": [{"id": n.node, "alive": True, "seal": "LIVE"} for n in self.nodes]
                                  + [{"id": PUBLIC_ALIAS, "alive": True, "seal": "LIVE"}], "buildings": []}}
        self.reviews = {n.ref: n.review for n in self.nodes}

    def fetch(self, url, headers, limit):
        if url.startswith(L.INTAKE_URL + "/"):
            self.assertEqual(headers, {"X-Owner-Review-Key": TOKEN})
            return self.reviews[url.rsplit("/", 1)[1]]
        self.assertEqual(headers, {})
        return self.catalog if url == L.CATALOG_URL else self.world

    def read(self, node):
        return L.read(node.home, review_key_file=node.token, signers=node.signers, fetch=self.fetch, now=NOW)

    def states(self, stage):
        return [self.read(n)["stages"][stage]["state"] for n in self.nodes]

    def test_three_distinct_identities_each_reach_live_on_their_own_evidence(self):
        results = [self.read(n) for n in self.nodes]
        self.assertEqual([r["node"] for r in results], list(NODES))
        for result in results:
            for name in ("prepare", "signature", "approval", "live"):
                self.assertEqual(result["stages"][name]["state"], "MEASURED", name)
            # The public projection never carries an exact heartbeat receipt.
            self.assertEqual(result["stages"]["heartbeat"]["state"], "NO_DATA")
        refs = {r["stages"]["signature"]["receipt_ref"] for r in results}
        self.assertEqual(len(refs), 3)

    def test_revoking_one_node_leaves_the_other_two_untouched(self):
        self.nodes[1].review["state"] = "REVOKED"
        self.assertEqual(self.states("revoke"), ["PENDING", "REVOKED", "PENDING"])
        self.assertEqual(self.states("live"), ["MEASURED", "NO_DATA", "MEASURED"])

    def test_expiry_of_one_heartbeat_withdraws_only_that_node(self):
        # Aduana drops a node from the projection once its heartbeat expires (#39).
        self.world["colonia"]["nodes"] = [r for r in self.world["colonia"]["nodes"] if r["id"] != NODES[2]]
        self.assertEqual(self.states("live"), ["MEASURED", "MEASURED", "NO_DATA"])
        self.assertEqual(self.read(self.nodes[2])["stages"]["live"]["cause"],
                         "node_absent_from_aduana_live_projection")

    def test_another_nodes_catalog_receipt_never_admits(self):
        self.catalog["cedulas"][1]["recibo_sha256"] = self.nodes[0].receipt["recibo_sha256"]
        self.assertEqual(self.states("live"), ["MEASURED", "NO_DATA", "MEASURED"])
        self.assertEqual(self.read(self.nodes[1])["stages"]["live"]["cause"],
                         "admission_receipt_absent_from_aduana_catalog")

    def test_one_owner_key_cannot_sign_for_another_node(self):
        # Node B trusts only its own owner; node A's key is a foreign signer there.
        self.nodes[1].signers.write_text(self.nodes[0].signers.read_text())
        self.assertEqual(self.states("signature"), ["MEASURED", "NO_DATA", "MEASURED"])
        self.assertEqual(self.states("live"), ["MEASURED", "NO_DATA", "MEASURED"])

    def test_public_alias_is_never_promoted_to_admission_even_when_live(self):
        with TemporaryDirectory() as tmp:
            node_building.provisionar_identidad(tmp, PUBLIC_ALIAS)
            fetch = mock.Mock(wraps=self.fetch)
            result = L.read(tmp, review_key_file=self.nodes[0].token, fetch=fetch, now=NOW)
        self.assertIsNone(result["node"])
        self.assertEqual(result["stages"]["prepare"]["cause"], "local_identity_not_cedula_namespace")
        self.assertTrue(all(s["state"] == "NO_DATA" for s in result["stages"].values()))
        fetch.assert_not_called()

    def test_no_secret_or_device_claim_leaves_any_projection(self):
        raw = json.dumps([self.read(n) for n in self.nodes])
        for n in self.nodes:
            for secret in (TOKEN, n.request["device_sha256"], n.request["nonce"]):
                self.assertNotIn(secret, raw)
        self.assertNotIn("BEGIN SSH SIGNATURE", raw)
