"""Synthetic-only adversarial tests for the atomic grant consumption/revocation journal.

Tests cover:
- Simultaneous claim race: exactly one success under concurrent processes
- Revoke vs claim: ordering matters
- Replay protection: double claim rejected
- Expiry: expired grants cannot be claimed
- No signer / absent journal: fail-closed behavior
- Corrupt journal: fail-closed behavior
- Integration with evaluate_authorization: journal provides consumed/revoked sets
"""
import datetime as dt
import hashlib
import json
import multiprocessing
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import agentes_contrato as A
import cuenta_cangrejo as CC
import grant_journal as GJ


def _grant_params(grant_id="1" * 64):
    """Common grant parameters for tests."""
    return {
        "grant_id": grant_id,
        "agent_id": "lantern",
        "device_id": "local-test",
        "grant_sha256": "2" * 64,
        "task_sha256": "3" * 64,
        "capability": "lab.propose",
        "expires_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1))
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _claim_worker(db_path: Path, grant_id: str, result_queue: multiprocessing.Queue, params: dict):
    """Worker process for concurrent claim tests."""
    try:
        result = GJ.claim_grant(db_path, **params)
        result_queue.put(("ok", result))
    except Exception as e:
        result_queue.put(("error", str(e)))


class TestJournalInit(unittest.TestCase):
    """Journal initialization and basic operations."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-journal-"))
        self.db_path = self.root / "journal.db"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_init_creates_journal(self):
        self.assertFalse(self.db_path.is_file())
        path = GJ.init_journal(self.db_path)
        self.assertEqual(path, self.db_path)
        self.assertTrue(self.db_path.is_file())

    def test_open_journal_creates_parent_dirs(self):
        nested = self.root / "deep" / "nested" / "journal.db"
        con = GJ.open_journal(nested)
        con.close()
        self.assertTrue(nested.is_file())

    def test_journal_schema_version(self):
        GJ.init_journal(self.db_path)
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            self.assertEqual(row[0], str(GJ.SCHEMA_VERSION))
        finally:
            con.close()

    def test_append_only_no_update(self):
        GJ.init_journal(self.db_path)
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(result["state"], "OK")
        # Direct attempt to update should fail
        con = sqlite3.connect(str(self.db_path), timeout=5)
        try:
            with con:
                con.execute("UPDATE journal SET cause = 'hacked' WHERE n = 1")
                self.fail("UPDATE should have been blocked by trigger")
        except sqlite3.IntegrityError:
            pass  # expected
        finally:
            con.close()

    def test_append_only_no_delete(self):
        GJ.init_journal(self.db_path)
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        GJ.claim_grant(self.db_path, **params, now=now)
        con = sqlite3.connect(str(self.db_path), timeout=5)
        try:
            with con:
                con.execute("DELETE FROM journal WHERE n = 1")
                self.fail("DELETE should have been blocked by trigger")
        except sqlite3.IntegrityError:
            pass  # expected
        finally:
            con.close()


class TestClaimGrant(unittest.TestCase):
    """Single-process claim tests."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-claim-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_successful_claim(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(result["state"], "OK")
        self.assertEqual(result["cause"], "grant_consumed")
        self.assertIn("n", result)

    def test_double_claim_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")
        self.assertEqual(r2["cause"], "grant_already_consumed")

    def test_different_grant_ids_both_succeed(self):
        p1 = _grant_params("a" * 64)
        p2 = _grant_params("b" * 64)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.claim_grant(self.db_path, **p1, now=now)
        r2 = GJ.claim_grant(self.db_path, **p2, now=now)
        self.assertEqual(r1["state"], "OK")
        self.assertEqual(r2["state"], "OK")

    def test_expired_grant_rejected(self):
        params = _grant_params()
        params["expires_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(result["cause"], "claim_grant_expired")

    def test_malformed_expiry_rejected(self):
        params = _grant_params()
        params["expires_at"] = "not-a-date"
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(result["cause"], "claim_expiry_malformed")

    def test_absent_journal_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        missing = self.root / "missing.db"
        result = GJ.claim_grant(missing, **params, now=now)
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("absent", result["cause"])

    def test_corrupt_journal_rejected(self):
        corrupt = self.root / "corrupt.db"
        corrupt.write_text("this is not a sqlite database", encoding="utf-8")
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.claim_grant(corrupt, **params, now=now)
        self.assertEqual(result["state"], "REJECTED")


class TestRevokeGrant(unittest.TestCase):
    """Revocation tests."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-revoke-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_successful_revocation(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        result = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(result["state"], "OK")
        self.assertEqual(result["cause"], "grant_revoked")

    def test_revoked_grant_cannot_be_claimed(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")
        self.assertEqual(r2["cause"], "grant_revoked")

    def test_consumed_grant_cannot_be_revoked(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")
        self.assertEqual(r2["cause"], "grant_already_consumed")

    def test_double_revocation_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")
        self.assertEqual(r2["cause"], "grant_already_revoked")

    def test_revoke_absent_journal_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        missing = self.root / "missing.db"
        result = GJ.revoke_grant(missing, **params, now=now)
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("absent", result["cause"])


class TestConcurrentClaims(unittest.TestCase):
    """Multi-process race condition tests — exactly one claim must succeed."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-race-"))
        self.db_path = self.root / "journal.db"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_simultaneous_claims_exactly_one_success(self):
        """Spawn multiple processes claiming the same grant; exactly one wins."""
        GJ.init_journal(self.db_path)
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        params["now"] = now

        num_workers = 8
        queues = [multiprocessing.Queue() for _ in range(num_workers)]
        processes = []

        for i in range(num_workers):
            q = queues[i]
            p = multiprocessing.Process(
                target=_claim_worker,
                args=(self.db_path, params["grant_id"], q, params),
            )
            processes.append(p)

        # Start all processes as close to simultaneously as possible
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)

        # Collect results
        results = []
        for q in queues:
            while not q.empty():
                status, data = q.get()
                results.append((status, data))

        ok_count = sum(1 for s, d in results if s == "ok" and d.get("state") == "OK")
        rejected_count = sum(1 for s, d in results if s == "ok" and d.get("state") == "REJECTED")

        self.assertEqual(
            ok_count, 1,
            f"Expected exactly 1 OK, got {ok_count} OK and {rejected_count} REJECTED",
        )
        self.assertEqual(len(results), num_workers, "All workers should report")

    def test_simultaneous_claims_different_grants_all_succeed(self):
        """Multiple processes claiming different grants all succeed."""
        GJ.init_journal(self.db_path)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

        num_workers = 4
        queues = [multiprocessing.Queue() for _ in range(num_workers)]
        processes = []

        for i in range(num_workers):
            q = queues[i]
            gid = str(i) * 64
            params = _grant_params(gid)
            params["now"] = now
            p = multiprocessing.Process(
                target=_claim_worker,
                args=(self.db_path, gid, q, params),
            )
            processes.append(p)

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)

        results = []
        for q in queues:
            while not q.empty():
                results.append(q.get())

        ok_count = sum(1 for s, d in results if s == "ok" and d.get("state") == "OK")
        self.assertEqual(ok_count, num_workers, f"All {num_workers} different grants should succeed")


