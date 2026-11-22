"""B-04: zero-network, thermal-guarded STT using existing oido.py.

The browser owns microphone permission, captures a short PCM16 WAV on user
gesture and stops its tracks on STOP. The existing PWA route must check its
loopback same-origin guard before handing audio to this module. No host mic
capture, remote ASR, autonomous tool call, long-lived audio file or background
inference is permitted here. Import is inert.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import wave

import oido
import silencio

MAX_BEELINK_TCTL_C = 75.0
MAX_WAV_BYTES = 161024
MAX_TRANSCRIPT_BYTES = 650
MAX_ENVELOPE_BYTES = 1023
COMMAND = "transcribe_es_pcm16_v1"
_LOCK = threading.Lock()


class STTUnavailable(ValueError):
    """Typed, closed, non-sensitive failure reason."""


def _temperature_c() -> float:
    for name in Path("/sys/class/hwmon").glob("hwmon*/name"):
        try:
            if name.read_text(encoding="utf-8").strip() != "k10temp":
                continue
            value = float((name.parent / "temp1_input").read_text().strip()) / 1000
            if not 0 < value < 140:
                break
            return value
        except (OSError, ValueError):
            break
    raise STTUnavailable("cpu_thermal_sensor_unavailable")


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _validate_wav(data: bytes) -> tuple[int, str]:
    if not isinstance(data, bytes) or not 44 <= len(data) <= MAX_WAV_BYTES:
        raise STTUnavailable("local_wav_bytes_out_of_range")
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise STTUnavailable("local_wav_header_invalid")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            frames = w.getnframes()
            if (w.getnchannels() != 1 or w.getsampwidth() != 2
                    or w.getframerate() != 16000 or w.getcomptype() != "NONE"
                    or not 8000 <= frames <= 80000
                    or len(w.readframes(frames)) != frames * 2):
                raise STTUnavailable("local_wav_format_invalid")
    except (wave.Error, EOFError):
        raise STTUnavailable("local_wav_format_invalid") from None
    return round(frames * 1000 / 16000), hashlib.sha256(data).hexdigest()


def transcribe_once(request: dict, wav_data: bytes, *, local_origin_verified: bool = False) -> dict:
    """Transcribe exactly one short browser-owned WAV; never execute a spoken command.

    HTTP origin/auth and the explicit button are obligations of the PWA caller.
    This function never accesses the microphone and never uses the network.
    """
    if local_origin_verified is not True:
        raise STTUnavailable("local_origin_required")
    if not isinstance(request, dict) or request != {"command": COMMAND}:
        raise STTUnavailable("explicit_es_transcription_required")
    if silencio.apagado():
        raise STTUnavailable("hardware_declared_off")
    duration_ms, audio_sha256 = _validate_wav(wav_data)
    before = _temperature_c()
    if before >= MAX_BEELINK_TCTL_C:
        raise STTUnavailable("beelink_cpu_thermal_hold")
    if not oido.oido_disponible():
        raise STTUnavailable("local_whisper_cpp_or_model_missing")
    if not _LOCK.acquire(blocking=False):
        raise STTUnavailable("local_stt_busy")
    try:
        model_sha256 = _sha(oido.WHISPER_MODEL)
        with tempfile.TemporaryDirectory(prefix="hex-stt-local-") as folder:
            f = Path(folder) / "voice.wav"
            f.write_bytes(wav_data)
            os.chmod(f, 0o600)
            t0 = time.perf_counter()
            try:
                transcript = oido.transcribir(str(f), idioma="es", cpu_only=True, threads=2, timeout_sec=25)
            except Exception:
                raise STTUnavailable("local_stt_executor_failed") from None
            inference_ms = round((time.perf_counter() - t0) * 1000, 2)
        after = _temperature_c()
        if after >= MAX_BEELINK_TCTL_C:
            raise STTUnavailable("beelink_cpu_thermal_hold_after_transcription")
        if not isinstance(transcript, str) or not transcript.strip():
            raise STTUnavailable("local_stt_no_transcript")
        transcript = transcript.strip()
        if (len(transcript.encode("utf-8")) > MAX_TRANSCRIPT_BYTES
                or any(ord(ch) < 32 and ch not in "\n\t" for ch in transcript)):
            raise STTUnavailable("local_stt_transcript_out_of_budget")
        result = {
            "state": "LOCAL_TRANSCRIPT_ONLY",
            "cause": "not_authenticated_brain_reply",
            "source": "beelink_existing_oido_py_whisper_cpp",
            "language": "es",
            "text": transcript,
            "text_sha256": hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
            "audio_sha256": audio_sha256,
            "model_sha256": model_sha256,
            "duration_ms": duration_ms,
            "inference_ms": inference_ms,
            "capture_device": "NO_DATA(browser_microphone_not_attested)",
        }
        if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_ENVELOPE_BYTES:
            raise STTUnavailable("local_stt_receipt_out_of_budget")
        return result
    except STTUnavailable:
        raise
    except OSError:
        raise STTUnavailable("local_stt_filesystem_or_model_unavailable") from None
    finally:
        _LOCK.release()
