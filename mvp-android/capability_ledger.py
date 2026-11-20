"""Android Capability Ledger: source, package, installed and runtime are independent."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

SCHEMA = "preceptoros.android-capability-ledger/1"
CANONICAL = "org.preceptoros.app"
LEGACY = "org.preceptoros.mvp"
OWNER_CERT = "16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"
NEXT_VERSION = 8

SOURCE = {
    "mathematics": {
        "mvp-android/native-mini/mini_quality.h": ("has_loop(", "sample_token("),
        "mvp-android/native-mini/mini_quality_cases.cpp": (),
    },
    "jni": {
        "mvp-android/native-mini/mini_jni.cpp": ("Java_org_preceptoros_mvp_MiniNative_generate", "llama_model_load_from_file"),
        "mvp-android/app/src/main/java/org/preceptoros/mvp/MiniNative.java": ("native",),
    },
    "local_model": {
        "mvp-android/app/build.gradle": ("offlineMiniModel", "org.preceptoros.app"),
        "mvp-android/offline_mini.js": (),
    },
    "accessibility": {
        "interface/audio_accessibility.js": (),
        "interface/acho_sonido.js": (),
    },
    "six_panels": {
        "interface/app.html": ('id="tab-conversacion"', 'id="tab-cuaderno"',
                               'id="tab-lab"', 'id="tab-ajustes"',
                               'id="tab-modelos"', 'id="tab-settings"'),
        "interface/app.js": (),
        "interface/mvp_first_run.js": (),
        "interface/superbot_talk.js": (),
        "interface/talk_crab_canvas.js": (),
    },
    "node_consent": {
        "mvp-android/android_join_bridge.js": (),
        "mvp-android/android_review_bridge.js": (),
        "mvp-android/android_heartbeat_bridge.js": (),
        "mvp-android/app/src/main/java/org/preceptoros/mvp/DeploymentJoinBridge.java": ("addWebMessageListener",),
        "mvp-android/app/src/main/java/org/preceptoros/mvp/HeartbeatOnceBridge.java": (),
        "interface/node_registration.js": (),
    },
    "documents_harness": {
        "interface/documents.js": (),
        "interface/notebook.js": (),
        "interface/owner_model_slots.js": (),
    },
}
APK = {
    "mathematics": ("lib/arm64-v8a/libmini_llama.so",),
    "jni": ("lib/arm64-v8a/libmini_llama.so",),
    "local_model": ("assets/offline-mini.gguf", "assets/offline_mini.js"),
    "accessibility": ("assets/audio_accessibility.js", "assets/acho_sonido.js"),
    "six_panels": ("assets/app.html", "assets/app.css", "assets/app.js",
                    "assets/mvp_first_run.js", "assets/superbot_talk.js",
                    "assets/talk_crab_canvas.js"),
    "node_consent": ("assets/android_join_bridge.js", "assets/android_review_bridge.js",
                     "assets/android_heartbeat_bridge.js", "assets/node_registration.js"),
    "documents_harness": ("assets/documents.js", "assets/notebook.js",
                          "assets/owner_model_slots.js"),
}

def no_data(cause):
    return {"state": "NO_DATA", "cause": cause}

def source_ledger(root):
    categories = {}
    for category, witnesses in SOURCE.items():
        missing, hashes = [], []
        for rel, tokens in witnesses.items():
            file = Path(root) / rel
            if not file.is_file() or file.is_symlink() or file.stat().st_size == 0:
                missing.append(rel)
                continue
            data = file.read_bytes()
            if any(token not in data.decode("utf8", errors="replace") for token in tokens):
                missing.append(rel + "#symbol_missing")
            hashes.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest()})
        categories[category] = ({"state": "CODE_PRESENT", "witnesses": hashes}
                                if not missing else {"state": "NO_DATA",
                                    "cause": "source_capability_missing",
                                    "missing": missing, "witnesses": hashes})
    return {"layer": "source", "categories": categories,
            "all_present": all(c["state"] == "CODE_PRESENT" for c in categories.values())}

def parse_badging(text):
    m = re.search(r"package:\s+name='([^']+)'\s+versionCode='(\d+)'\s+versionName='([^']+)'", text)
    return ({"state": "MEASURED", "package": m.group(1),
             "versionCode": int(m.group(2)), "versionName": m.group(3)}
            if m else no_data("badging_unparseable"))

def parse_certificate(text):
    m = re.search(r"certificate SHA-256 digest:\s*([0-9a-f]{64})", text, re.I)
    return {"state": "MEASURED", "sha256": m.group(1).lower()} if m else no_data("cert_unparseable")

def sha_archive_member(archive, name):
    h = hashlib.sha256()
    with archive.open(name) as stream:
        for block in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_parity(archive, source_root):
    if source_root is None:
        return no_data("source_root_not_provided")
    mismatch = []
    # Gradle's copyPanels copies interface and Android-only bridge scripts.
    compared = 0
    for name in sorted({asset for paths in APK.values() for asset in paths}):
        if not name.startswith("assets/") or name.endswith(".gguf"):
            continue
        compared += 1
        rel = name.removeprefix("assets/")
        source_path = Path(source_root) / (
            ("mvp-android/" if rel in
             ("offline_mini.js", "android_join_bridge.js", "android_review_bridge.js",
              "android_heartbeat_bridge.js")
             else "interface/") + rel)
        if not source_path.is_file() or source_path.is_symlink() or name not in archive.namelist():
            mismatch.append(name)
            continue
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != sha_archive_member(archive, name):
            mismatch.append(name)
    return ({"state": "BYTE_EQUAL", "compared_assets": compared}
            if not mismatch else {"state": "NO_DATA", "cause": "apk_source_bytes_mismatch",
                                  "mismatched_assets": mismatch})


def inspect_apk(path, tools_dir=None, min_version=NEXT_VERSION, source_root=None, expected_model_sha=None, expected_jni_sha=None):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return {"layer": "apk", **no_data("apk_missing_or_symlink")}
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(2 * 1024 * 1024)
            if not block:
                break
            h.update(block)
    digest = h.hexdigest()
    result = {"layer": "apk", "bytes": path.stat().st_size, "sha256": digest,
              "capabilities": {}, "identity": no_data("build_tools_unavailable"),
              "source_parity": no_data("source_root_not_provided"),
              "embedded_artifacts": {}, "embedded_identity": no_data("approved_digests_not_provided")}
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                return {**result, **no_data("apk_duplicate_entries")}
            if archive.testzip() is not None:
                return {**result, **no_data("apk_crc_failed")}
            for cap, paths in APK.items():
                missing = [p for p in paths if p not in names or archive.getinfo(p).file_size == 0
                           or ((archive.getinfo(p).external_attr >> 16) & 0o170000) == 0o120000]
                result["capabilities"][cap] = (
                    {"state": "PACKAGED"} if not missing else
                    {"state": "NO_DATA", "cause": "apk_capability_missing", "missing": missing})
            result["source_parity"] = source_parity(archive, source_root)
            for artifact in ("assets/offline-mini.gguf", "lib/arm64-v8a/libmini_llama.so"):
                if artifact in names and archive.getinfo(artifact).file_size > 0:
                    result["embedded_artifacts"][artifact] = {
                        "bytes": archive.getinfo(artifact).file_size,
                        "sha256": sha_archive_member(archive, artifact)}
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError):
        return {**result, **no_data("apk_unreadable")}
    model = result["embedded_artifacts"].get("assets/offline-mini.gguf")
    jni = result["embedded_artifacts"].get("lib/arm64-v8a/libmini_llama.so")
    pin_valid = (isinstance(expected_model_sha, str) and
                 isinstance(expected_jni_sha, str) and
                 re.fullmatch(r"[0-9a-f]{64}", expected_model_sha) and
                 re.fullmatch(r"[0-9a-f]{64}", expected_jni_sha))
    if pin_valid:
        match = (model and jni and model["sha256"] == expected_model_sha and
                 jni["sha256"] == expected_jni_sha)
        result["embedded_identity"] = (
            {"state": "PINNED"} if match
            else no_data("model_or_jni_digest_changed"))
    if tools_dir:
        aapt, signer = Path(tools_dir) / "aapt2", Path(tools_dir) / "apksigner"
        if aapt.is_file() and signer.is_file():
            try:
                a = subprocess.run([str(aapt), "dump", "badging", str(path)],
                                   capture_output=True, text=True, timeout=30)
                b = subprocess.run([str(signer), "verify", "--print-certs", str(path)],
                                   capture_output=True, text=True, timeout=30)
                meta, cert = parse_badging(a.stdout), parse_certificate(b.stdout)
                if a.returncode or b.returncode or meta["state"] != "MEASURED" or cert["state"] != "MEASURED":
                    result["identity"] = no_data("apk_identity_verification_failed")
                else:
                    valid = (meta["package"] == CANONICAL and
                             meta["versionCode"] >= min_version and cert["sha256"] == OWNER_CERT)
                    result["identity"] = {**meta, "certificate_sha256": cert["sha256"],
                                          "state": "VERIFIED" if valid else "BLOCKED",
                                          "cause": None if valid else "package_version_or_cert_mismatch"}
            except (OSError, subprocess.TimeoutExpired):
                result["identity"] = no_data("apk_tool_failed")
    complete = all(x["state"] == "PACKAGED" for x in result["capabilities"].values())
    parity_ok = result["source_parity"]["state"] == "BYTE_EQUAL"
    pins_ok = result["embedded_identity"]["state"] == "PINNED"
    result["state"] = ("VERIFIED_PACKAGE"
                       if complete and parity_ok and pins_ok and
                       result["identity"]["state"] == "VERIFIED" else "NO_DATA")
    if result["state"] == "NO_DATA":
        result["cause"] = ("apk_capability_missing" if not complete else
                           result["identity"].get("cause") or
                           result["source_parity"].get("cause") or
                           result["embedded_identity"].get("cause") or "apk_unverified")
    return result

def parse_dumpsys(text, package):
    m = re.search(r"\bversionCode=(\d+)", text)
    if not m:
        return {"package": package, **no_data("not_installed_or_unreadable")}
    v = re.search(r"\bversionName=([^\r\n]+)", text)
    user = re.search(r"User 0:[^\r\n]*", text)
    raw_enabled = re.search(r"\benabled=(\d+)\b", user.group(0)) if user else None
    enabled = {"0": "DEFAULT", "1": "ENABLED", "2": "DISABLED",
               "3": "USER_DISABLED", "4": "DISABLED_UNTIL_USED"}
    return {"state": "INSTALLED_METADATA", "package": package,
            "versionCode": int(m.group(1)), "versionName": v.group(1).strip() if v else None,
            "user0_enabled": enabled.get(raw_enabled.group(1), "NO_DATA") if raw_enabled else "NO_DATA"}

def installed_apk_sha256(serial, package, adb="adb"):
    """Read SHA on device; no APK export, no serial/path in output."""
    try:
        p = subprocess.run([adb, "-s", serial, "shell", "pm", "path", package],
                           capture_output=True, text=True, timeout=18)
        paths = [line.removeprefix("package:").strip()
                 for line in p.stdout.splitlines() if line.startswith("package:")]
        if p.returncode != 0 or not paths:
            return no_data("adb_package_path_unavailable")
        base = next((x for x in paths if x.endswith("/base.apk")), paths[0])
        if not base.startswith("/data/app/") or not re.fullmatch(r"[/a-zA-Z0-9._+=~-]+", base):
            return no_data("adb_apk_path_untrusted")
        digest = subprocess.run([adb, "-s", serial, "shell", "sha256sum", base],
                                capture_output=True, text=True, timeout=45)
        match = re.match(r"^([0-9a-f]{64})\s", digest.stdout)
        if digest.returncode != 0 or not match:
            return no_data("device_apk_digest_unavailable")
        return {"state": "MEASURED", "sha256": match.group(1)}
    except (OSError, subprocess.TimeoutExpired):
        return no_data("device_apk_digest_tool_failed")


def installed_ledger(serial, adb="adb"):
    """Read-only metadata and optional on-device SHA; never writes or prints serial."""
    entries = []
    for pkg in (CANONICAL, LEGACY):
        try:
            q = subprocess.run([adb, "-s", serial, "shell", "dumpsys", "package", pkg],
                               capture_output=True, text=True, timeout=18)
            entries.append(parse_dumpsys(q.stdout if q.returncode == 0 else "", pkg))
        except (OSError, subprocess.TimeoutExpired):
            entries.append({"package": pkg, **no_data("adb_unavailable")})
    canonical, legacy = entries
    for entry in entries:
        entry["installed_apk"] = (installed_apk_sha256(serial, entry["package"], adb)
                                  if entry["state"] == "INSTALLED_METADATA"
                                  else no_data("package_not_installed_or_unreadable"))
    return {"layer": "installed", "packages": entries,
            "state": "INSTALLED_METADATA" if canonical["state"] == "INSTALLED_METADATA" else "NO_DATA",
            "legacy_migration": "NEEDS_OWNER_REVIEW" if legacy["state"] == "INSTALLED_METADATA" else "NO_DATA",
            "certificate": no_data("installed_cert_requires_matching_signed_candidate")}

def make_report(root, apk=None, tools_dir=None, serial=None, adb="adb",
                expected_model_sha=None, expected_jni_sha=None):
    return {"schema": SCHEMA,
            "source": source_ledger(root),
            "apk": inspect_apk(apk, tools_dir, source_root=root,
                               expected_model_sha=expected_model_sha,
                               expected_jni_sha=expected_jni_sha)
                   if apk else {"layer": "apk", **no_data("candidate_apk_not_provided")},
            "installed": installed_ledger(serial, adb) if serial else {"layer": "installed", **no_data("device_not_examined")},
            "runtime": {"layer": "runtime", **no_data("physical_inference_a11y_rack_turn_not_measured")},
            "product": {"APP 1.0": "owner_distribution_label_not_versionCode",
                        "APP 1.1": "local_inference_goal_not_certified_release"}}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--apk", type=Path)
    p.add_argument("--tools-dir", type=Path, default=Path(os.environ["ANDROID_BUILD_TOOLS"]) if "ANDROID_BUILD_TOOLS" in os.environ else None)
    p.add_argument("--model-sha256", help="owner-approved GGUF digest for candidate release")
    p.add_argument("--jni-sha256", help="owner-approved native library digest for candidate release")
    p.add_argument("--serial", help="ADB serial, never included in output")
    p.add_argument("--adb", default=os.environ.get("ANDROID_ADB", "adb"))
    p.add_argument("--strict-source", action="store_true")
    a = p.parse_args()
    report = make_report(a.root, a.apk, a.tools_dir, a.serial, a.adb,
                         a.model_sha256, a.jni_sha256)
    print(json.dumps(report, indent=2, sort_keys=True))
    # Supplying a candidate APK is a release gate, not a casual information
    # display. NO_DATA or BLOCKED must not return a successful process exit.
    return 1 if (((a.strict_source or a.apk is not None) and not report["source"]["all_present"]) or
                 (a.apk is not None and report["apk"]["state"] != "VERIFIED_PACKAGE")) else 0

if __name__ == "__main__":
    raise SystemExit(main())
