"""Sabotage: break memory_onboarding.py on purpose and require the tests to catch each break.

Each mutation is a real way this step could go wrong: creating without consent, recreating an existing memory,
losing it, creating on a mere read, «repairing» a file that is not a memory. A copy is mutated in a temporary
folder; the module tests run against it and MUST fail. Prints one JSON line; exit 0 only if every sabotage was caught."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "memory_onboarding.py").read_text(encoding="utf-8")
MUTATIONS = {
    "create_without_consent": ("    if not consent_ok(body):\n", "    if False:\n"),
    "recreate_existing": ('        if before["state"] == "READY":\n', "        if False:\n"),
    # the worst kind: wipes and recreates an existing memory, then answers as if nothing happened
    "lose_existing_silently": ('            return 200, dict(before, outcome="ALREADY_EXISTS", changed=False)\n',
                               '            os.remove(ruta); M.crear(ruta)\n            return 200, dict(before, outcome="ALREADY_EXISTS", changed=False)\n'),
    "create_on_read": ('    out = {"schema": SCHEMA,', '    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)\n    out = {"schema": SCHEMA,'),
    "repair_unknown_file": ('        if before["state"] == "UNKNOWN":\n', "        if False:\n"),
}


def main():
    out, caught = {}, True
    with tempfile.TemporaryDirectory() as tmp:
        for name, (old, new) in MUTATIONS.items():
            if SRC.count(old) != 1:
                out[name] = "NO_DATA:anchor_missing"; caught = False; continue
            mod = Path(tmp) / (name + ".py")
            mod.write_text(SRC.replace(old, new), encoding="utf-8")
            env = dict(os.environ, PRECEPTOROS_SABOTAGE_MODULE=str(mod))
            r = subprocess.run([sys.executable, "-m", "unittest", "test_memory_onboarding.Module"], cwd=ROOT, env=env,
                               capture_output=True, text=True, timeout=120)
            out[name] = "caught" if r.returncode != 0 else "MISSED"
            caught = caught and r.returncode != 0
        # The pre-#317 gap: Origin netloc == Host accepted for ANY host (DNS rebinding), and the route's exact Host
        # check removed. Both layers are cut together; the RealServer rebinding cases must then fail.
        srv = (ROOT / "bin" / "preceptoros-pwa").read_text(encoding="utf-8")
        anchor_helper = '        if not origin or not host:\n            return False\n'
        anchor_route = 'or host not in ("localhost:" + port, "127.0.0.1:" + port, "[::1]:" + port):'
        if srv.count(anchor_helper) != 1 or srv.count(anchor_route) != 1:
            out["server_guard_weakened"] = "NO_DATA:anchor_missing"; caught = False
        else:
            weak = srv.replace(anchor_helper, anchor_helper +
                '        if urllib.parse.urlsplit(origin).netloc == host:\n            return True\n')
            weak = weak.replace(anchor_route, 'or False and host not in ("localhost:" + port, "127.0.0.1:" + port, "[::1]:" + port):')
            bad = Path(tmp) / "preceptoros-pwa"
            bad.write_text(weak, encoding="utf-8")
            env = dict(os.environ, PRECEPTOROS_SABOTAGE_SERVER=str(bad))
            r = subprocess.run([sys.executable, "-m", "unittest", "test_memory_onboarding.RealServer"], cwd=ROOT, env=env,
                               capture_output=True, text=True, timeout=300)
            out["server_guard_weakened"] = "caught" if r.returncode != 0 else "MISSED"
            caught = caught and r.returncode != 0
    print(json.dumps({"sabotage": "caught" if caught else "MISSED", "cases": out}))
    return 0 if caught else 1


if __name__ == "__main__":
    sys.exit(main())
