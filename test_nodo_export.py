from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import nodo_export


def cedula():
    c = {
        "esquema": "preceptoros.cedula-nodo/1",
        "nodo": "nodo.1.prueba",
        "admin": "a1" * 32,
        "plan_sha256": "c1" * 32,
        "dispositivos": [{"clave": "b2" * 32, "estado": "solicitado"}],
        "firma_ssh": "firma-de-prueba",
        "autenticidad": "NO_DATA · pendiente de verificación local",
    }
    c["sha256"] = hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return c


def receipt_hash(receipt):
    base = {k: v for k, v in receipt.items() if k != "recibo_sha256"}
    return hashlib.sha256(json.dumps(base, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def reseal(card):
    card = deepcopy(card)
    card["sha256"] = hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!="sha256"},
                                             sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return card


def receipt_fixture(c, state="pendiente"):
    base = {"esquema": "preceptoros.recibo-cedula/1", "credential_sha256": c["sha256"],
            "node_id": c["nodo"], "admin_sha256": c["admin"], "plan_sha256": c["plan_sha256"],
            "estado": state, "causa": "ancla_ausente" if state == "pendiente" else None, "recibido": "2026-11-14T12:00:00.000Z"}
    base["recibo_sha256"] = receipt_hash(base)
    return {"estado": state, "causa": base["causa"], "recibidos": 1, "recibo": base,
            "paquete": {"esquema": "preceptoros/cedula-nodo/1", "pares": [c], "firma": None}}


class PwaSignedExport(unittest.TestCase):
    def response(self, payload, *, origin="http://127.0.0.1:8742", extra_headers=None):
        import io
        from types import SimpleNamespace
        from test_agent_voice import _load_pwa

        app = _load_pwa()
        handler = app.PWA.__new__(app.PWA)
        body = json.dumps(payload).encode()
        handler.path = "/api/nodo/export"
        handler.headers = {"Host": "127.0.0.1:8742", "Origin": origin,
                           "Content-Type": "application/json", "Content-Length": str(len(body)),
                           **(extra_headers or {})}
        handler.client_address = ("127.0.0.1", 5432)
        handler.server = SimpleNamespace(server_port=8742)
        handler.rfile = io.BytesIO(body)
        observed = {}
        handler._json = lambda code, body: observed.update(code=code, body=body)
        handler.do_POST()
        return observed, handler.rfile.tell()

    def test_visitor_and_proxy_rejected_before_body_or_export(self):
        with patch.object(nodo_export, "enviar") as export:
            for options in ({"origin": "https://preceptoros.org"},
                            {"extra_headers": {"X-Forwarded-Proto": "https"}}):
                reply, read = self.response({"cedula": cedula()}, **options)
                self.assertEqual((reply["code"], read), (403, 0))
            export.assert_not_called()

    def test_owner_returns_only_bound_aduana_receipt_with_state_http(self):
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        if not shutil.which("ssh-keygen"):
            self.skipTest("OpenSSH unavailable")
        actual = nodo_export.enviar
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key, body, anchors = (root / name for name in ("key", "body", "anchors"))
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
            anchors.write_text("soberano " + key.with_suffix(".pub").read_text())
            card = cedula()
            body.write_bytes(nodo_export.nodo_app.cuerpo_firmado(card))
            subprocess.run(["ssh-keygen", "-Y", "sign", "-n", "preceptoros-cedula",
                            "-f", str(key), str(body)], check=True, capture_output=True)
            card["firma_ssh"] = body.with_suffix(".sig").read_text()
            card = reseal(card)
            for state, status in (("pendiente", 202), ("verificado", 200)):
                remote_receipt = receipt_fixture(card, state)
                with patch.object(nodo_export, "enviar", side_effect=lambda data, **kwargs:
                        actual(data, signers=anchors, transport=lambda *_: remote_receipt, **kwargs)):
                    reply, _ = self.response({"cedula": card})
                self.assertEqual(reply["code"], status)
                self.assertEqual(reply["body"]["recibo"], remote_receipt["recibo"])
                self.assertNotIn("paquete", reply["body"])
                self.assertNotIn("live", reply["body"])


class ExportacionNodo(unittest.TestCase):
    def test_foreign_credential_receipt_is_rejected(self):
        other = cedula(); other["nodo"] = "nodo.2.other"
        other["sha256"] = "d1" * 32
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "TEST gate")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=lambda *_: receipt_fixture(other))
        self.assertEqual(r["codigo"], "recibo_no_corresponde")

    def test_corrupt_receipt_hash_is_rejected(self):
        answer = receipt_fixture(cedula()); answer["recibo"]["recibo_sha256"] = "00" * 32
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "TEST gate")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=lambda *_: answer)
        self.assertEqual(r["codigo"], "recibo_no_corresponde")

    def send_reply(self, card, answer):
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "TEST local gate")):
            return nodo_export.enviar({"cedula":card}, transport=lambda *_:deepcopy(answer))

    def test_verified_foreign_receipt_never_becomes_success(self):
        card = cedula()
        foreign = reseal(dict(card, nodo="nodo.2.other"))
        self.assertEqual(self.send_reply(card,receipt_fixture(foreign,"verificado"))["codigo"],
                         "recibo_no_corresponde")

    def test_binding_fields_cannot_be_rewritten_even_with_valid_receipt_hash(self):
        for field,value in (("credential_sha256","d1"*32),("node_id","nodo.2.other"),
                            ("admin_sha256","e1"*32),("plan_sha256","f1"*32)):
            with self.subTest(field=field):
                answer=receipt_fixture(cedula(),"verificado")
                answer["recibo"][field]=value
                answer["recibo"]["recibo_sha256"]=receipt_hash(answer["recibo"])
                self.assertEqual(self.send_reply(cedula(),answer)["codigo"],"recibo_no_corresponde")

    def test_missing_receipt_fails_closed(self):
        for receipt in (None, [], "not-a-receipt", {}):
            with self.subTest(receipt_type=type(receipt).__name__):
                answer=receipt_fixture(cedula());answer["recibo"]=receipt
                self.assertEqual(self.send_reply(cedula(),answer)["codigo"],"recibo_no_corresponde")

    def test_receipt_schema_and_envelope_must_agree(self):
        for field,value in (("estado","verificado"),("causa",None),("recibidos",True),
                            ("recibidos",1.0),("recibidos",2)):
            with self.subTest(field=field,value=value):
                answer=receipt_fixture(cedula());answer[field]=value
                self.assertEqual(self.send_reply(cedula(),answer)["codigo"],"recibo_no_corresponde")
        answer=receipt_fixture(cedula());answer["recibo"]["esquema"]="other/1"
        answer["recibo"]["recibo_sha256"]=receipt_hash(answer["recibo"])
        self.assertEqual(self.send_reply(cedula(),answer)["codigo"],"recibo_no_corresponde")

    def test_echoed_package_must_match_entire_sent_credential(self):
        answer=receipt_fixture(cedula())
        answer["paquete"]["pares"][0]["dispositivos"]=[]
        self.assertEqual(self.send_reply(cedula(),answer)["codigo"],"recibo_no_corresponde")

    def test_exact_json_comparison_does_not_alias_bool_and_int(self):
        card=reseal(dict(cedula(),synthetic_counter=1))
        answer=receipt_fixture(card)
        answer["paquete"]["pares"][0]=dict(card,synthetic_counter=True)
        self.assertEqual(self.send_reply(card,answer)["codigo"],"recibo_no_corresponde")

    def test_caller_mutation_during_transport_does_not_change_request_identity(self):
        card=cedula();original=deepcopy(card)
        foreign=reseal(dict(card,nodo="nodo.2.other"))
        def transport(_url,body):
            self.assertEqual(json.loads(body)["cedula"],original)
            card.clear();card.update(foreign)
            return receipt_fixture(foreign,"verificado")
        with patch("nodo_export.nodo_app.autenticidad",return_value=("OK","TEST local gate")):
            result=nodo_export.enviar({"cedula":card},transport=transport)
        self.assertEqual(result["codigo"],"recibo_no_corresponde")

    def test_reordered_and_unicode_json_preserves_correlation(self):
        card=reseal(dict(cedula(),synthetic_label="café"))
        answer=receipt_fixture(card,"verificado")
        answer["paquete"]["pares"][0]=dict(reversed(list(card.items())))
        self.assertEqual(self.send_reply(card,answer)["estado"],"verificado")

    def test_repeated_receipt_repeats_document_state_without_new_authority(self):
        card=cedula();answer=receipt_fixture(card,"verificado")
        first=self.send_reply(card,answer);again=self.send_reply(card,answer)
        self.assertEqual(first,again)
        self.assertEqual(set(first),{"estado","codigo","causa","recibidos"})
        self.assertEqual(first["estado"],"verificado")
        # No admission, territory, signature, capability grant or receipt minted.
        self.assertEqual(first,{"estado":"verificado","codigo":"recibido","causa":None,"recibidos":1})

    def test_forma_invalida_se_rechaza_sin_red(self):
        llamada = []
        r = nodo_export.enviar({"cedula": {"esquema": "otro"}}, transport=lambda *a: llamada.append(a))
        self.assertEqual((r["estado"], r["codigo"], r["http"]), ("bloqueado", "cedula_rechazada", 422))
        self.assertEqual(llamada, [])

    def test_firma_ausente_no_abre_la_red(self):
        llamada = []
        with patch("nodo_export.nodo_app.autenticidad", return_value=("NO_DATA", "firma no disponible")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=lambda *a: llamada.append(a))
        self.assertEqual(r["codigo"], "firma_no_disponible")
        self.assertEqual(r["http"], 503)
        self.assertEqual(llamada, [])

    def test_envio_solo_con_firma_validada_y_paquete_sin_firma_de_silicio(self):
        recibida = []
        def transport(url, body):
            recibida.append((url, json.loads(body)))
            return receipt_fixture(cedula())
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "verificada")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=transport)
        self.assertEqual(r, {"estado": "pendiente", "codigo": "recibido", "causa": "ancla_ausente", "recibidos": 1})
        self.assertEqual(recibida[0][0], nodo_export.ENDPOINT)
        self.assertTrue(nodo_export.ENDPOINT.endswith("/api/v1/cedulas"))
        self.assertEqual(recibida[0][1], {"cedula": cedula()})

    def test_un_estado_desconocido_no_se_repite_como_recibido(self):
        paquete = {"esquema": "preceptoros/cedula-nodo/1", "pares": [cedula()], "firma": None}
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "verificada")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=lambda *_: {
                "estado": "confiable", "recibidos": 1, "paquete": paquete})
        self.assertEqual(r["codigo"], "recibo_invalido")

    def test_silicio_no_puede_devolver_paquete_firmado(self):
        with patch("nodo_export.nodo_app.autenticidad", return_value=("OK", "verificada")):
            r = nodo_export.enviar({"cedula": cedula()}, transport=lambda *_: {
                "recibidos": 1, "paquete": {"esquema": "preceptoros/cedula-nodo/1", "pares": [cedula()], "firma": "inventada"}})
        self.assertEqual(r["codigo"], "paquete_invalido")


if __name__ == "__main__":
    unittest.main()