class TestRevokeVsClaimRace(unittest.TestCase):
    """Revoke vs claim race — whichever arrives first wins."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-rev-claim-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_revoke_then_claim_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")

    def test_claim_then_revoke_rejected(self):
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        r1 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r1["state"], "OK")
        r2 = GJ.revoke_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")


class TestGetSets(unittest.TestCase):
    """Query the consumed/revoked sets for evaluate_authorization integration."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-sets-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_empty_sets_after_init(self):
        consumed = GJ.get_consumed_grant_ids(self.db_path)
        revoked = GJ.get_revoked_grant_ids(self.db_path)
        self.assertEqual(consumed, set())
        self.assertEqual(revoked, set())

    def test_consumed_set_after_claim(self):
        params = _grant_params("a" * 64)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        GJ.claim_grant(self.db_path, **params, now=now)
        consumed = GJ.get_consumed_grant_ids(self.db_path)
        self.assertIn("a" * 64, consumed)

    def test_revoked_set_after_revoke(self):
        params = _grant_params("b" * 64)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        GJ.revoke_grant(self.db_path, **params, now=now)
        revoked = GJ.get_revoked_grant_ids(self.db_path)
        self.assertIn("b" * 64, revoked)

    def test_absent_journal_returns_none(self):
        missing = self.root / "missing.db"
        self.assertIsNone(GJ.get_consumed_grant_ids(missing))
        self.assertIsNone(GJ.get_revoked_grant_ids(missing))

    def test_corrupt_journal_returns_none(self):
        corrupt = self.root / "corrupt.db"
        corrupt.write_text("not sqlite", encoding="utf-8")
        self.assertIsNone(GJ.get_consumed_grant_ids(corrupt))
        self.assertIsNone(GJ.get_revoked_grant_ids(corrupt))

    def test_mixed_consumed_and_revoked(self):
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        p1 = _grant_params("c" * 64)
        p2 = _grant_params("r" * 64)
        GJ.claim_grant(self.db_path, **p1, now=now)
        GJ.revoke_grant(self.db_path, **p2, now=now)
        consumed = GJ.get_consumed_grant_ids(self.db_path)
        revoked = GJ.get_revoked_grant_ids(self.db_path)
        self.assertIn("c" * 64, consumed)
        self.assertNotIn("c" * 64, revoked)
        self.assertIn("r" * 64, revoked)
        self.assertNotIn("r" * 64, consumed)


