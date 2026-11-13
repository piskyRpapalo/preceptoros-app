"""TEST LAUNCHER, never a product entry point: the app server with a SYNTHETIC records source injected in process.

Used only by tests/records_source.browser.cjs, on its own port with a throw-away HOME. It plays the host: it sets
tareas_hexelion.RECORDS_SOURCE once, before serving, to a reader of <HOME>/synthetic_records.json (a fixture the test
writes; not a journal). Nothing here opens a live journal, changes the 8742 service or adds a way to configure a
source from the environment of the real server.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tareas_hexelion  # noqa: E402

FIXTURE = Path(os.environ["HOME"]) / "synthetic_records.json"


def synthetic_source(observed_at):
    got = json.loads(FIXTURE.read_text(encoding="utf-8"))          # read-only; a missing file is a failed source
    return {"records": got["records"], "complete_ref": got.get("complete_ref")}


tareas_hexelion.RECORDS_SOURCE = synthetic_source
loader = importlib.machinery.SourceFileLoader("preceptoros_pwa_under_test", str(ROOT / "bin" / "preceptoros-pwa"))
spec = importlib.util.spec_from_loader(loader.name, loader)
pwa = importlib.util.module_from_spec(spec)
loader.exec_module(pwa)
sys.exit(pwa.main([]))
