"""Synthetic-only adversarial tests for agent-card and task-grant boundaries."""
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

import agentes_contrato as A
import cuenta_cangrejo as CC


@unittest.skipUnless(shutil.which("ssh-keygen"), "NO_DATA(ssh-keygen_unavailable)")
class AuthorizationContract(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-superbot-f1-"))
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
        shutil.rmtree(self.root)

    def _sign(self, payload, private=None, namespace=A.GRANT_NAMESPACE):
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

    def _evaluate(self, **changes):
        args = dict(card_raw=self.card_raw, grant_raw=json.dumps(self.grant, sort_keys=True, separators=(",", ":")).encode(), account=self.account,
                    message_signature=self.message_sig, signed_message=self.message,
                    allowed_signers=self.signers, agent_key_dir=self.key_dir,
                    task_bytes=self.task, capability="lab.propose", device_id="local-test",
                    conditions_bytes=b"accepted-test-conditions", now=self.now,
                    revoked_grant_ids=set(), consumed_grant_ids=set())
        args.update(changes)
        if "grant" in args:
            args["grant_raw"] = json.dumps(args.pop("grant"), sort_keys=True, separators=(",", ":")).encode()
        return A.evaluate_authorization(**args)

    def test_valid_card_is_only_a_declaration(self):
        self.assertEqual(A.parse_card(self.card_raw)["state"], "DECLARED")
        self.assertEqual(A.validate_card(self.card)["state"], "DECLARED")

    def test_valid_host_auth_and_signed_task_grant_are_eligible_but_not_dispatched(self):
        result = self._evaluate()
        self.assertEqual(result["state"], "ELIGIBLE_FOR_ATOMIC_CLAIM", result)
        self.assertEqual(result["task_sha256"], hashlib.sha256(self.task).hexdigest())
        self.assertEqual(result["grant_sha256"], hashlib.sha256(json.dumps(self.grant, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
        self.assertIn("no dispatch", result["note"])

    def test_card_cannot_self_grant_or_claim_reserved_identity(self):
        fake = dict(self.card, authority="authorized")
        self.assertEqual(A.validate_card(fake)["state"], "REJECTED")
        fake = json.loads(self.card_raw)
        fake["agent"]["id"] = "soberano"
        self.assertEqual(A.validate_card(fake)["state"], "REJECTED")

    def test_card_duplicate_keys_and_oversize_rejected(self):
        self.assertEqual(A.parse_card(b'{"schema":"x","schema":"y"}') ["state"], "REJECTED")
        self.assertEqual(A.parse_card(b" " * A.CARD_LIMIT)["cause"], "card_byte_limit")
        self.assertEqual(A.parse_grant(b'{"schema":"a","schema":"b"}') ["state"], "REJECTED")

    def test_untrusted_or_missing_identity_and_signature_fail_closed(self):
        result = self._evaluate(allowed_signers=self.root / "missing")
        self.assertEqual((result["state"], result["cause"]), ("NO_DATA", "authentication_trust_anchor_unavailable"))
        result = self._evaluate(message_signature="not-a-signature")
        self.assertEqual(result["state"], "REJECTED")
        wrong = json.loads(self.card_raw)
        wrong["key"]["public_hex"] = "f" * 64
        raw = json.dumps(wrong, separators=(",", ":")).encode()
        result = self._evaluate(card_raw=raw)
        self.assertEqual(result["cause"], "card_key_does_not_match_authenticated_account")

    def test_fixture_identity_cannot_authorize_runtime(self):
        card = json.loads(self.card_raw)
        card.update(fixture=True, key={"state": "NO_DATA", "cause": "fixture"})
        raw = json.dumps(card, separators=(",", ":")).encode()
        result = self._evaluate(card_raw=raw)
        self.assertEqual((result["state"], result["cause"]), ("REJECTED", "card_not_eligible_for_runtime"))

    def test_modified_task_card_hash_and_agent_identity_rejected(self):
        self.assertEqual(self._evaluate(task_bytes=self.task + b" ")["cause"], "grant_task_mismatch")
        self.assertEqual(self._evaluate(grant=self._grant(card_sha256="4" * 64))["cause"], "grant_card_or_agent_mismatch")
        self.assertEqual(self._evaluate(grant=self._grant(agent_id="other"))["cause"], "grant_card_or_agent_mismatch")

    def test_expired_revoked_and_replayed_grants_rejected(self):
        expired = self._grant(expires_at=(self.now - dt.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertEqual(self._evaluate(grant=expired)["cause"], "grant_expired")
        self.assertEqual(self._evaluate(revoked_grant_ids={self.grant["grant_id"]})["cause"], "grant_revoked")
        self.assertEqual(self._evaluate(consumed_grant_ids={self.grant["grant_id"]})["cause"], "grant_replayed_or_consumed")

    def test_capability_device_conditions_and_missing_confirmation_rejected(self):
        self.assertEqual(self._evaluate(capability="talk.write")["cause"], "grant_capability_not_requested_or_mismatched")
        self.assertEqual(self._evaluate(device_id="other-device")["cause"], "grant_device_mismatch")
        self.assertEqual(self._evaluate(conditions_bytes=b"different conditions")["cause"], "grant_conditions_mismatch")
        no_signature = dict(self.grant, signature="")
        self.assertEqual(self._evaluate(grant=no_signature)["cause"], "grant_signature_missing")
        false_confirmation = dict(self.grant, signature="invalid")
        self.assertEqual(self._evaluate(grant=false_confirmation)["cause"], "grant_signature_unverified")

    def test_model_authorization_fields_are_not_part_of_the_contract(self):
        injected = dict(self.grant, authorized=True)
        self.assertEqual(A.validate_grant(injected)["cause"], "grant_fields_invalid")

    def test_unknown_revocation_or_replay_state_blocks_eligibility(self):
        self.assertEqual(self._evaluate(revoked_grant_ids=None)["cause"], "grant_revocation_state_unavailable")
        self.assertEqual(self._evaluate(consumed_grant_ids=None)["cause"], "grant_replay_state_unavailable")


    def test_perceived_control_is_not_authority_to_invoke(self):
        # Synthetic semantic projection; never a real APP control or grant.
        control = {"id": "fixture-control", "visible": True, "enabled": True,
                   "authorized": True, "label": "Run fixture"}
        self.card["requests"] = ["talk.read"]
        self.card_raw = A.canonical_bytes(self.card)
        self.task = A.canonical_bytes({"action": "read", "control": control})
        read_grant = self._grant(capability="talk.read", scope=["talk.read"])
        positive = self._evaluate(grant=read_grant, capability="talk.read")
        self.assertEqual(positive["state"], "ELIGIBLE_FOR_ATOMIC_CLAIM", positive)
        self.assertIn("no dispatch", positive["note"])
        for operation in ("app.control.invoke", "talk.write", "lab.propose"):
            with self.subTest(operation=operation):
                denied = self._evaluate(grant=read_grant, capability=operation)
                self.assertEqual((denied["state"], denied["cause"]),
                                 ("REJECTED", "grant_capability_not_requested_or_mismatched"))
        altered = A.canonical_bytes({"action": "invoke", "control": control})
        denied = self._evaluate(grant=read_grant, capability="talk.read", task_bytes=altered)
        self.assertEqual((denied["state"], denied["cause"]),
                         ("REJECTED", "grant_task_mismatch"))

    def test_permission_expansion_requires_a_new_supported_contract(self):
        # A signature over a proposed scope is not enough to introduce it.
        for capability in ("app.control.invoke", "repo.deploy", "shell.execute"):
            with self.subTest(capability=capability):
                grant = self._grant(capability=capability, scope=[capability])
                self.assertEqual(A.validate_grant(grant)["cause"], "grant_scope_invalid")
                result = self._evaluate(grant=grant, capability=capability)
                self.assertEqual((result["state"], result["cause"]),
                                 ("REJECTED", "grant_scope_invalid"))
        widened = self._grant(scope=["lab.propose", "talk.write"])
        self.assertEqual(A.validate_grant(widened)["cause"], "grant_scope_invalid")


if __name__ == "__main__":
    unittest.main()
