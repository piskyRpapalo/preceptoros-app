"""OWNER/Talk boundary tests: agent grants and their journal are NOT OWNER authority.

No real keys, no private requests, no app service writes or model calls.
These tests document the missing cross-contract gate; NOT an OWNER E2E.
"""
import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

import agentes_contrato as A
import grant_journal as J


def grant(**updates):
    item = {
        "schema": A.GRANT_SCHEMA, "grant_id": "1" * 64,
        "agent_id": "fixture", "card_sha256": "2" * 64,
        "key_fingerprint": "3" * 64, "task_sha256": "4" * 64,
        "capability": "talk.write", "device_id": "fixture-device",
        "scope": ["talk.write"], "conditions_accepted_sha256": "5" * 64,
        "not_before": "2026-11-20T00:00:00Z",
        "expires_at": "2030-11-21T00:00:00Z", "nonce": "6" * 64,
        "signature": "SYNTHETIC_NOT_A_REAL_SIGNATURE",
    }
    item.update(updates)
    return item


class OwnerGrantCannotBeAgentGrant(unittest.TestCase):
    def assert_denied(self, expected, **changes):
        value = A.validate_grant(grant(**changes))
        self.assertEqual((value["state"], value["cause"]), ("REJECTED", expected))

    def test_owner_audience_not_accepted(self):
        self.assert_denied("grant_fields_invalid", audience="owner-talk")

    def test_owner_scope_turn_not_accepted(self):
        self.assert_denied("grant_scope_invalid", scope=["turn"])

    def test_owner_capability_not_accepted(self):
        self.assert_denied("grant_scope_invalid", capability="owner-talk",
                           scope=["owner-talk"])

    def test_owner_revocation_epoch_not_self_declared(self):
        self.assert_denied("grant_fields_invalid", epoch=1)

    def test_owner_issuer_not_self_declared(self):
        self.assert_denied("grant_fields_invalid", issuer="soberano")

    def test_invalid_nonce_rejected(self):
        self.assert_denied("grant_nonce_invalid", nonce="guessable")

    def test_missing_signature_is_not_authentication(self):
        result = A.validate_grant(grant(signature=""))
        self.assertEqual((result["state"], result["cause"]),
                         ("NO_DATA", "grant_signature_missing"))

    def test_valid_shape_is_not_signature_or_execution(self):
        result = A.validate_grant(grant())
        self.assertEqual(result["state"], "STRUCTURALLY_VALID")
        self.assertNotIn("AUTHENTICATED", result.values())

    def test_model_cannot_claim_sovereign_role_in_agent_card(self):
        no_data = {"state": "NO_DATA", "cause": "synthetic_fixture"}
        card = {
            "schema": A.CARD_SCHEMA, "fixture": True,
            "agent": {"id": "soberano", "name": "Synthetic", "kind": "rack-cli",
                      "route": "thread"},
            "contributor": "fixture", "model": no_data, "key": no_data,
            "requests": ["talk.write"], "conditions": no_data,
            "authority": A.CARD_AUTHORITY,
        }
        value = A.validate_card(card)
        self.assertEqual((value["state"], value["cause"]),
                         ("REJECTED", "agent_id_invalid_or_reserved"))


class JournalAccountingNotOwnerAuthentication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="owner-boundary-synthetic-")
        self.db = Path(self.tmp.name) / "journal.db"
        J.init_journal(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def kwargs(self, expires_at="2030-11-21T00:00:00Z"):
        return dict(db_path=self.db, grant_id="1" * 64, agent_id="fixture",
                    device_id="fixture-device", grant_sha256="2" * 64,
                    task_sha256="4" * 64, capability="owner-talk",
                    expires_at=expires_at,
                    now=dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc))

    def rows(self):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT COUNT(*) FROM journal").fetchone()[0]

    def test_direct_claim_is_not_signature_verification(self):
        # A known seam: journal accepts raw caller parameters. It must ONLY
        # be reached after an external, trusted signature/identity gate.
        self.assertEqual(A.validate_grant(
            grant(capability="owner-talk", scope=["turn"]))["state"], "REJECTED")
        self.assertEqual(J.claim_grant(**self.kwargs())["state"], "OK")
        self.assertEqual(self.rows(), 1)  # synthetic DB only

    def test_expired_grant_never_writes_a_claim(self):
        value = J.claim_grant(**self.kwargs("2026-11-20T11:59:59Z"))
        self.assertEqual(value["state"], "REJECTED")
        self.assertEqual(self.rows(), 0)

    def test_same_grant_id_replay_does_not_write_twice(self):
        self.assertEqual(J.claim_grant(**self.kwargs())["state"], "OK")
        value = J.claim_grant(**self.kwargs())
        self.assertEqual((value["state"], value["cause"]),
                         ("REJECTED", "grant_already_consumed"))
        self.assertEqual(self.rows(), 1)

    def test_revoked_before_use_cannot_be_claimed(self):
        self.assertEqual(J.revoke_grant(**self.kwargs())["state"], "OK")
        value = J.claim_grant(**self.kwargs())
        self.assertEqual((value["state"], value["cause"]),
                         ("REJECTED", "grant_revoked"))
        self.assertEqual(self.rows(), 1)

    def test_consumed_grant_does_not_supply_session_epoch(self):
        self.assertEqual(J.claim_grant(**self.kwargs())["state"], "OK")
        value = J.revoke_grant(**self.kwargs())
        self.assertEqual((value["state"], value["cause"]),
                         ("REJECTED", "grant_already_consumed"))
        self.assertEqual(self.rows(), 1)
