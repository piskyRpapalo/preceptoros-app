"""Pure R4 inspection specifications; no activation of the existing sender."""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import nodo_app
import nodo_export
import nodo_export_preview as P
from test_nodo_export import cedula, reseal


def raw(card=None):
    return json.dumps(cedula() if card is None else card, ensure_ascii=False, separators=(",", ":"))


def paths(card=None):
    result = P.preview(raw(card))
    return [r["path"] for r in result["fields"] if r["known"] and r["present"]]


class PureInspection(unittest.TestCase):
    def blocked(self, result, cause=None):
        self.assertFalse(result["export_allowed"])
        self.assertIsNone(result["transport"])
        self.assertFalse(result["may_operate"])
        self.assertEqual(result["authority"], "NOT_GRANTED")
        self.assertEqual(result["node_admission"], "NO_DATA")
        if cause:
            self.assertIn(cause, result["causes"])

    def test_S01_unselected_and_unconfirmed(self):
        result = P.preview(raw())
        self.blocked(result, "unselected_field")
        self.assertEqual(result["inspection"], "AVAILABLE")
        self.assertTrue(all(not r["selected"] for r in result["fields"]))

    def test_S02_claimed_consent_never_authorizes(self):
        for consent in (True, 1, "yes", {"authorized": True}, {"preview_ref": "self-claimed"}):
            with self.subTest(kind=type(consent).__name__):
                self.blocked(P.preview(raw(), paths(), consent=consent), "supplied_consent_not_authority")

    def test_S03_private_root_is_withheld_and_blocked(self):
        card = reseal(dict(cedula(), private_note="synthetic-private-marker"))
        result = P.preview(raw(card), paths(card))
        self.blocked(result, "unknown_field_blocked")
        encoded = json.dumps(result)
        self.assertNotIn("synthetic-private-marker", encoded)
        self.assertNotIn("private_note", encoded)
        self.assertTrue(any(not row["known"] for row in result["fields"]))

    def test_S04_nested_private_field_not_hidden_by_container_selection(self):
        card = cedula();card["dispositivos"][0]["private_note"] = "synthetic-nested-marker"
        card = reseal(card)
        result = P.preview(raw(card), paths(card))
        self.blocked(result, "unknown_field_blocked")
        self.assertNotIn("synthetic-nested-marker", json.dumps(result))
        self.assertIn("signed_field_not_selected", result["causes"])

    def test_S05_additional_device_requires_each_concrete_path(self):
        before = paths()
        card = cedula();card["dispositivos"].append({"clave": "d1"*32, "estado": "solicitado"})
        result = P.preview(raw(reseal(card)), before)
        self.blocked(result, "required_field_not_selected")
        self.assertFalse(next(r for r in result["fields"] if r["path"] == "/dispositivos/1/clave")["selected"])

    def test_S06_required_deselection_does_not_change_credential(self):
        card = cedula();source = raw(card)
        for name in ("/admin", "/nodo", "/plan_sha256", "/dispositivos/0/clave"):
            with self.subTest(path=name):
                result = P.preview(source, [p for p in paths(card) if p != name])
                self.blocked(result, "required_field_not_selected")
                self.assertEqual(raw(card), source)

    def test_S07_signed_optional_fields_stay_signed(self):
        card = cedula();card["dispositivos"][0].update(tipo="agente",ambito=["herramientas"],caduca="2026-11-14T13:00:00Z")
        card = reseal(card)
        selected = [p for p in paths(card) if p != "/dispositivos/0/caduca"]
        result = P.preview(raw(card), selected)
        self.blocked(result, "signed_field_not_selected")
        self.assertTrue(next(r for r in result["fields"] if r["path"] == "/dispositivos/0/caduca")["signed"])

    def test_S08_unsigned_metadata_is_still_digest_bound(self):
        result = P.preview(raw(), [p for p in paths() if p != "/autenticidad"])
        row = next(r for r in result["fields"] if r["path"] == "/autenticidad")
        self.assertFalse(row["signed"])
        self.assertTrue(row["credential_digest_covered"])
        self.blocked(result, "unselected_field")

    def test_S09_unknown_selection_never_approves_field(self):
        card = reseal(dict(cedula(), unknown="synthetic"))
        result = P.preview(raw(card), paths(card) + ["/unknown"])
        self.blocked(result, "selection_invalid")
        self.assertEqual(result["state"], "REJECTED")

    def test_S10_values_never_echo_even_in_known_optional_field(self):
        card = reseal(dict(cedula(), firma="synthetic-sensitive-marker"))
        result = P.preview(raw(card), paths(card))
        self.blocked(result, "disclosure_policy_unresolved")
        self.assertNotIn("synthetic-sensitive-marker", json.dumps(result))
        self.assertTrue(all(r["display"] == "withheld" for r in result["fields"]))

    def test_S11_paths_are_exact_not_coerced_or_expanded(self):
        for selection in (["/admin", "/admin"], ["/dispositivos/*"], ["/dispositivos/00/clave"],
                          ["/dispositivos/3/clave"], ["/аdmin"], [True], {"/admin": True}, "all"):
            with self.subTest(kind=type(selection).__name__):
                self.blocked(P.preview(raw(), selection), "selection_invalid")

    def test_S12_empty_container_remains_visible_and_selectable(self):
        card = reseal(dict(cedula(), dispositivos=[]))
        result = P.preview(raw(card), paths(card))
        self.blocked(result)
        row = next(r for r in result["fields"] if r["path"] == "/dispositivos")
        self.assertEqual(row["kind"], "array")
        self.assertTrue(row["selected"])
        self.assertTrue(row["required"])

    def test_S13_payload_tamper_with_old_digest_rejected(self):
        card = cedula();card["admin"] = "d1"*32
        self.blocked(P.preview(raw(card)), "credential_shape_or_integrity_invalid")

    def test_S14_resealed_changed_credential_requires_new_preview(self):
        old = P.preview(raw(), paths())
        card = reseal(dict(cedula(), nodo="nodo.2.other"))
        result = P.preview(raw(card), paths(card), expected_ref=old["preview_ref"])
        self.blocked(result, "preview_binding_mismatch")

    def test_S15_selection_recipient_and_generation_binding(self):
        old = P.preview(raw(), paths())
        changed = P.preview(raw(), [], expected_ref=old["preview_ref"])
        self.blocked(changed, "preview_binding_mismatch")
        self.blocked(P.preview(raw(), paths(),generation=1,expected_ref=old["preview_ref"]), "preview_binding_mismatch")
        self.blocked(P.preview(raw(), recipient="https://fixture.invalid/elsewhere"), "context_invalid")
        self.blocked(old, "disclosure_policy_unresolved")
        self.assertEqual(old["binding"]["policy_state"], "UNRESOLVED")

    def test_S16_raw_input_immutable_and_result_mutation_is_not_authority(self):
        source = raw();first = P.preview(source, paths())
        first["export_allowed"] = True
        first["binding"]["selected_paths"].clear()
        second = P.preview(source, paths())
        self.blocked(second)
        self.assertTrue(second["binding"]["selected_paths"])
        self.assertEqual(source, raw())

    def test_S17_local_revocation_blocks(self):
        old = P.preview(raw(), paths())
        result = P.preview(raw(), paths(), revoked=True,expected_ref=old["preview_ref"])
        self.blocked(result, "consent_revoked")
        self.blocked(result, "preview_binding_mismatch")
        self.assertEqual(result["consent_state"], "REVOKED")

    def test_S19_revoked_device_is_not_admitted(self):
        card = cedula();card["dispositivos"][0]["estado"] = "revocado";card = reseal(card)
        result = P.preview(raw(card), paths(card))
        self.blocked(result, "revoked_record_action_unresolved")
        self.assertEqual(result["node_admission"], "NO_DATA")

    def test_S20_revocation_notice_policy_not_invented(self):
        self.blocked(P.preview(raw(), paths(), purpose="revocation_notice"), "revocation_notice_policy_unresolved")

    def test_S21_MH01_and_CONNECTED_are_not_consent_or_node_identity(self):
        for packet in ({"schema":"preceptoros.device-capability/1","identity":{"verified":True},"authorization":"ATTESTED"},
                       {"state":"CONNECTED"}, {"observed_at":"2026-10-01T00:00:00Z","lease":"historical"}):
            self.blocked(P.preview(raw(), paths(), consent=packet), "supplied_consent_not_authority")

    def test_S22_self_hash_does_not_verify_signature(self):
        result = P.preview(raw(), paths())
        self.blocked(result, "signature_not_verified")
        self.assertEqual(result["signature_state"], "NOT_VERIFIED")

    def test_S23_clean_fully_selected_is_inspectable_but_policy_blocked(self):
        result = P.preview(raw(), paths())
        self.blocked(result, "disclosure_policy_unresolved")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertNotIn("unselected_field", result["causes"])
        self.assertTrue(all(r["selected"] for r in result["fields"]))
        self.assertNotIn("cedula", result)

    def test_S24_repeat_preview_and_old_consent_do_not_create_authorization(self):
        self.assertEqual(P.preview(raw(),paths()),P.preview(raw(),paths()))
        self.blocked(P.preview(raw(),paths(),consent={"receipt":"replayed"}),"supplied_consent_not_authority")

    def test_S25_preview_is_not_an_exportable_credential_or_receipt(self):
        result = P.preview(raw(),paths())
        calls = []
        r = nodo_export.enviar({"cedula":result},transport=lambda *a:calls.append(a))
        self.assertEqual(r["codigo"],"cedula_rechazada")
        self.assertEqual(calls,[])

    def test_S26_bounded_parser_duplicate_keys_and_nonfinite_numbers(self):
        bad = (b'\xff', '{} '*30000, '[]', '{"a":1,"a":2}', '{"a":NaN}',
               '['*20+'0'+']'*20, {"not":"serialized bytes"}, '"scalar"', '{"a":Infinity}')
        for value in bad:
            with self.subTest(kind=type(value).__name__):
                result = P.preview(value)
                self.blocked(result)
                self.assertEqual(result["state"], "REJECTED")

    def test_fingerprints_match_existing_exporter_and_signed_body(self):
        c = cedula();result = P.preview(raw(c),paths(c))
        body = json.dumps({"cedula":c},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        self.assertEqual(result["binding"]["transport_payload_ref"],"sha256:"+hashlib.sha256(body).hexdigest())
        self.assertEqual(result["binding"]["signed_payload_ref"],"sha256:"+hashlib.sha256(nodo_app.cuerpo_firmado(c)).hexdigest())
        sha_row = next(r for r in result["fields"] if r["path"]=="/sha256")
        self.assertFalse(sha_row["signed"])
        self.assertFalse(sha_row["credential_digest_covered"])

    def test_missing_receiver_fields_visible_and_blocked(self):
        c = cedula();del c["admin"];c=reseal(c)
        result=P.preview(raw(c))
        self.blocked(result,"required_field_missing")
        self.assertFalse(next(r for r in result["fields"] if r["path"]=="/admin")["present"])

    def test_node_bound_and_unknown_nested_scalar(self):
        c = reseal(dict(cedula(),private_array=list(range(600))))
        self.assertEqual(P.preview(raw(c))["state"],"REJECTED")
        c = reseal(dict(cedula(),autenticidad={"private":"synthetic-marker"}))
        r = P.preview(raw(c),paths(c))
        self.blocked(r,"unknown_field_blocked")
        self.assertNotIn("synthetic-marker",json.dumps(r))

    def test_context_values_not_coerced(self):
        for kwargs in ({"generation":True},{"generation":-1},{"revoked":1},{"expected_ref":"bad"},{"purpose":"admit"}):
            self.blocked(P.preview(raw(),**kwargs),"context_invalid")

    def test_escaping_whitespace_and_braces_in_strings_are_deterministic(self):
        c=reseal(dict(cedula(),autenticidad='synthetic " [ { \\ marker'))
        a=P.preview(raw(c),paths(c))
        b=P.preview(json.dumps(c,indent=2),list(reversed(paths(c))))
        self.assertEqual(a,b)

    def test_inspection_has_no_files_network_clock_or_signer_side_effects(self):
        source=raw();selection=paths()
        with patch('builtins.open',side_effect=AssertionError('no file reads')), \
             patch('socket.socket',side_effect=AssertionError('no network')), \
             patch('subprocess.Popen',side_effect=AssertionError('no process')), \
             patch.object(nodo_app,'autenticidad',side_effect=AssertionError('no signer')), \
             patch.object(nodo_export,'enviar',side_effect=AssertionError('no transport')):
            result=P.preview(source,selection)
        self.blocked(result)


if __name__ == '__main__':
    unittest.main()
