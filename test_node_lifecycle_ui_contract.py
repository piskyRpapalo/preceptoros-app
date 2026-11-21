"""Round 4 · the My node ladder against Codex's real projection (node_lifecycle.read, #402), not a hand-written double.

Each Aduana decision is produced by node_lifecycle.read itself (only the network fetch is replaced) and then fed to
interface/node_registration.js `lifecycle()`; the ladder must stop, name who acts, and never show LIVE early.
"""
from __future__ import annotations
import json
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import node_building
import node_lifecycle as L

ROOT = Path(__file__).resolve().parent
NODE = "nodo.42.fixture"
AT = "2026-11-21T18:59:55Z"
NOW = datetime(2026, 11, 21, 19, 0, tzinfo=timezone.utc)
JS = r"""
const flow = require('./interface/node_registration.js');
const rows = JSON.parse(require('fs').readFileSync(0, 'utf8')).map(([identity, life]) => {
  const v = flow.lifecycle({ identity, lifecycle: life });
  return { current: v.current, live: v.live, revoked: v.revoked, sentence: flow.lifecycleSentence(v),
           stages: v.stages.map((s) => [s.key, s.state, s.cause, s.done]) };
});
process.stdout.write(JSON.stringify(rows));
"""


def ladder(cases):
    out = subprocess.run(["node", "-e", JS], cwd=ROOT, input=json.dumps(cases), capture_output=True, text=True,
                         timeout=30)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


class LadderReadsCodexProjection(unittest.TestCase):
    def projection(self, *, intake=True, decision=None):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            node_building.provisionar_identidad(home, NODE)
            request = {"schema": "preceptoros.deployment-request/1", "node": NODE, "consent": True,
                       "nonce": "a" * 32, "device_sha256": "b" * 64}
            ref = L._digest(request)
            receipt = {"schema": "preceptoros.deployment-request-receipt/1", "request_id": ref,
                       "state": "AWAITING_HUMAN", "received_at": AT}
            if intake:
                self.assertTrue(L.record_intake(home, request, receipt))
            key = home / "review-key"
            key.write_text("t" * 40)
            key.chmod(0o600)

            def fetch(url, headers, limit):
                if decision is None:
                    raise OSError("offline")
                body = {**receipt, "state": decision, "node": NODE, "consent": True,
                        "device_sha256": request["device_sha256"], "receipt_sha256": ref}
                if decision != "AWAITING_HUMAN":
                    body.update(decision_at=AT, decision_sha256="e" * 64)
                return body
            return L.read(home, review_key_file=str(key) if decision else None, fetch=fetch, now=NOW)

    def test_codex_projection_drives_the_ladder_without_skips(self):
        ident = {"state": "MEASURED", "node": NODE}
        cases = [
            ("no intake", self.projection(intake=False)),
            ("intake recorded", self.projection()),
            ("aduana pending", self.projection(decision="AWAITING_HUMAN")),
            ("aduana approved", self.projection(decision="APPROVED")),
            ("aduana rejected", self.projection(decision="REJECTED")),
            ("aduana revoked", self.projection(decision="REVOKED")),
        ]
        for _, p in cases:
            self.assertEqual(p["schema"], "preceptoros.node-lifecycle/1")
            self.assertEqual(p["node"], NODE)
        got = dict(zip([c[0] for c in cases], ladder([[ident, p] for _, p in cases])))
        self.assertEqual(got["no intake"]["current"], 1)  # consent: the owner acts
        self.assertIn("Next (you)", got["no intake"]["sentence"])
        # Stage 3 comes from the server record, so it survives a reload with no in-page receipt.
        r = got["intake recorded"]
        self.assertEqual(r["stages"][2][:4], ["request", "PENDING", "aduana_intake_receipt_verified", True])
        self.assertEqual(r["current"], 3)
        self.assertIn("Needs a human SSH signature", r["sentence"])
        self.assertIn("signed_export_or_plan_unavailable", r["sentence"])
        # Aduana's answers never jump the unsigned stage 4.
        for name in ("aduana pending", "aduana approved"):
            self.assertEqual(got[name]["current"], 3, name)
            self.assertFalse(got[name]["live"], name)
            self.assertFalse(got[name]["stages"][4][3], name)
        self.assertEqual(got["aduana pending"]["stages"][4][1:3], ["PENDING", "d1_awaiting_owner_review"])
        self.assertEqual(got["aduana approved"]["stages"][4][2], "earlier_stage_unverified")
        # A rejection is final: the owner is told so instead of being sent to sign a refused request.
        rj = got["aduana rejected"]
        self.assertEqual(rj["current"], 4)
        self.assertIn("Blocked (d1_rejection_verified): Read the cause, then send a new request", rj["sentence"])
        self.assertFalse(any(s[3] for s in rj["stages"][3:]))
        # A verified revocation sends the owner back to Request admission and says so.
        rv = got["aduana revoked"]
        self.assertTrue(rv["revoked"]); self.assertEqual(rv["current"], 2)
        self.assertIn("Blocked (node_revoked)", rv["sentence"])
        for g in got.values():
            self.assertFalse(g["stages"][9][3], "revoke is never ticked off")

    def test_codex_heartbeat_gap_keeps_live_closed(self):
        # node_lifecycle.read marks live MEASURED but heartbeat NO_DATA(projection_omits_exact_heartbeat_receipt).
        # The ladder must not show LIVE until the heartbeat receipt exists (contract gap reported to Codex).
        stages = {k: {"state": "MEASURED", "cause": "fixture"} for k in L.STAGES}
        stages["request"] = {"state": "PENDING", "cause": "aduana_intake_receipt_verified"}
        stages["heartbeat"] = {"state": "NO_DATA", "cause": "projection_omits_exact_heartbeat_receipt"}
        stages["live"] = {"state": "MEASURED", "cause": "aduana_live_projection_confirmed"}
        [g] = ladder([[{"state": "MEASURED", "node": NODE}, {"schema": L.SCHEMA, "node": NODE, "stages": stages}]])
        self.assertFalse(g["live"])
        self.assertEqual(g["current"], 5)
        self.assertEqual(g["stages"][6][2], "earlier_stage_unverified")
        self.assertIn("projection_omits_exact_heartbeat_receipt", g["sentence"])


if __name__ == "__main__":
    unittest.main()
