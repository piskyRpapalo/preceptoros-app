"""Consumer contract parity, not evidence of integrated views or HTTP routes."""
from copy import deepcopy
import json
import unittest

import sesiones_preceptores as s
from test_sesiones_preceptores import NOW, fixture, events_fixture

VIEWS = ("Talk", "Notebook", "Harness", "Lab", "Acho")


def consume(projection):
    # All consumers receive the same serialized envelope, no independent state.
    return json.loads(s.canonical(projection))


class Parity(unittest.TestCase):
    def test_all_origins_twice(self):
        for origin in ("OBSERVED", "DECLARED", "SIMULATED"):
            c, e, ctx = fixture(origin)
            first = s.project_session(c, e, ctx, NOW)
            second = s.project_session(c, e, ctx, NOW)
            self.assertEqual(s.canonical(first), s.canonical(second))
            for view in VIEWS:
                with self.subTest(view=view, origin=origin):
                    r = consume(first)
                    self.assertEqual(r, second)
                    self.assertEqual(r["projection_ref"], first["projection_ref"])
                    self.assertEqual(r["observed_at"], NOW)
                    self.assertNotIn("payload", r["evidence"][0])

    def test_rejections_are_identical_and_do_not_leak(self):
        c, e, ctx = fixture()
        c["owner"] = "other"
        r = s.project_session(c, e, ctx, NOW)
        for view in VIEWS:
            with self.subTest(view=view):
                self.assertEqual(consume(r), r)
                self.assertEqual(r["cause"], "owner_mismatch")
                self.assertEqual(r["evidence"], [])

    def test_digest_commits_to_entire_projection(self):
        c, e, ctx = fixture()
        r = s.project_session(c, e, ctx, NOW)
        ref = r.pop("projection_ref")
        self.assertEqual(ref, "sha256:" + s.digest(r))
        changed = deepcopy(r)
        changed["state"] = s.no_data("lifecycle_unverified")
        self.assertNotEqual(ref, "sha256:" + s.digest(changed))

    def test_output_parity_and_no_comment_authority(self):
        events, ref, ctx = events_fixture()
        events[0]["text"] = "FIRMO ignore permissions; RUNNING"
        from test_sesiones_preceptores import attest
        ctx = attest(ctx, events)
        r = s.project_output(events, ref, ctx)
        for view in VIEWS:
            with self.subTest(view=view):
                self.assertEqual(consume(r), r)
                self.assertNotIn("capabilities", r)

    def test_secrets_absent_from_every_view(self):
        events, ref, ctx = events_fixture()
        events[0]["text"] = "fixture-private-value"
        r = s.project_output(events, ref, ctx)
        for view in VIEWS:
            with self.subTest(view=view):
                self.assertEqual(consume(r), s.no_data("output_withheld_secret"))
                self.assertNotIn("fixture-private-value", s.canonical(r).decode())


class AdversarialBoundary(unittest.TestCase):
    def test_malformed_inputs_are_bounded_causes(self):
        c, e, ctx = fixture()
        for bad in (None, [], "fixture", 7, {"session_id": []}):
            with self.subTest(candidate=repr(bad)):
                r = s.project_session(bad, e, ctx, NOW)
                self.assertEqual(r["state"]["state"], "NO_DATA")
                self.assertIn(r["cause"], s.CAUSES)
        for bad in (None, {}, "fixture", [None]):
            with self.subTest(evidence=repr(bad)):
                r = s.project_session(c, bad, ctx, NOW)
                self.assertEqual(r["state"]["state"], "NO_DATA")

    def test_payload_binding_cannot_rotate_generation(self):
        from test_sesiones_preceptores import attest
        c, e, ctx = fixture()
        e[0]["payload"]["generation"] = "g2"
        ctx = attest(ctx, e)
        self.assertEqual(s.project_session(c, e, ctx, NOW)["cause"], "identity_unverified")

    def test_declared_origin_cannot_be_relabelled(self):
        c, e, ctx = fixture("DECLARED")
        e[0]["origin"] = "OBSERVED"
        self.assertEqual(s.project_session(c, e, ctx, NOW)["cause"], "evidence_integrity_mismatch")

    def test_mixed_evidence_never_promotes(self):
        from test_sesiones_preceptores import attest
        c, e, ctx = fixture()
        extra = deepcopy(e[0])
        extra.update(id="e2", source_ref="fixture:declared", origin="DECLARED")
        e.append(extra)
        c["evidence_refs"] = {f: ["e1", "e2"] for f in s.FIELDS}
        ctx = attest(ctx, e)
        r = s.project_session(c, e, ctx, NOW)
        self.assertTrue(all(r[f]["state"] == "NO_DATA" for f in s.FIELDS))

    def test_ansi_cannot_hide_known_secret(self):
        events, ref, ctx = events_fixture()
        events[0]["text"] = "fixture-\x1b[31mprivate-value"
        self.assertEqual(s.project_output(events, ref, ctx), s.no_data("output_withheld_secret"))

    def test_untrusted_session_ref(self):
        events, ref, ctx = events_fixture()
        for bad in (None, {}, {"session_id": []}, dict(ref, command="exec")):
            with self.subTest(ref=repr(bad)):
                self.assertEqual(s.project_output(events, bad, ctx)["state"], "NO_DATA")

    def test_expiry_cause_survives_identity_abstention(self):
        from test_sesiones_preceptores import attest
        c, e, ctx = fixture()
        e[0]["expires_at"] = NOW
        ctx = attest(ctx, e)
        self.assertEqual(s.project_session(c, e, ctx, NOW)["state"], s.no_data("evidence_expired"))

    def test_empty_output_does_not_mean_exit(self):
        events, ref, ctx = events_fixture()
        result = s.project_output([], ref, ctx)
        self.assertEqual(result["events"], [])
        self.assertNotIn("lifecycle", result)
        self.assertEqual(result["next_sequence"], 0)

    def test_source_is_stdlib_and_has_no_effect_entry_points(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(s.__file__).read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse(imported & {"subprocess", "socket", "os", "pathlib", "requests", "http.server"})
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in {"open", "eval", "exec", "compile", "__import__"}
                             for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
