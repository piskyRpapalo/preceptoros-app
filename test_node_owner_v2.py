"""HEX-NODE3 v2 from the APP: request with owner material, admission and heartbeat key, no SSH knowledge."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import hashlib
import json
import stat

import node_building
import node_lifecycle as L
import node_owner
import node_registration as R

NODE = "nodo.906.fixture-v2"


class Wire:
    """Records what would leave the device and answers like Aduana."""

    def __init__(self):
        self.sent = []
        self.replies = []

    def __call__(self, url, body, headers, timeout):
        self.sent.append((url, json.loads(body)))
        status, reply = self.replies.pop(0)
        return status, json.dumps(reply).encode(), url


def receipt_reply(cedula, estado="verificado"):
    recibo = {"esquema": "preceptoros.recibo-cedula/1", "credential_sha256": cedula["sha256"], "node_id": cedula["nodo"],
              "admin_sha256": cedula["admin"], "plan_sha256": cedula["plan_sha256"], "estado": estado, "causa": None,
              "recibido": "2026-11-22T21:00:00Z"}
    enc = json.dumps(recibo, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    recibo["recibo_sha256"] = hashlib.sha256(enc).hexdigest()
    return {"recibo": recibo, "estado": estado, "causa": None, "recibidos": 1, "paquete": {"pares": [cedula]}}


class V2(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "app"
        self.home.mkdir(mode=0o700)
        node_building.provisionar_identidad(self.home, NODE)

    def request(self, wire, **extra):
        data = {"esquema": R.PWA_INTAKE_SCHEMA_V2, "node": NODE, "nonce": "a" * 32, "consent": True,
                "alias": "fixture-v2", "roles": ["APP_CLIENT"], **extra}
        return R.submit_preliminary(self.home, data, post=wire)

    def intake_reply(self, wire):
        def answer(url, body, headers, timeout):
            ref = hashlib.sha256(body).hexdigest()
            wire.sent.append((url, json.loads(body)))
            return 202, json.dumps({"schema": R.INTAKE_RECEIPT, "request_id": ref, "state": "AWAITING_HUMAN",
                                    "received_at": "2026-11-22T21:00:00Z", "authority": "NONE",
                                    "credential": "NOT_PROVISIONED", "live": "NO_DATA(heartbeat_not_verified)",
                                    "owner_alert": "NO_DATA(recipient_notification_not_verified)",
                                    "notification": "QUEUED"}).encode(), url
        return answer

    def test_v2_request_carries_only_public_owner_material(self):
        wire = Wire()
        code, out = self.request(self.intake_reply(wire))
        self.assertEqual(code, 202, out)
        url, body = wire.sent[0]
        self.assertEqual(body["schema"], "preceptoros.deployment-request/2")
        self.assertRegex(body["owner_public_key"], r"^ssh-ed25519 [A-Za-z0-9+/]{68}$")
        self.assertEqual((body["alias"], body["offer"]), ("fixture-v2", {"roles": ["APP_CLIENT"]}))
        private = (self.home / "node-owner" / "owner_ed25519").read_text()
        self.assertNotIn(private.splitlines()[1], json.dumps(body))
        self.assertEqual(L._load(self.home, NODE, "intake")["request"]["schema"], "preceptoros.deployment-request/2")

    def test_v2_rejects_bad_alias_or_roles_before_any_network(self):
        wire = Wire()
        for extra in ({"alias": "nodo.1.x"}, {"alias": "Bad Alias"}, {"roles": []}, {"roles": ["ROOT"]},
                      {"roles": ["APP_CLIENT", "APP_CLIENT"]}):
            self.assertEqual(self.request(wire, **extra)[0], 422, extra)
        self.assertEqual(wire.sent, [])

    def test_admission_pending_then_verified_and_bound(self):
        self.request(self.intake_reply(Wire()))
        wire = Wire()
        wire.replies.append((409, {"codigo": "prior_human_approval_required"}))
        self.assertEqual(node_owner.submit_admission(self.home, NODE, post=wire)["state"], "PENDING")
        url, body = wire.sent[0]
        self.assertEqual(url, node_owner.CEDULAS_URL)
        self.assertEqual(set(body), {"cedula", "plan"})
        wire.replies.append((202, receipt_reply(body["cedula"])))
        out = node_owner.submit_admission(self.home, NODE, post=wire)
        self.assertEqual(out["state"], "MEASURED")
        self.assertTrue(out["lifecycle_recorded"])
        self.assertEqual(L.read(self.home)["stages"]["signature"]["state"], "MEASURED")

    def test_admission_refuses_a_receipt_for_something_else(self):
        self.request(self.intake_reply(Wire()))
        wire = Wire()
        bogus = {"esquema": "preceptoros.cedula-nodo/1", "nodo": NODE, "admin": "0" * 64, "plan_sha256": "1" * 64,
                 "sha256": "2" * 64, "dispositivos": []}
        wire.replies.append((202, receipt_reply(bogus)))
        self.assertEqual(node_owner.submit_admission(self.home, NODE, post=wire)["state"], "NO_DATA")

    def test_heartbeat_key_is_born_here_and_only_switches_after_registration(self):
        wire = Wire()
        wire.replies.append((403, {"codigo": "human_admission_not_verified"}))
        out = node_owner.heartbeat_key(self.home, "fixture-v2", post=wire)
        self.assertEqual(out, {"state": "NO_DATA", "cause": "human_admission_not_verified"})
        key_file = self.home / "node-owner" / node_owner.HEARTBEAT_KEY
        self.assertFalse(key_file.exists())
        wire.replies.append((202, {"estado": "registrada", "nodo": "fixture-v2"}))
        self.assertEqual(node_owner.heartbeat_key(self.home, "fixture-v2", post=wire)["state"], "MEASURED")
        self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
        key = key_file.read_text().strip()
        sent = wire.sent[-1][1]
        self.assertEqual(sent["sha256"], hashlib.sha256(key.encode()).hexdigest())
        self.assertNotIn(key, json.dumps(wire.sent))
        self.assertIn("BEGIN SSH SIGNATURE", sent["firma_ssh"])

    def test_v1_request_is_unchanged(self):
        wire = Wire()
        code, _ = R.submit_preliminary(self.home, {"esquema": R.PWA_INTAKE_SCHEMA, "node": NODE, "nonce": "b" * 32,
                                                   "consent": True}, post=self.intake_reply(wire))
        self.assertEqual(code, 202)
        self.assertEqual(set(wire.sent[0][1]), {"schema", "node", "nonce", "device_sha256", "consent"})
        self.assertFalse((self.home / "node-owner").exists())


class Routes(TestCase):
    """The two loopback routes: owner origin only, explicit consent, identity required."""

    def call(self, path, datos, headers, home):
        from types import SimpleNamespace
        from unittest import mock
        from test_agent_voice import _load_pwa
        pwa = _load_pwa()
        h = pwa.PWA.__new__(pwa.PWA)
        h.path = path
        h.headers = {"Host": "127.0.0.1:8742", "Content-Type": "application/json",
                     "Content-Length": str(len(json.dumps(datos))), **headers}
        h.server = SimpleNamespace(server_port=8742)
        h.client_address = ("127.0.0.1", 1234)
        h._json = lambda code, body: (code, body)
        h._leer = lambda: datos
        h._tailnet_proxy_request = lambda: False
        with mock.patch.object(pwa._casa, "raiz", return_value=home), \
             mock.patch.object(node_owner, "submit_admission", return_value={"state": "PENDING", "cause": "x"}) as sub, \
             mock.patch.object(node_owner, "heartbeat_key", return_value={"state": "MEASURED", "cause": "y"}) as hk:
            code, body = h._despachar_post()
        return code, body, sub.call_count + hk.call_count

    def test_routes_need_owner_origin_consent_and_identity(self):
        own = {"Origin": "http://127.0.0.1:8742"}
        ok_adm = {"esquema": "preceptoros.pwa-node-admission/1", "confirm": True}
        ok_key = {"esquema": "preceptoros.pwa-node-heartbeat-key/1", "alias": "fixture-v2"}
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(self.call("/api/nodo/admission", ok_adm, own, home)[0], 422)  # no identity yet
            node_building.provisionar_identidad(home, NODE)
            for path, datos, headers, status, calls in (
                ("/api/nodo/admission", ok_adm, {}, 403, 0),
                ("/api/nodo/admission", ok_adm, {"Origin": "https://preceptoros.org"}, 403, 0),
                ("/api/nodo/admission", ok_adm, {**own, "X-Forwarded-For": "192.0.2.1"}, 403, 0),
                ("/api/nodo/admission", {**ok_adm, "confirm": False}, own, 422, 0),
                ("/api/nodo/admission", ok_adm, own, 200, 1),
                ("/api/nodo/heartbeat-key", {"esquema": "preceptoros.pwa-node-heartbeat-key/1"}, own, 422, 0),
                ("/api/nodo/heartbeat-key", ok_key, own, 200, 1),
            ):
                with self.subTest(path=path, headers=headers, datos=datos):
                    code, _body, n = self.call(path, datos, headers, home)
                    self.assertEqual((code, n), (status, calls))
