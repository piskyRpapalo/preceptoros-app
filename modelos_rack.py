"""Rack model catalog and one streamed conversation turn, for the APP's existing model picker.

The hosts are host-owned configuration (a private file named by PRECEPTOROS_MODEL_HOSTS_FILE), never a browser
value: loopback or tailnet (100.64.0.0/10) Ollama bases only, no redirects, no proxies. A model is listed as
READY only when its engine reports it loaded (/api/ps), AVAILABLE when installed (/api/tags), OFFLINE when its host
does not answer. Capabilities are what the engine declares (/api/show); `e2e` is set only by a completed
conversation turn through this module, never by a listing.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import time
import urllib.request
from urllib.parse import urlsplit

HOSTS_FILE_ENV = "PRECEPTOROS_MODEL_HOSTS_FILE"
DEFAULT_HOSTS_FILE = os.path.expanduser("~/.config/preceptoros/modelos_rack.json")
E2E_FILE_ENV = "PRECEPTOROS_MODEL_E2E_FILE"
DEFAULT_E2E_FILE = os.path.expanduser("~/.local/state/preceptoros/modelos_e2e.json")
HOST_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
MODEL_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,95}$")
TAILNET = ipaddress.ip_network("100.64.0.0/10")
PROBE_S = 3
FIRST_TOKEN_S = 180          # a cold model may need to load before its first token
MAX_TURNS = 12
MAX_TEXT_B = 4000
_SHOW_CACHE: dict = {}
_SHOW_TTL = 600


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open


def valid_base(base):
    try:
        p = urlsplit(base)
        if p.scheme != "http" or p.username or p.password or p.query or p.fragment or p.path not in ("", "/"):
            return False
        ip = ipaddress.ip_address(p.hostname or "")
        return (ip.is_loopback or ip in TAILNET) and p.port is not None and 1 <= p.port <= 65535
    except (ValueError, TypeError):
        return False


def hosts(path=None):
    """[(id, base)] from the host-owned file; anything malformed is dropped, never guessed."""
    try:
        with open(path or os.environ.get(HOSTS_FILE_ENV) or DEFAULT_HOSTS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for h in data.get("hosts", []) if isinstance(data, dict) else []:
        if (isinstance(h, dict) and isinstance(h.get("id"), str) and HOST_ID.match(h["id"])
                and isinstance(h.get("base"), str) and valid_base(h["base"])
                and h["id"] not in [x for x, _ in out]):
            out.append((h["id"], h["base"].rstrip("/")))
    return out[:16]


def _get(url, timeout=PROBE_S, body=None, opener=None):
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"Accept": "application/json", "Content-Type": "application/json"})
    with (opener or _OPEN)(req, timeout=timeout) as r:
        raw = r.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("response_too_large")
    return json.loads(raw.decode("utf-8"))


def _e2e(path=None):
    try:
        with open(path or os.environ.get(E2E_FILE_ENV) or DEFAULT_E2E_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_e2e(key, receipt, path=None):
    path = path or os.environ.get(E2E_FILE_ENV) or DEFAULT_E2E_FILE
    data = _e2e(path)
    data[key] = receipt
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, sort_keys=True)
    os.replace(tmp, path)


def _capabilities(base, name, opener=None, now=None):
    now = time.monotonic() if now is None else now
    hit = _SHOW_CACHE.get((base, name))
    if hit and now - hit[0] < _SHOW_TTL:
        return hit[1]
    try:
        caps = _get(base + "/api/show", body=json.dumps({"model": name}).encode(), opener=opener).get("capabilities")
        caps = sorted(c for c in caps if isinstance(c, str) and re.fullmatch(r"[a-z_]{1,24}", c)) \
            if isinstance(caps, list) else None
    except Exception:
        caps = None
    _SHOW_CACHE[(base, name)] = (now, caps)
    return caps


def catalog(path=None, e2e_path=None, opener=None):
    receipts = _e2e(e2e_path)
    models, devices = [], []
    for host, base in hosts(path):
        try:
            tags = _get(base + "/api/tags", opener=opener).get("models") or []
        except Exception:
            devices.append({"id": host, "state": "OFFLINE", "cause": "host_unreachable"})
            continue
        try:
            loaded = {m.get("name") for m in (_get(base + "/api/ps", opener=opener).get("models") or [])}
            ps_known = True
        except Exception:
            loaded, ps_known = set(), False
        devices.append({"id": host, "state": "ONLINE", "models": len(tags)})
        for m in tags:
            name = m.get("name") if isinstance(m, dict) else None
            if not isinstance(name, str) or not MODEL_NAME.match(name):
                continue
            details = m.get("details") if isinstance(m.get("details"), dict) else {}
            caps = _capabilities(base, name, opener=opener)
            key = host + "/" + name
            models.append({
                "key": key, "name": name, "device": host, "where": "RACK", "network": True,
                "size_gb": round(m["size"] / 1e9, 1) if isinstance(m.get("size"), int) else None,
                "parameters": details.get("parameter_size"), "quantization": details.get("quantization_level"),
                "state": ("READY" if name in loaded else "AVAILABLE") if ps_known else "NO_DATA",
                "capabilities": caps if caps is not None else "NO_DATA",
                "chat": bool(caps) and "completion" in caps and "embedding" not in caps,
                "voice": "ANDROID_TTS",
                "e2e": receipts.get(key) or None,
            })
    return {"schema": "preceptoros.modelos-rack/1", "devices": devices, "models": models,
            "local_android": {"state": "NO_DATA", "cause": "no_stable_android_native_inference"}}


def resolve(key, path=None):
    """(base, model) for a catalog key, or (None, cause). The browser names a key; the host decides the address."""
    if not isinstance(key, str) or "/" not in key:
        return None, "model_key_invalid"
    host, name = key.split("/", 1)
    if not HOST_ID.match(host) or not MODEL_NAME.match(name):
        return None, "model_key_invalid"
    base = dict(hosts(path)).get(host)
    return (base, name) if base else (None, "model_host_not_configured")


def messages(raw):
    """Bounded [{'role','content'}]: the last MAX_TURNS user/assistant turns, ending with the person's turn."""
    if not isinstance(raw, list) or not raw or len(raw) > 40:
        return None
    out = []
    for m in raw[-MAX_TURNS:]:
        if (not isinstance(m, dict) or m.get("role") not in ("user", "assistant")
                or not isinstance(m.get("content"), str) or not m["content"].strip()
                or len(m["content"].encode("utf-8")) > MAX_TEXT_B):
            return None
        out.append({"role": m["role"], "content": m["content"]})
    return out if out[-1]["role"] == "user" else None


