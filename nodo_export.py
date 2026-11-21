"""Explicit, human-triggered export of an already signed node credential."""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request

import nodo_app

# Ruling of the Sovereign (buzon#30, 2026-10-25): the registration route is /api/v1/cedulas.
ENDPOINT = "https://api.preceptoros.org/api/v1/cedulas"
ESTADOS_ADUANA = {"pendiente", "verificado"}
TIMEOUT_S = 15
MAX_RESPONSE = 1024 * 1024
CAUSAS_ADUANA = {
    "clave_publica_no_configurada", "plan_firmado_no_configurado",
    "plan_no_coincide", "firma_cedula_rechazada", "cedula_mal_formada",
    "registro_no_disponible", "cuerpo_invalido", "cuerpo_fuera_de_rango",
    "hash_no_coincide", "plan_firmado_invalido", "plan_firmado_rechazado",
}


def _rechazo(codigo: str, http: int = 409) -> dict:
    return {"estado": "bloqueado", "codigo": codigo, "http": http}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _recibo_corresponde(cedula, respuesta):
    """Bind to the serialized request; hash integrity is not an admission grant."""
    recibo = respuesta.get("recibo")
    if not isinstance(recibo, dict):
        return False
    expected = {"credential_sha256": cedula["sha256"], "node_id": cedula["nodo"],
                "admin_sha256": cedula.get("admin"), "plan_sha256": cedula.get("plan_sha256")}
    if (recibo.get("esquema") != "preceptoros.recibo-cedula/1"
            or any(recibo.get(k) != v for k, v in expected.items())
            or respuesta.get("estado") != recibo.get("estado")
            or respuesta.get("causa") != recibo.get("causa")
            or type(respuesta.get("recibidos")) is not int
            or respuesta["recibidos"] != 1):
        return False
    base = {k: v for k, v in recibo.items() if k != "recibo_sha256"}
    try:
        def encoded(value):
            return json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True, allow_nan=False).encode("utf-8")
        # Python equality aliases True and 1; compare exact JSON values instead.
        if encoded(respuesta["paquete"]["pares"]) != encoded([cedula]):
            return False
        return recibo.get("recibo_sha256") == hashlib.sha256(encoded(base)).hexdigest()
    except (TypeError, ValueError):
        return False


def enviar(datos, *, transport=None, signers=None, include_receipt=False) -> dict:
    """Validate and forward one signed credential; never create a signature.

    The only network path is called by the explicit POST route. Tests inject a
    transport, so the live endpoint is never contacted by the test suite.
    """
    if not isinstance(datos, dict) or set(datos) != {"cedula"}:
        return _rechazo("cuerpo_invalido", 400)
    cedula = datos.get("cedula")
    forma = nodo_app._forma(cedula)
    if forma:
        return _rechazo("cedula_rechazada", 422)
    try:
        estado, _causa = nodo_app.autenticidad(cedula, signers=signers)
    except (OSError, subprocess.SubprocessError):
        return _rechazo("firma_no_disponible", 503)
    if estado == "NO_DATA":
        return _rechazo("firma_no_disponible", 503)
    if estado != "OK":
        return _rechazo("firma_rechazada", 422)

    cuerpo = json.dumps({"cedula": cedula}, ensure_ascii=False,
                        sort_keys=True, separators=(",", ":")).encode("utf-8")
    # Compare the response with bytes already sent, not mutable caller data.
    enviada = json.loads(cuerpo)["cedula"]
    if transport is None:
        req = urllib.request.Request(
            ENDPOINT, data=cuerpo,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(req, timeout=TIMEOUT_S) as resp:
                if resp.status < 200 or resp.status >= 300:
                    return _rechazo("aduana_rechazo", 502)
                raw = resp.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    return _rechazo("recibo_invalido", 502)
                respuesta = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                with exc:
                    fallo = json.loads(exc.read(4097).decode("utf-8"))
                codigo = fallo.get("codigo") if isinstance(fallo, dict) else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                codigo = None
            return _rechazo(codigo, 409) if codigo in CAUSAS_ADUANA else _rechazo("aduana_rechazo", 502)
        except (urllib.error.URLError, TimeoutError, OSError):
            return _rechazo("aduana_no_disponible", 502)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _rechazo("recibo_invalido", 502)
    else:
        try:
            respuesta = transport(ENDPOINT, cuerpo)
        except Exception:
            return _rechazo("aduana_no_disponible", 502)

    if not isinstance(respuesta, dict):
        return _rechazo("recibo_invalido", 502)
    paquete = respuesta.get("paquete")
    if (not isinstance(paquete, dict)
            or paquete.get("esquema") != "preceptoros/cedula-nodo/1"
            or paquete.get("firma", "missing") is not None
            or not isinstance(paquete.get("pares"), list)
            or len(paquete["pares"]) != 1):
        return _rechazo("paquete_invalido", 502)
    # The aduana answers pendiente (no verifiable anchor) or verificado. The exporter repeats
    # that state and its cause as they are; it never upgrades a pending cedula to trusted.
    if respuesta.get("estado") not in ESTADOS_ADUANA:
        return _rechazo("recibo_invalido", 502)
    if not _recibo_corresponde(enviada, respuesta):
        return _rechazo("recibo_no_corresponde", 502)
    result = {"estado": respuesta["estado"], "codigo": "recibido",
              "causa": respuesta.get("causa"), "recibidos": respuesta.get("recibidos")}
    if include_receipt:
        receipt = respuesta["recibo"]
        fields = ("esquema", "credential_sha256", "node_id", "admin_sha256",
                  "plan_sha256", "estado", "causa", "recibido", "recibo_sha256")
        if set(receipt) != set(fields):
            return _rechazo("recibo_invalido", 502)
        result["recibo"] = {field: receipt[field] for field in fields}
    return result
