#!/usr/bin/env python3
"""Offline Android 1.1 candidate judge; never certifies physical inference or OWNER access.

Usage (release candidate only):
  python3 mvp-android/release_guard.py candidate.apk \
    --apk-sha256 <reviewed-apk-sha> --jni-sha256 <reviewed-jni-sha> \
    --cert-sha256 <owner-approved-cert-sha> --apksigner /path/to/apksigner \
    --aapt2 /path/to/aapt2

Hashes/certificate must come from independent review, not from the APK being checked.
No network, install, signing, changes to the APK, or private data printing.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import stat
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

MODEL_SHA256 = "ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747"
MODEL = "assets/offline-mini.gguf"
JNI = "lib/arm64-v8a/libmini_llama.so"
REQUIRED = (
    MODEL, JNI, "assets/licenses/ATTRIBUTIONS.txt",
    "assets/licenses/Apache-2.0.txt", "assets/licenses/llama.cpp-MIT.txt",
)
MAX_APK_BYTES = 600 * 1024 * 1024
MAX_MEMBER_BYTES = 450 * 1024 * 1024
MAX_TOTAL_BYTES = 800 * 1024 * 1024
MAX_ENTRIES = 4096
CHUNK = 1024 * 1024
# These are patterns, not private values. Never print any matched content.
_PRIVATE_ELF_PATH = re.compile(rb"(?:/home/|/Users/|/root/|[A-Za-z]:\\\\Users\\\\)[A-Za-z0-9_.-]+[/\\\\]")
_PRIVATE_PUBLIC_ROUTE = re.compile(
    rb"/api/(?:hexelion/(?:chat|decision|search)|hitl|nodo/(?:identity|edificio|export))"
)
_PRIVATE_HOST = re.compile(rb"[A-Za-z0-9._-]+\.ts\.net\b|(?i:onexstation)")
_SHA = re.compile(r"[a-fA-F0-9]{64}\Z")


class ReleaseHold(Exception):
    """Only stable, non-sensitive cause codes may cross the CLI boundary."""


def pin(value: str, cause: str) -> str:
    if not _SHA.fullmatch(value or ""):
        raise ReleaseHold(cause)
    return value.lower()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(CHUNK), b""):
            h.update(part)
    return h.hexdigest()


def _valid_entry(info) -> bool:
    p = info.filename
    # Path normalization must never turn hostile ZIP names into trusted names.
    if not p or p.startswith("/") or "\\" in p or "\x00" in p:
        return False
    if any(seg in ("", ".", "..") for seg in p.rstrip("/").split("/")):
        return False
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) == stat.S_IFLNK:
        return False
    return True


def _member_digest(archive: ZipFile, name: str, *, elf_paths=False, public_asset=False) -> str:
    digest = hashlib.sha256()
    tail = b""
    with archive.open(name) as source:
        while True:
            piece = source.read(CHUNK)
            if not piece:
                break
            digest.update(piece)
            window = tail + piece
            if elf_paths and _PRIVATE_ELF_PATH.search(window):
                raise ReleaseHold("JNI_PRIVATE_BUILD_PATH")
            if public_asset and (_PRIVATE_PUBLIC_ROUTE.search(window) or _PRIVATE_HOST.search(window)):
                raise ReleaseHold("PUBLIC_ASSET_PRIVATE_REFERENCE")
            tail = window[-256:]
    return digest.hexdigest()


def inspect_zip(apk: Path, *, apk_sha: str, jni_sha: str,
                model_sha: str = MODEL_SHA256) -> None:
    apk_pin = pin(apk_sha, "APK_PIN_MISSING")
    jni_pin = pin(jni_sha, "JNI_PIN_MISSING")
    model_pin = pin(model_sha, "MODEL_PIN_INVALID")
    try:
        if not apk.is_file() or not 0 < apk.stat().st_size <= MAX_APK_BYTES:
            raise ReleaseHold("APK_MISSING_OR_OVERSIZE")
        if sha_file(apk) != apk_pin:
            raise ReleaseHold("APK_SHA_MISMATCH")
        with ZipFile(apk, "r") as arc:
            infos = arc.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ReleaseHold("ZIP_ENTRY_LIMIT")
            names = [x.filename for x in infos]
            if len(names) != len(set(names)):
                raise ReleaseHold("ZIP_DUPLICATE_ENTRY")
            if any(not _valid_entry(info) for info in infos):
                raise ReleaseHold("ZIP_INVALID_PATH_OR_LINK")
            if any(x.file_size > MAX_MEMBER_BYTES for x in infos):
                raise ReleaseHold("ZIP_MEMBER_LIMIT")
            if sum(x.file_size for x in infos) > MAX_TOTAL_BYTES:
                raise ReleaseHold("ZIP_TOTAL_LIMIT")
            if not set(REQUIRED).issubset(names):
                raise ReleaseHold("APK_REQUIRED_MEMBER_MISSING")
            if _member_digest(arc, MODEL) != model_pin:
                raise ReleaseHold("GGUF_SHA_MISMATCH")
            if _member_digest(arc, JNI, elf_paths=True) != jni_pin:
                raise ReleaseHold("JNI_SHA_MISMATCH")
            for name in REQUIRED[2:]:
                if not arc.getinfo(name).file_size:
                    raise ReleaseHold("LICENSE_EMPTY")
                _member_digest(arc, name)
            for info in infos:
                if info.filename.startswith("assets/") and info.filename not in REQUIRED:
                    if not info.is_dir():
                        _member_digest(arc, info.filename, public_asset=True)
    except (OSError, ValueError, BadZipFile, RuntimeError, EOFError) as exc:
        raise ReleaseHold("APK_UNREADABLE_OR_CORRUPT") from exc


def _run(tool: Path, args: list[str], cause: str) -> str:
    if not tool.is_file() or not tool.exists():
        raise ReleaseHold(cause)
    try:
        p = subprocess.run([str(tool), *args], capture_output=True, text=True,
                           timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseHold(cause) from exc
    if p.returncode != 0 or not p.stdout.strip():
        raise ReleaseHold(cause)
    return p.stdout


def inspect_signature_and_identity(apk: Path, *, cert_sha: str,
                                   apksigner: Path, aapt2: Path) -> None:
    cert_pin = pin(cert_sha, "CERT_PIN_MISSING")
    sig = _run(apksigner, ["verify", "--verbose", "--print-certs", str(apk)],
               "APK_SIGNATURE_UNVERIFIED")
    matches = re.findall(r"^Signer #(\d+) certificate SHA-256 digest:\s*([a-fA-F0-9]{64})\s*$",
                         sig, flags=re.MULTILINE)
    if len(matches) != 1 or matches[0][0] != "1" or matches[0][1].lower() != cert_pin:
        raise ReleaseHold("APK_SIGNER_MISMATCH")
    if not re.search(r"^Verified using v[23] scheme.*:\s*true\s*$", sig,
                     flags=re.MULTILINE | re.IGNORECASE):
        raise ReleaseHold("APK_V2_V3_SIGNATURE_MISSING")
    badging = _run(aapt2, ["dump", "badging", str(apk)], "APK_IDENTITY_UNVERIFIED")
    match = re.search(r"^package:\s+name='([^']+)'\s+versionCode='([0-9]+)'", badging,
                      flags=re.MULTILINE)
    if not match or match.group(1) != "org.preceptoros.app" or int(match.group(2)) < 8:
        raise ReleaseHold("APK_PACKAGE_OR_VERSION_INVALID")
    if re.search(r"^application-debuggable(?:\b|:)", badging, flags=re.MULTILINE):
        raise ReleaseHold("APK_DEBUGGABLE")


def audit(apk: Path, *, apk_sha: str, jni_sha: str, cert_sha: str,
          apksigner: Path, aapt2: Path, model_sha: str = MODEL_SHA256) -> None:
    # Verify authenticity before interpreting attacker-supplied ZIP entries.
    inspect_signature_and_identity(apk, cert_sha=cert_sha,
                                   apksigner=apksigner, aapt2=aapt2)
    inspect_zip(apk, apk_sha=apk_sha, jni_sha=jni_sha, model_sha=model_sha)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("apk", type=Path)
    p.add_argument("--apk-sha256", required=True)
    p.add_argument("--jni-sha256", required=True)
    p.add_argument("--cert-sha256", required=True)
    p.add_argument("--apksigner", type=Path, required=True)
    p.add_argument("--aapt2", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        audit(a.apk, apk_sha=a.apk_sha256, jni_sha=a.jni_sha256,
              cert_sha=a.cert_sha256, apksigner=a.apksigner, aapt2=a.aapt2)
    except ReleaseHold as exc:
        print("HOLD(" + str(exc) + ")", file=sys.stderr)
        return 1
    print("PASS_STATIC(release_archive_signature_identity_integrity_privacy); "
          "NO_DATA(Android_inference_TalkBack_OWNER_E2E)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
