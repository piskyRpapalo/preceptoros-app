"""Read-only local System Check adapter. No model, account, daemon or network needed.

Run: python3 -m system_check_local. The result stays on stdout. Importing this
module does not run collection. Only fixed OS/stdlib probes and the existing
configured model-store reader are used; no command or browser path is accepted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import shutil
import sys
import time

import system_check as core


def _missing(field, stamp, cause="source_unavailable"):
    return core.Observation(None, core.SOURCES[field], stamp, "NO_DATA", cause)


def _probe(field, stamp, read):
    try:
        return core.Observation(read(), core.SOURCES[field], stamp)
    except (OSError, ValueError, RuntimeError, ImportError, AttributeError, KeyError, TypeError):
        return _missing(field, stamp)


def _memory_available():
    if not sys.platform.startswith("linux"):
        raise OSError("unsupported memory probe")
    with open("/proc/meminfo", "rb") as stream:
        content = stream.read(16385)
    if len(content) > 16384:
        raise ValueError("memory source limit")
    for line in content.decode("ascii").splitlines():
        words = line.split()
        if words and words[0] == "MemAvailable:" and len(words) == 3 and words[2] == "kB":
            return int(words[1])*1024
    raise ValueError("memory unavailable")


def _sqlite():
    # A fixed import proves the dependency imports, not that user storage is writable.
    importlib.import_module("sqlite3")
    return True


def _privacy_core():
    # redactar_salida() can seed policies.json. Inspect only the immutable core
    # patterns: no policy creation, no user config and no arbitrary text probe.
    import re
    import guardrails
    return bool(re.search(guardrails.PATRONES_CORE["ASSIGNED_SECRET"], "password=fixture-private-value"))


MAX_STORE_ENTRIES = 256
MAX_STORE_DEPTH = 8
MAX_STORE_BYTES = 1 << 20


def _directory(parent, name):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)


def _read_manifest(root, parts, budget):
    directory = os.dup(root)
    try:
        for name in parts[:-1]:
            child = _directory(directory, name)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > min(65536, budget[0]):
                raise ValueError("manifest type or byte limit")
            data = stream.read(min(65537, budget[0]))
            if os.fstat(stream.fileno()).st_size != info.st_size or len(data) != info.st_size:
                raise ValueError("manifest changed during capture")
            budget[0] -= len(data)
            if len(data) > 65536 or budget[0] < 0:
                raise ValueError("store byte limit")
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate key")
                value[key] = item
            return value
        return json.loads(data, object_pairs_hook=unique)
    finally:
        os.close(directory)


def _manifest_paths(root):
    remaining = [MAX_STORE_ENTRIES]
    paths = []
    def visit(directory, parts):
        if len(parts) > MAX_STORE_DEPTH:
            raise ValueError("store depth limit")
        with os.scandir(directory) as entries:
            for entry in entries:
                remaining[0] -= 1
                if remaining[0] < 0 or entry.is_symlink():
                    raise ValueError("store entry limit or symlink")
                child_parts = parts+(entry.name,)
                if entry.is_dir(follow_symlinks=False):
                    child = _directory(directory, entry.name)
                    try:
                        visit(child, child_parts)
                    finally:
                        os.close(child)
                elif entry.is_file(follow_symlinks=False):
                    paths.append(child_parts)
                    if len(paths) > core.MAX_MODELS:
                        raise ValueError("model count limit")
                else:
                    raise ValueError("unsupported store file")
    manifests = _directory(root, "manifests")
    try:
        visit(manifests, ())
    finally:
        os.close(manifests)
    return sorted(paths)


def _present_blob(root, sha, size):
    blobs = _directory(root, "blobs")
    try:
        try:
            fd = os.open("sha256-"+sha, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=blobs)
        except FileNotFoundError:
            return False
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("blob is not regular")
            return info.st_size == size
        finally:
            os.close(fd)
    finally:
        os.close(blobs)


def _catalogue():
    # The existing reader's schema/root selection is reused, but its unbounded
    # rglob and permissive blob paths cannot serve this diagnostic boundary.
    # Unsupported descriptor APIs abstain; they never fall back to unsafe reads.
    import consola
    if (not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY")
            or os.open not in os.supports_dir_fd or os.scandir not in os.supports_fd):
        raise OSError("descriptor-safe model observation unavailable")
    root = os.open(consola.raiz_ollama(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        paths = _manifest_paths(root)  # validate all count/type limits BEFORE reading manifests
        budget, rows = [MAX_STORE_BYTES], []
        for parts in paths:
            if len(parts) < 3:
                raise ValueError("manifest layout")
            manifest = _read_manifest(root, ("manifests",)+parts, budget)
            if type(manifest) is not dict or type(manifest.get("layers")) is not list:
                raise ValueError("manifest schema")
            layers = [v for v in manifest["layers"] if type(v) is dict
                      and v.get("mediaType") == "application/vnd.ollama.image.model"]
            if len(layers) != 1:
                raise ValueError("model layer ambiguous")
            layer = layers[0]
            sha, size = layer.get("digest"), layer.get("size")
            if (type(sha) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", sha)
                    or type(size) is not int or not 0 < size <= (1 << 63)-1):
                raise ValueError("model metadata invalid")
            name = "/".join(parts[1:-1])
            if parts[0] == "registry.ollama.ai" and name.startswith("library/"):
                name = name[len("library/"):]
            elif parts[0] != "registry.ollama.ai":
                name = parts[0]+"/"+name
            rows.append({"id": name+":"+parts[-1], "sha256": sha[7:], "bytes": size,
                         "blob_presente": _present_blob(root, sha[7:], size)})
        return {"estado": "MEDIDO", "total": len(rows), "modelos": rows}
    finally:
        os.close(root)


def collect(*, model_reader=None):
    """Collect once locally. A future Harness handler can call run_check().

    The existing model reader observes configured store manifests/blob sizes,
    not every engine or loaded weights. No service/Internet probes are made.
    Errors use fixed causes, never exception strings or private filesystem paths.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    facts = {
        "os": _probe("os", stamp, platform.system),
        "architecture": _probe("architecture", stamp, platform.machine),
        "python": core.Observation(list(sys.version_info[:3]), core.SOURCES["python"], stamp),
        "auxiliary_python": _probe("auxiliary_python", stamp, lambda: shutil.which("python3") is not None),
        "sqlite": _probe("sqlite", stamp, _sqlite),
        "cpu_logical": _probe("cpu_logical", stamp, os.cpu_count),
        "memory_available_bytes": _probe("memory_available_bytes", stamp, _memory_available),
        "disk_free_bytes": _probe("disk_free_bytes", stamp, lambda: shutil.disk_usage(Path(__file__).parent).free),
        "internet": _missing("internet", stamp, "connectivity_not_measured"),
        "privacy_preview": _probe("privacy_preview", stamp, _privacy_core),
    }
    try:
        source = "consola.modelos_pc" if model_reader else "system_check_local.model_store"
        facts["models"] = core.console_models((model_reader or _catalogue)(), stamp, source=source)
    except (OSError, ValueError, RuntimeError, ImportError, AttributeError, KeyError, TypeError):
        facts["models"] = core.Observation(None, "consola.modelos_pc" if model_reader else "system_check_local.model_store",
                                          stamp, "NO_DATA", "model_inventory_unavailable")
    facts["services"] = {name: core.Observation(None, "host.service_witness:"+name,
                            stamp, "NO_DATA", "service_not_probed") for name in core.SERVICES}
    return facts, stamp


def run_check(*, model_reader=None):
    start = time.monotonic_ns()
    observations, stamp = collect(model_reader=model_reader)
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = core.diagnose(observations, checked_at)
    # Bind the operation timing into the same canonical report for all consumers.
    report.pop("projection_ref")
    report["first_use"] = core.first_use_metric(start, time.monotonic_ns(), report["state"] in ("LOCAL", "CONNECTED"))
    report["projection_ref"] = "sha256:"+core.fingerprint(report)
    return report


def main():
    report = run_check()
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    return 0 if report["state"] in ("LOCAL", "CONNECTED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
