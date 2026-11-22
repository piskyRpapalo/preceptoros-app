#!/usr/bin/env python3
"""oido.py · El oído de PreceptorOS.

Encapsula whisper.cpp para transcribir audio local. Sin red.

Doctrina:
- Si whisper-cli no existe o falla, oido.py devuelve None y PreceptorOS
  pide al usuario que escriba. Nunca bloquea la misión.
- El modelo tiny es el default (75MB). El usuario puede elegir base/small
  para mejor precisión.
"""
from __future__ import annotations

import subprocess
import os
import tempfile
from typing import Optional

import silencio as _silencio

WHISPER_CLI = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
WHISPER_MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-tiny.bin")


def oido_disponible() -> bool:
    """True si whisper-cli y el modelo existen y el microfono no esta vetado.

    El veto va PRIMERO y en esta funcion, que es la unica puerta: si estuviera
    en quien llama, bastaria un llamante nuevo para volver a abrir el
    microfono sin querer. Ver `silencio.py`.
    """
    if _silencio.apagado():
        return False
    return os.path.isfile(WHISPER_CLI) and os.path.isfile(WHISPER_MODEL)


def transcribir(ruta_wav: str, idioma: str = "es", *,
               cpu_only: bool = False, threads: int | None = None,
               timeout_sec: int = 60) -> Optional[str]:
    """Transcribe un WAV a texto. Devuelve None si falla."""
    if not oido_disponible():
        return None
    if threads is not None and (type(threads) is not int or not 1 <= threads <= 4):
        return None
    if type(timeout_sec) is not int or not 1 <= timeout_sec <= 60:
        return None
    args = [WHISPER_CLI, "-m", WHISPER_MODEL, "-f", ruta_wav,
            "--language", idioma, "--no-timestamps"]
    if cpu_only:
        args.append("--no-gpu")
        if threads is None:
            threads = 2
    if threads is not None:
        args.extend(["--threads", str(threads)])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec)
        if r.returncode != 0:
            return None
        # Extraer solo el texto (whisper-cli imprime líneas con timestamps)
        texto = ""
        for linea in r.stdout.split("\n"):
            linea = linea.strip()
            if linea and not linea.startswith("["):
                texto += linea + " "
        return texto.strip() or None
    except Exception:
        return None


def grabar_y_transcribir(duracion_seg: int = 5, idioma: str = "es") -> Optional[str]:
    """Graba del micrófono y transcribe. Devuelve None si falla.

    La comprobación va ANTES de grabar, y no la tenía: se abría `arecord`
    cinco segundos, se grababa la habitación, y sólo entonces `transcribir`
    miraba si whisper existía y devolvía None. Grabar a alguien para acabar
    tirando la grabación no es un desperdicio de tiempo: es abrirle el
    micrófono sin usarlo para nada, que es peor que no abrirlo.
    """
    if not oido_disponible():
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        ruta = tmp.name
    try:
        # Grabar con arecord
        subprocess.run(
            ["arecord", "-d", str(duracion_seg), "-r", "16000",
             "-c", "1", "-f", "S16_LE", ruta],
            capture_output=True, timeout=duracion_seg + 5
        )
        if not os.path.isfile(ruta) or os.path.getsize(ruta) < 1000:
            return None
        return transcribir(ruta, idioma)
    except Exception:
        return None
    finally:
        if os.path.isfile(ruta):
            os.unlink(ruta)


if __name__ == "__main__":
    if oido_disponible():
        print(f"✓ OÍDO disponible: {WHISPER_CLI}")
        print(f"  Modelo: {WHISPER_MODEL}")
    else:
        print("✗ OÍDO no disponible. Preceptor pedirá texto.")
