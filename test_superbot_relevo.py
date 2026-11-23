"""Superbot host adapter: both authority boundaries, one run per grant, receipts read back from the real relay.

Synthetic keys and a private tmux socket; `cat` stands in for the CLI. Nothing here is a real Sovereign grant.
The relay module comes from PRECEPTOROS_RELEVO_BIN (p0x bin/); without it the suite is NO_DATA (skipped).
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import agentes_contrato as A
import cuenta_cangrejo as CC
import grant_journal as GJ
import plan_store
import superbot_relevo as S

RELAY = S.load_relay()


@unittest.skipUnless(shutil.which("ssh-keygen") and shutil.which("tmux") and RELAY is not None,
                     "NO_DATA(ssh-keygen, tmux or cli_relevo unavailable)")
class SuperbotRelay(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-superbot-relay-"))
        (self.root / "sock").mkdir(mode=0o700)
        self.env = mock.patch.dict(os.environ, {"TMUX_TMPDIR": str(self.root / "sock")})
        self.env.start()
        os.environ.pop("TMUX", None)
        self.saved_root = RELAY.ROOT
        RELAY.ROOT = self.root / "relevo"
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        # keys and trust, as in test_agentes_contrato
        self.agent_fp, self.agent_private = CC.generar_par(persistente=True, directorio=self.root / "agent")
        self.sov_fp, self.sov_private = CC.generar_par(persistente=True, directorio=self.root / "sovereign")
        sov = Path(self.sov_private + ".pub").read_text().split()
        self.signers = self.root / "allowed_signers"
        self.signers.write_text(f'soberano namespaces="{CC.ACCOUNT_NAMESPACE},{A.GRANT_NAMESPACE}" {sov[0]} {sov[1]}\n')
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.card = {"schema": A.CARD_SCHEMA, "fixture": False,
                     "agent": {"id": "lantern", "name": "Lantern", "kind": "rack-cli", "route": "thread"},
                     "contributor": "fictional-contributor", "model": {"state": "NO_DATA", "cause": "test"},
                     "key": {"alg": "ed25519", "public_hex": A._key_material(Path(self.agent_private + ".pub")),
                             "registry": "babel registry/keys/lantern.pub"},
                     "requests": ["lab.read_document", "lab.propose"],
                     "conditions": {"state": "NO_DATA", "cause": "synthetic"}, "authority": A.CARD_AUTHORITY}
        self.card_raw = A.canonical_bytes(self.card)
        acc = CC.crear_cuenta("puente", "nodo.1.local-test", ["herramientas"], self.agent_fp, ahora=self.now)
        self.account = dict(acc, estado="linkeado", firma_ssh=self._sign(CC._account_payload(acc), CC.ACCOUNT_NAMESPACE))
        self.conditions = b"accepted-test-conditions"
        self.journal = GJ.init_journal(self.root / "registro" / "grant_journal.db")
        # plan, managed terminal, goal approved once by the (simulated) owner
        self.plan = plan_store.put(self.home, json.dumps({"schema": plan_store.SCHEMA, "title": "Read one file",
                                                          "text": "Read README and say its first line."}).encode())["plan_sha256"]
        self.sid, self.name = RELAY.launch("cat", "local", "none", ["cat"], self.root, "superbot test")
        self.goal = self._goal([self.sid])

    def tearDown(self):
        RELAY._tmux("kill-server")
        RELAY.ROOT = self.saved_root
        self.env.stop()
        shutil.rmtree(self.root)

    def _sign(self, payload, namespace, private=None):
        base = self.root / ("signed-" + uuid.uuid4().hex)
        base.write_bytes(payload)
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", private or self.sov_private, str(base)],
                       check=True, capture_output=True)
        return Path(str(base) + ".sig").read_text()

    def _goal(self, sessions, voice=S.VOICE):
        gid = RELAY.goal_propose(voice, "Superbot read", "one read-only task", sessions, 1, 5)["goal_id"]
        with mock.patch("sys.stdin.isatty", return_value=True), \
                mock.patch("builtins.input", return_value="APROBAR GOAL " + gid[:8]), mock.patch("builtins.print"):
            RELAY.goal_approve(gid)
        return gid

    def _task(self, instruction="Read README and say its first line.", capability="lab.read_document", plan=None):
        return S.task_bytes(plan or self.plan, "lantern", capability, instruction)

    def _grant(self, task_raw, grant_id="1" * 64, capability="lab.read_document", hours=1):
        g = {"schema": A.GRANT_SCHEMA, "grant_id": grant_id, "agent_id": "lantern",
             "card_sha256": hashlib.sha256(self.card_raw).hexdigest(), "key_fingerprint": self.agent_fp,
             "task_sha256": hashlib.sha256(task_raw).hexdigest(), "capability": capability,
             "device_id": "local-test", "scope": [capability],
             "conditions_accepted_sha256": hashlib.sha256(self.conditions).hexdigest(),
             "not_before": (self.now - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "expires_at": (self.now + dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "nonce": uuid.uuid4().hex * 2}
        g["signature"] = self._sign(A.canonical_bytes(g), A.GRANT_NAMESPACE)
        return A.canonical_bytes(g)

    def _dispatch(self, run_id="sb-run-1", task_raw=None, grant_raw=None, goal=None, sid=None, sign_task_sha=None):
        task_raw = task_raw or self._task()
        grant_raw = grant_raw or self._grant(task_raw)
        goal, sid = goal or self.goal, sid or self.sid
        req = S.request_bytes(run_id, sign_task_sha or hashlib.sha256(task_raw).hexdigest(), goal, sid, "lantern")
        return S.dispatch(self.home, run_id=run_id, task_raw=task_raw, session_id=sid, goal_id=goal,
                          card_raw=self.card_raw, grant_raw=grant_raw, account=self.account,
                          request_signature=CC.firmar(req, self.agent_private),
                          allowed_signers=self.signers, agent_key_dir=self.root / "agent", device_id="local-test",
                          conditions_bytes=self.conditions, journal_db=self.journal, relay=RELAY, now=self.now)

    def _screen(self, needle, tries=40):
        for _ in range(tries):
            if needle in RELAY.screen(self.sid).get("text", ""):
                return True
            time.sleep(0.1)
        return False

    # ── the first E2E shape: one read-only task, both boundaries, receipt back ──
    def test_authorized_read_task_runs_once_and_its_receipt_comes_back_under_the_same_id(self):
        with mock.patch.object(RELAY, "SETTLE_IDLE_S", 1):
            out = self._dispatch()
            self.assertEqual(out["state"], "DISPATCHED", out)
            self.assertTrue(self._screen("[SUPERBOT run=sb-run-1"))
            time.sleep(2.2)
            st = S.status(self.home, "sb-run-1", relay=RELAY)
        self.assertEqual(st["state"], "RESULT", st)
        run = st["run"]
        for k in ("plan_sha256", "task_sha256", "agent_id", "grant_id", "run_id", "goal_id", "receipt"):
            self.assertTrue(run[k], k)
        self.assertEqual(run["plan_sha256"], self.plan)
        # the same identifier and receipt the MCP (ChatGPT Web) reads
        ev = [e for e in RELAY.read_events(self.sid, 0, 20)["events"] if e["op_id"] == "sb-run-1"]
        self.assertEqual([e["kind"] for e in ev], ["delivered", "ack", "result"])
        self.assertEqual(run["receipt"]["sha256"], ev[-1]["sha256"])
        g = next(x for x in RELAY.goals()["goals"] if x["goal_id"] == self.goal)
        self.assertEqual(g["ops"][0]["op_id"], "sb-run-1")
        nb = S.notebook(self.home)
        self.assertEqual(nb["runs"][0]["state"], "RESULT")
        self.assertNotIn("instruction", json.dumps(nb))
        self.assertEqual(GJ.get_consumed_grant_ids(self.journal), {"1" * 64})

    def test_a_goal_without_a_grant_and_a_grant_without_a_goal_both_stop_before_any_paste(self):
        task = self._task()
        other_goal = self._goal([self.sid], voice="codex-web")                 # covers the session, wrong voice
        self.assertEqual(self._dispatch(goal=other_goal)["cause"], "goal_belongs_to_other_voice")
        bad_grant = self._grant(task)[:-40] + b'"}'                            # unsigned / broken grant
        self.assertNotEqual(self._dispatch(run_id="sb-run-2", grant_raw=bad_grant)["state"], "DISPATCHED")
        RELAY.goal_revoke(self.goal)
        self.assertEqual(self._dispatch(run_id="sb-run-3")["cause"], "goal_revoked")
        self.assertFalse(self._screen("[SUPERBOT", tries=5))
        self.assertEqual(GJ.get_consumed_grant_ids(self.journal), set())

    def test_one_grant_one_run_and_one_run_id_once(self):
        task = self._task()
        grant = self._grant(task)
        self.assertEqual(self._dispatch("sb-run-1", task, grant)["state"], "DISPATCHED")
        self.assertEqual(self._dispatch("sb-run-1", task, grant)["cause"], "run_id_already_used")      # A4
        again = self._dispatch("sb-run-9", task, grant)                                               # replay
        self.assertEqual((again["state"], again["cause"]), ("REJECTED", "grant_replayed_or_consumed"))

    def test_changed_task_wrong_signer_write_capability_and_missing_plan_are_refused(self):
        task = self._task()
        grant = self._grant(task)
        changed = self._task("Read README and delete it.")
        self.assertEqual(self._dispatch(task_raw=changed, grant_raw=grant)["cause"], "grant_task_mismatch")   # A3
        write = self._task(capability="lab.propose")
        self.assertEqual(self._dispatch(task_raw=write, grant_raw=self._grant(write, capability="lab.propose"))["cause"],
                         "capability_not_read_only_in_first_version")
        ghost = self._task(plan="0" * 64)
        self.assertTrue(self._dispatch(task_raw=ghost)["cause"].startswith("plan_"))                  # A8
        forged = self._dispatch(run_id="sb-run-5", sign_task_sha="f" * 64)           # agent signed another task
        self.assertEqual(forged["cause"], "agent_message_signature_invalid")
        g = json.loads(grant)
        self.assertEqual(GJ.revoke_grant(self.journal, g["grant_id"], "lantern", "local-test", hashlib.sha256(grant).hexdigest(),
                                         g["task_sha256"], g["capability"], g["expires_at"], now=self.now)["state"], "OK")
        self.assertNotEqual(self._dispatch(run_id="sb-run-6", task_raw=task, grant_raw=grant)["state"], "DISPATCHED")

    def test_unknown_outcome_blocks_new_runs_until_a_person_resolves_it(self):
        with mock.patch.object(RELAY, "SETTLE_IDLE_S", 30):
            self.assertEqual(self._dispatch()["state"], "DISPATCHED")
            self.assertTrue(self._screen("[SUPERBOT"))
            RELAY._tmux("kill-session", "-t", "=" + self.name)
            st = S.status(self.home, "sb-run-1", relay=RELAY)
        self.assertEqual((st["state"], st["run"]["cause"]), ("OUTCOME_UNKNOWN", "relay_blocked"))
        task2 = self._task("Second read.")
        blocked = self._dispatch("sb-run-2", task2, self._grant(task2, grant_id="2" * 64))
        self.assertEqual(blocked["cause"], "outcome_unknown_blocks_new_runs")                         # A12
        self.assertEqual(S.resolve(self.home, "sb-run-1", "x")["cause"], "resolution_needs_an_interactive_terminal")
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="RESOLVER sb-run-1"):
            self.assertEqual(S.resolve(self.home, "sb-run-1", "terminal died; checked by hand")["state"], "RESOLVED")
        self.assertEqual(S._unresolved(self.home), [])

    def test_a_secret_like_instruction_is_refused_before_the_grant_is_consumed(self):
        task = self._task("Read README; token=abcdefghijklmnop0123")
        out = self._dispatch(task_raw=task, grant_raw=self._grant(task))
        self.assertEqual(out["cause"], "instruction_secret_or_signature_like")
        self.assertEqual(GJ.get_consumed_grant_ids(self.journal), set())
        self.assertEqual(S.runs(self.home), [])

    def test_a_relay_without_ack_result_has_its_own_cause(self):
        old = self.root / "old"
        old.mkdir()
        (old / "cli_relevo.py").write_text("def goal_covers(*a): pass\ndef goal_send(*a): pass\n"
                                           "def claim(*a): pass\ndef read_events(*a): pass\nSECRET = FIRMA = None\n")
        with mock.patch.dict(os.environ, {"PRECEPTOROS_RELEVO_BIN": str(old)}):
            self.assertEqual(S.relay_probe(), (None, "relay_older_than_p0x_143_missing_settle"))

    def test_without_the_relay_everything_is_no_data(self):
        with mock.patch.dict(os.environ, {"PRECEPTOROS_RELEVO_BIN": str(self.root / "nowhere")}):
            self.assertIsNone(S.load_relay())
            task = self._task()
            out = S.dispatch(self.home, run_id="sb-run-1", task_raw=task, session_id=self.sid, goal_id=self.goal,
                             card_raw=self.card_raw, grant_raw=self._grant(task), account=self.account,
                             request_signature="x", allowed_signers=self.signers, agent_key_dir=self.root / "agent",
                             device_id="local-test", conditions_bytes=self.conditions, journal_db=self.journal)
        self.assertEqual(out, {"state": "NO_DATA", "cause": "relay_unavailable"})


class TaskBytes(unittest.TestCase):
    def test_task_bytes_are_canonical_and_closed(self):
        raw = S.task_bytes("a" * 64, "lantern", "lab.read_document", "Read it.")
        self.assertEqual(S.parse_task(raw)["agent_id"], "lantern")
        for bad in (raw.replace(b'"Read it."', b'"Read it." '), raw[:-1] + b',"x":1}', b"[]"):
            with self.assertRaises(ValueError):
                S.parse_task(bad)
        with self.assertRaises(ValueError):
            S.task_bytes("a" * 64, "Lantern!", "lab.read_document", "x")
        with self.assertRaises(ValueError):
            S.task_bytes("a" * 64, "lantern", "lab.read_document", "x" * 5000)


if __name__ == "__main__":
    unittest.main()