class TestJournalPersistence(unittest.TestCase):
    """Journal survives process restart."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-persist-"))
        self.db_path = self.root / "journal.db"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_claim_survives_reopen(self):
        GJ.init_journal(self.db_path)
        params = _grant_params()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        GJ.claim_grant(self.db_path, **params, now=now)
        # Re-read after "restart"
        consumed = GJ.get_consumed_grant_ids(self.db_path)
        self.assertIn(params["grant_id"], consumed)
        # Second claim must still be rejected
        r2 = GJ.claim_grant(self.db_path, **params, now=now)
        self.assertEqual(r2["state"], "REJECTED")


class TestReadJournalEntries(unittest.TestCase):
    """Audit log reading."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-read-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_empty_journal(self):
        entries = GJ.read_journal_entries(self.db_path)
        self.assertEqual(entries, [])

    def test_entries_after_operations(self):
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        p1 = _grant_params("e" * 64)
        p2 = _grant_params("f" * 64)
        GJ.claim_grant(self.db_path, **p1, now=now)
        GJ.revoke_grant(self.db_path, **p2, now=now)
        entries = GJ.read_journal_entries(self.db_path)
        self.assertEqual(len(entries), 2)
        actions = {e["action"] for e in entries}
        self.assertEqual(actions, {"consume", "revoke"})

    def test_absent_journal_returns_none(self):
        missing = self.root / "missing.db"
        self.assertIsNone(GJ.read_journal_entries(missing))


