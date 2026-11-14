"""Native pure system diagnosis. Informational evidence never grants tool access."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

import estado_app
from guardrails import PATRONES_CORE

SCHEMA = "preceptoros.system-check/0"
TTL_SECONDS = 120
MAX_INPUT = 65536
MAX_MODELS = 64
FIELDS = ("os", "architecture", "python", "auxiliary_python", "sqlite",
          "cpu_logical", "memory_available_bytes", "disk_free_bytes", "models",
          "internet", "privacy_preview")
SERVICES = ("model_engine", "tool_transport", "remote_provider")
SOURCES = {
    "os": "host.platform", "architecture": "host.platform",
    "python": "host.runtime", "auxiliary_python": "host.path_lookup",
    "sqlite": "host.import", "cpu_logical": "host.cpu_count",
    "memory_available_bytes": "host.meminfo", "disk_free_bytes": "host.disk_usage",
    "models": "consola.modelos_pc", "internet": "host.connectivity_witness",
    "privacy_preview": "host.privacy_self_check",
}
MODEL_SOURCES = frozenset({"consola.modelos_pc", "system_check_local.model_store"})
CAUSES = frozenset({"check_complete", "input_invalid", "input_limit_exceeded",
    "not_measured", "source_unavailable", "source_mismatch", "evidence_expired",
    "evidence_future", "evidence_not_measured", "model_inventory_unavailable",
    "model_inventory_partial", "service_not_probed", "service_unreachable",
    "auxiliary_python_absent", "python_unsupported", "dependency_missing",
    "hardware_not_measured", "connectivity_not_measured", "unsupported_platform",
    "first_use_not_measured", "operation_not_completed", "runtime_not_measured"})
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}\Z")
_DATE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


@dataclass(frozen=True)
class Observation:
    """Only the local host adapter supplies observations, never browser/model text."""
    value: object
    source: str
    observed_at: str
    origin: str = "MEASURED"
    cause: str = "not_measured"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _utc(value):
    if type(value) is not str or not _DATE.fullmatch(value):
        raise ValueError("invalid clock")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def unknown(cause, source=None, observed_at=None):
    if cause not in CAUSES:
        cause = "input_invalid"
    return {"state": "NO_DATA", "cause": cause, "source": source,
            "observed_at": observed_at, "freshness": "UNKNOWN"}


def _integer(value, low=0):
    return type(value) is int and low <= value <= (1 << 63)-1


def _label(value):
    return (type(value) is str and bool(_LABEL.fullmatch(value)) and ".." not in value
            and not any(re.search(pattern, value) for pattern in PATRONES_CORE.values()))


def _valid(field, value):
    if field in ("os", "architecture"):
        return _label(value) and len(value) <= 40
    if field == "python":
        return type(value) is list and len(value) == 3 and all(_integer(v) and v < 100 for v in value)
    if field in ("auxiliary_python", "sqlite", "internet", "privacy_preview") or field in SERVICES:
        return type(value) is bool
    if field == "models":
        return (type(value) is list and len(value) <= MAX_MODELS
                and all(_label(v) for v in value) and len(value) == len(set(value)))
    return _integer(value, 1 if field == "cpu_logical" else 0)


def _datum(field, raw, now):
    source = SOURCES.get(field, "host.service_witness:"+field)
    if not isinstance(raw, Observation):
        return unknown("not_measured", source)
    if raw.source != source and not (field == "models" and raw.source in MODEL_SOURCES):
        return unknown("source_mismatch", source)
    source = raw.source
    if raw.origin not in ("MEASURED", "DECLARED", "SIMULATED", "NO_DATA"):
        return unknown("input_invalid", source)
    seen = _utc(raw.observed_at)
    age = (now-seen).total_seconds()
    if age < 0:
        return unknown("evidence_future", source)
    if raw.origin == "NO_DATA":
        return unknown(raw.cause, source, raw.observed_at)
    if not _valid(field, raw.value):
        return unknown("input_invalid", source, raw.observed_at)
    if age > TTL_SECONDS:
        result = unknown("evidence_expired", source, raw.observed_at)
        result["freshness"] = "STALE"
        return result
    return {"state": raw.origin, "value": deepcopy(raw.value), "source": source,
            "observed_at": raw.observed_at, "freshness": "FRESH", "cause": "check_complete" if raw.origin == "MEASURED" else "evidence_not_measured"}


def _measured(row, value=None):
    return row["state"] == "MEASURED" and (value is None or row["value"] == value)


def _finish(result):
    result["projection_ref"] = "sha256:"+fingerprint(result)
    return result


def diagnose(observations, now):
    """Pure closed projection; missing facts never become zero or online.

    observations contains any subset of FIELDS and services (the fixed three
    optional service keys). Sources and timestamps are validated per fact.
    A local adapter observation is not a cryptographic identity attestation.
    """
    try:
        clock = _utc(now)
        if type(observations) is not dict or not set(observations) <= set(FIELDS) | {"services"}:
            raise ValueError("invalid input")
        raw_services = observations.get("services", {})
        if type(raw_services) is not dict or not set(raw_services) <= set(SERVICES):
            raise ValueError("invalid services")
        raw = [vars(v) if isinstance(v, Observation) else None
               for v in list(observations.values()) if not isinstance(v, dict)]
        raw += [vars(v) if isinstance(v, Observation) else None for v in raw_services.values()]
        if len(canonical(raw)) > MAX_INPUT:
            return _finish({"schema": SCHEMA, "state": "NO_DATA", "cause": "input_limit_exceeded"})
        data = {f: _datum(f, observations.get(f), clock) for f in FIELDS}
        services = {f: _datum(f, raw_services.get(f), clock) for f in SERVICES}
        for row in services.values():
            if _measured(row, False):
                row["cause"] = "service_unreachable"
            elif row["state"] == "NO_DATA" and row["cause"] == "not_measured":
                row["cause"] = "service_not_probed"
        requirements = {
            "python": unknown("runtime_not_measured"),
            "sqlite": unknown("dependency_missing"),
            "auxiliary_python": deepcopy(data["auxiliary_python"]),
        }
        if _measured(data["python"]):
            requirements["python"] = deepcopy(data["python"])
            requirements["python"]["value"] = tuple(data["python"]["value"]) >= (3, 10, 0)
            if not requirements["python"]["value"]:
                requirements["python"]["cause"] = "python_unsupported"
        if _measured(data["sqlite"]):
            requirements["sqlite"] = deepcopy(data["sqlite"])
            if not requirements["sqlite"]["value"]:
                requirements["sqlite"]["cause"] = "dependency_missing"
        if _measured(data["auxiliary_python"], False):
            requirements["auxiliary_python"]["cause"] = "auxiliary_python_absent"
        local = _measured(requirements["python"], True)
        connected = local and any(_measured(v, True) for v in services.values())
        mode = "CONNECTED" if connected else "LOCAL" if local else "UNKNOWN"
        evidence = [data["python"]] if local else []
        if connected:
            evidence += [v for v in services.values() if _measured(v, True)]
        status_evidence = {"source": "system_check.diagnose",
            "observed_at": min((v["observed_at"] for v in evidence), default=None),
            "freshness": "FRESH" if local else "UNKNOWN",
            "inputs": [{"source": v["source"], "observed_at": v["observed_at"]} for v in evidence]}
        # Informational actions only: no commands, grants, connect or install callbacks.
        actions = ["review_diagnosis", "review_requirements"] if local else ["review_requirements"]
        if local and _measured(data["privacy_preview"], True):
            actions.append("review_privacy_rules")
        if local and _measured(data["models"]):
            actions.append("inspect_model_files")
        return _finish({"schema": SCHEMA, "state": mode, "cause": "check_complete" if local else "runtime_not_measured",
            "checked_at": now, "status_evidence": status_evidence, "facts": data, "requirements": requirements, "services": services,
            "local_capabilities": actions, "offline_actions": actions[:],
            "model_scope": "configured_local_store_files_not_runtime_or_all_engines",
            "hardware_scope": "system_logical_cpus_and_system_memory_not_task_budget",
            "authority": "NOT_AUTHORIZED", "first_use": unknown("first_use_not_measured")})
    except (ValueError, TypeError, AttributeError, OverflowError, RecursionError, UnicodeError):
        return _finish({"schema": SCHEMA, "state": "NO_DATA", "cause": "input_invalid"})


def console_models(catalogue, observed_at, *, source="consola.modelos_pc"):
    """Adapt consola.modelos_pc's file-presence evidence without copying paths.

    Missing catalogue is not a measured zero. A manifest alone never proves
    installed bytes, loaded weights, hash integrity or callable inference.
    """
    unavailable = Observation(None, source, observed_at, "NO_DATA", "model_inventory_unavailable")
    if source not in MODEL_SOURCES:
        return unavailable
    if type(catalogue) is not dict or catalogue.get("estado") != "MEDIDO":
        return unavailable
    rows = catalogue.get("modelos")
    if (type(rows) is not list or len(rows) > MAX_MODELS or type(catalogue.get("total")) is not int
            or catalogue["total"] != len(rows)):
        return Observation(None, source, observed_at, "NO_DATA", "model_inventory_partial")
    names = []
    for row in rows:
        if type(row) is not dict or not _label(row.get("id")) or "error" in row:
            return Observation(None, source, observed_at, "NO_DATA", "model_inventory_partial")
        if row.get("blob_presente") is True:
            sha, size = row.get("sha256"), row.get("bytes")
            if (type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha)
                    or not _integer(size, 1)):
                return Observation(None, source, observed_at, "NO_DATA", "model_inventory_partial")
            names.append(row["id"])
        elif row.get("blob_presente") is not False:
            return Observation(None, source, observed_at, "NO_DATA", "model_inventory_partial")
    if len(names) != len(set(names)):
        return Observation(None, source, observed_at, "NO_DATA", "model_inventory_partial")
    return Observation(sorted(names), source, observed_at)


def first_use_metric(start_ns, finish_ns, completed):
    """Host monotonic times, same process; never infer clean-install duration."""
    if type(completed) is not bool:
        return unknown("input_invalid")
    if not completed:
        return unknown("operation_not_completed")
    if not _integer(start_ns) or not _integer(finish_ns) or finish_ns < start_ns:
        return unknown("input_invalid")
    return {"state": "MEASURED", "elapsed_ns": finish_ns-start_ns,
            "source": "host.monotonic", "scope": "check_to_local_report_not_installation"}


def harness_surface(report):
    """Use the existing surface contract; wall time is never Proof of Tick."""
    if report.get("projection_ref") != "sha256:"+fingerprint({k: v for k, v in report.items() if k != "projection_ref"}):
        raise ValueError("projection integrity mismatch")
    surface = {"esquema": estado_app.ESQUEMA, "zona": "harness",
        "transicion": {"origen": None, "destino": "harness", "tau": 0}, "tick": None,
        "frescura": {"estado": "NO_DATA", "edad_tics": None, "causa": "proof_of_tick_unavailable"},
        "guion": {"titulo": "Check my computer", "orden": ["titulo", "estado", "contenido", "acciones"], "edad_tics": None},
        "semantica": {"hue": None, "saturacion": None, "luminosidad": None,
                      "niebla": True, "borde": "normal", "halo": "normal"},
        "fuente_semantica": dict(estado_app.FUENTE_SEMANTICA)}
    estado_app.serializar(surface)
    return {"projection_ref": report["projection_ref"], "state": report["state"],
            "surface": surface}