def stream(base, name, msgs, emit, opener=None, clock=time.monotonic):
    """One streamed turn. `emit(event)` returns False when the client is gone; then the upstream is closed,
    which makes the engine stop generating. Events: loading, token, done, error."""
    started = clock()
    body = json.dumps({"model": name, "messages": msgs, "stream": True, "think": False,
                       "options": {"num_predict": 768}}).encode("utf-8")
    req = urllib.request.Request(base + "/api/chat", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"})
    if not emit({"e": "loading", "model": name}):
        return {"state": "CANCELLED"}
    first, text = None, []
    try:
        with (opener or _OPEN)(req, timeout=FIRST_TOKEN_S) as up:
            for line in up:
                chunk = json.loads(line.decode("utf-8"))
                if chunk.get("error"):
                    emit({"e": "error", "cause": "engine_error"})
                    return {"state": "NO_DATA", "cause": "engine_error"}
                if chunk.get("model") != name:
                    emit({"e": "error", "cause": "engine_model_unconfirmed"})
                    return {"state": "NO_DATA", "cause": "engine_model_unconfirmed"}
                piece = (chunk.get("message") or {}).get("content") or ""
                if piece:
                    if first is None:
                        first = clock()
                    text.append(piece)
                    if not emit({"e": "token", "t": piece}):
                        return {"state": "CANCELLED"}
                if chunk.get("done"):
                    if not text:
                        emit({"e": "error", "cause": "engine_returned_no_text"})
                        return {"state": "NO_DATA", "cause": "engine_returned_no_text"}
                    receipt = {"state": "MEASURED", "model": name,
                               "first_token_ms": round((first - started) * 1000) if first else None,
                               "total_ms": round(chunk["total_duration"] / 1e6) if isinstance(chunk.get("total_duration"), int) else None,
                               "load_ms": round(chunk["load_duration"] / 1e6) if isinstance(chunk.get("load_duration"), int) else None,
                               "tokens": chunk.get("eval_count") if isinstance(chunk.get("eval_count"), int) else None,
                               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                    emit(dict(receipt, e="done"))
                    return dict(receipt, text="".join(text))
    except Exception as exc:
        cause = "engine_timeout" if "timed out" in str(exc) else "engine_unreachable"
        emit({"e": "error", "cause": cause})
        return {"state": "NO_DATA", "cause": cause}
    emit({"e": "error", "cause": "engine_stream_truncated"})
    return {"state": "NO_DATA", "cause": "engine_stream_truncated"}