@unittest.skipUnless(shutil.which("ssh-keygen"), "NO_DATA(ssh-keygen_unavailable)")
class TestIntegrationWithEvaluateAuthorization(unittest.TestCase):
    """Integration: journal provides consumed/revoked sets to evaluate_authorization.

    This verifies the end-to-end flow: a grant that passes all checks in
    evaluate_authorization can be atomically claimed, and a second evaluation
    with the updated journal state must reject it as consumed.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-integration-"))
        self.db_path = self.root / "journal.db"
        GJ.init_journal(self.db_path)
        self.agent_fp, self.agent_private = CC.generar_par(persistente=True, directorio=self.root / "agent")
        self.sovereign_fp, self.sovereign_private = CC.generar_par(persistente=True, directorio=self.root / "sovereign")
        self.key_dir = self.root / "agent"
        self.agent_public = Path(self.agent_private + ".pub")
        sovereign_fields = Path(self.sovereign_private + ".pub").read_text().split()
        self.signers = self.root / "allowed_signers"
        self.signers.write_text(
            f'soberano namespaces="{CC.ACCOUNT_NAMESPACE},{A.GRANT_NAMESPACE}" '
            f'{sovereign_fields[0]} {sovereign_fields[1]}\n', encoding="ascii")
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) + dt.timedelta(minutes=1)
        self.task = b'{"action":"read-only-check","version":1}'
        raw_key = A._key_material(self.agent_public)
        self.card = {
            "schema": A.CARD_SCHEMA, "fixture": False,
            "agent": {"id": "lantern", "name": "Lantern", "kind": "rack-cli", "route": "thread"},
            "contributor": "fictional-contributor",
            "model": {"state": "NO_DATA", "cause": "test_model_not_observed"},
            "key": {"alg": "ed25519", "public_hex": raw_key, "registry": "babel registry/keys/lantern.pub"},
            "requests": ["lab.propose"],
            "conditions": {"state": "NO_DATA", "cause": "synthetic_conditions"},
            "authority": A.CARD_AUTHORITY,
        }
        self.card_raw = json.dumps(self.card, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.account = CC.crear_cuenta("puente", "nodo.1.local-test", ["herramientas"], self.agent_fp, ahora=self.now)
        self.account = self._activate_account(self.account)
        self.message = b'{"request_id":"req-1","agent_id":"lantern","body":"proposal"}'
        self.message_sig = CC.firmar(self.message, self.agent_private)
        self.grant = self._grant()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _sign(self, payload, private=None, namespace=A.GRANT_NAMESPACE):
        import uuid
        base = self.root / ("signed-" + uuid.uuid4().hex)
        base.write_bytes(payload)
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", namespace,
                        "-f", private or self.sovereign_private, str(base)],
                       check=True, capture_output=True)
        return Path(str(base) + ".sig").read_text(encoding="utf-8")

    def _activate_account(self, account):
        payload = CC._account_payload(account)
        signature = self._sign(payload, namespace=CC.ACCOUNT_NAMESPACE)
        activated = dict(account, estado="linkeado", firma_ssh=signature)
        return activated

    def _grant(self, **changes):
        import uuid
        card_sha = hashlib.sha256(self.card_raw).hexdigest()
        before = (self.now - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        after = (self.now + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "schema": A.GRANT_SCHEMA,
            "grant_id": "1" * 64,
            "agent_id": "lantern",
            "card_sha256": card_sha,
            "key_fingerprint": self.agent_fp,
            "task_sha256": hashlib.sha256(self.task).hexdigest(),
            "capability": "lab.propose",
            "device_id": "local-test",
            "scope": ["lab.propose"],
            "conditions_accepted_sha256": hashlib.sha256(b"accepted-test-conditions").hexdigest(),
            "not_before": before,
            "expires_at": after,
            "nonce": "3" * 64,
            "signature": "pending",
        }
        value.update(changes)
        unsigned = {k: v for k, v in value.items() if k != "signature"}
        value["signature"] = self._sign(A.canonical_bytes(unsigned))
        return value

    def _evaluate(self, **overrides):
        grant_raw = json.dumps(self.grant, sort_keys=True, separators=(",", ":")).encode()
        consumed = GJ.get_consumed_grant_ids(self.db_path)
        revoked = GJ.get_revoked_grant_ids(self.db_path)
        args = dict(
            card_raw=self.card_raw,
            grant_raw=grant_raw,
            account=self.account,
            message_signature=self.message_sig,
            signed_message=self.message,
            allowed_signers=self.signers,
            agent_key_dir=self.key_dir,
            task_bytes=self.task,
            capability="lab.propose",
            device_id="local-test",
            conditions_bytes=b"accepted-test-conditions",
            now=self.now,
            revoked_grant_ids=revoked if revoked is not None else set(),
            consumed_grant_ids=consumed if consumed is not None else set(),
        )
        args.update(overrides)
        return A.evaluate_authorization(**args)

    def test_eligible_then_claimed_then_rejected(self):
        """Full flow: eligible → claim → consumed → rejected on replay."""
        # First evaluation: eligible
        r1 = self._evaluate()
        self.assertEqual(r1["state"], "ELIGIBLE_FOR_ATOMIC_CLAIM", r1)

        # Claim the grant in the journal
        grant = self.grant
        claim_now = self.now
        claim_result = GJ.claim_grant(
            self.db_path,
            grant_id=grant["grant_id"],
            agent_id=grant["agent_id"],
            device_id=grant["device_id"],
            grant_sha256=hashlib.sha256(json.dumps(grant, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            task_sha256=grant["task_sha256"],
            capability=grant["capability"],
            expires_at=grant["expires_at"],
            now=claim_now,
        )
        self.assertEqual(claim_result["state"], "OK")

        # Second evaluation: must be rejected as consumed
        r2 = self._evaluate()
        self.assertEqual(r2["state"], "REJECTED")
        self.assertEqual(r2["cause"], "grant_replayed_or_consumed")

    def test_revoked_grant_rejected_by_authorization(self):
        """Revoke in journal → evaluate_authorization rejects."""
        grant = self.grant
        revoke_now = self.now
        revoke_result = GJ.revoke_grant(
            self.db_path,
            grant_id=grant["grant_id"],
            agent_id=grant["agent_id"],
            device_id=grant["device_id"],
            grant_sha256=hashlib.sha256(json.dumps(grant, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            task_sha256=grant["task_sha256"],
            capability=grant["capability"],
            expires_at=grant["expires_at"],
            now=revoke_now,
        )
        self.assertEqual(revoke_result["state"], "OK")

        r = self._evaluate()
        self.assertEqual(r["state"], "REJECTED")
        self.assertEqual(r["cause"], "grant_revoked")

    def test_no_signer_journal_returns_none(self):
        """When journal is absent, get_* return None → evaluate_authorization returns NO_DATA."""
        # Use a non-existent journal path
        missing = self.root / "missing_journal.db"
        consumed = GJ.get_consumed_grant_ids(missing)
        revoked = GJ.get_revoked_grant_ids(missing)
        self.assertIsNone(consumed)
        self.assertIsNone(revoked)
        # evaluate_authorization treats None as unavailable
        r = self._evaluate(consumed_grant_ids=None)
        self.assertEqual((r["state"], r["cause"]), ("NO_DATA", "grant_replay_state_unavailable"))


class TestJournalPath(unittest.TestCase):
    """Default path resolution."""

    def test_journal_path_with_base(self):
        base = Path("/tmp/test-base")
        path = GJ.journal_path(base)
        self.assertEqual(path, base / "registro" / "grant_journal.db")

    def test_journal_exists_false_for_missing(self):
        self.assertFalse(GJ.journal_exists(Path("/tmp/nonexistent-journal-999.db")))


if __name__ == "__main__":
    unittest.main()
