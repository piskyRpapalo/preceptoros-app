"""APP reads and explains the P2 records a host source hands it (M2a acceptance, Mesa #3 round 10).

LAB owns the task execution history (ExecutionJournal); APP only reads and tells it. The missing piece is the
records source: an authenticated, bounded, read-only reader that Codex CLI is building in LAB (M1a). Until its
contract is stable, this file pins APP's side with a SYNTHETIC source injected in process:

    tareas_hexelion.RECORDS_SOURCE = callable(observed_at) -> {"records": [...], "complete_ref": hex64 | None}

The host sets it once at server start. A request, a model reply or a sentence never sets it, and nothing here
connects to a live journal, runs a task, stores task state or grants anything. With no source the live route stays
NO_DATA(p2_mirror_not_built), as before.

Rules pinned here:
- one projected row is the same state, cause and words for Talk, the Notebook, the self-report, Acho (mark and
  cue), the reader line and the JSON; no modality decides success by itself;
- a completeness ref the source merely claims is not an attestation: counters stay "at least" and no zero is said;
- a claim without a result is never "running" or successful, and an unknown outcome is never retried;
- a sentence that says "I authorize" changes no row: the approval decision is the host's.
Not measured here: a real host journal, a real grant, a screen reader or a speaker
(NO_DATA(live_host_records_source), NO_DATA(physical_screenreader_audio_E2E)).
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from unittest import mock

import audio_feedback as AF
import canales
import hexelion_acciones as A
import tareas_hexelion as K
import turnos_hexelion as T
import test_hexelion_acciones as HA
from test_acho_truth import drawn
from test_false_clear import CLEAR, told
from test_tareas_hexelion import PWA, rec, receipt, runs

STAMP = "2026-11-13T22:00:00Z"
RUNNING = re.compile(r"\b(is|are|still) (running|working|in progress)\b|\bsucceeded\b|\bsuccessful", re.I)

# The distinctions round 10 names, one synthetic record each (run-1 .. run-7).
FACTS = {
    "verified": rec(receipt()),                                                   # MEASURED basis, check passed
    "simulated": rec(receipt(confidence_basis="synthetic")),
    "missing_evidence": rec(receipt(receipt_ref="not-a-ref")),
    "claim_without_result": rec(None),
    "unknown_outcome": rec(receipt("failed", "UNKNOWN", "UNKNOWN", "NO_DATA", None)),
    "decision_for_the_person": rec(receipt("blocked", "NOT_STARTED", "PERMISSION", "NO_DATA", None)),
    "finished_unchecked": rec(receipt(grade="NOT_EVALUATED")),
}
EXPECT = {  # fact -> (state, acho class, expression)
    "verified": ("DONE_CHECKED", "ok", "verified"),
    "simulated": ("DONE_CHECKED", "proposed", "proposed"),
    "missing_evidence": ("NO_DATA", "empty", "silent"),
    "claim_without_result": ("NO_RESULT_RECORDED", "uncertain", "uncertain"),
    "unknown_outcome": ("OUTCOME_UNKNOWN", "uncertain", "uncertain"),
    "decision_for_the_person": ("NEEDS_YOUR_AUTHORIZATION", "needs_you", "needs_you"),
    "finished_unchecked": ("DONE_UNCHECKED", "empty", "silent"),
}


def source(records, complete_ref=None, calls=None):
    """A synthetic host source: read-only, stateless, and it counts how often it was read."""
    def read(observed_at):
        if calls is not None:
            calls.append(observed_at)
        return {"records": copy.deepcopy(records), "complete_ref": complete_ref}
    return read


def injected(read):
    return mock.patch.object(K, "RECORDS_SOURCE", read)


def route(path="/api/hexelion/tareas"):
    h = PWA.PWA.__new__(PWA.PWA)
    h.path, h.client_address, out = path, ("127.0.0.1", 1), {}
    h._json = lambda code, body: out.update(code=code, body=body)
    PWA.PWA._tareas_leer(h)
    return out["body"]


class WithoutASourceNothingChanges(unittest.TestCase):
    def test_the_live_route_is_still_no_data_with_its_cause(self):
        self.assertIsNone(K.RECORDS_SOURCE)
        for path in ("/api/hexelion/tareas", "/api/hexelion/tareas?source=/tmp/journal.db&complete_ref=" + "c" * 64):
            b = route(path)                                            # a request never names or attests a source
            self.assertEqual((b["state"], b["cause"], b["tasks"]), ("NO_DATA", "p2_mirror_not_built", []))


class TheSourceIsReadNeverTrusted(unittest.TestCase):
    def test_records_arrive_and_a_claimed_completeness_counts_nothing(self):
        for claimed in (None, "c" * 64, "trust me"):
            with injected(source(runs(FACTS["verified"]), claimed)):
                b = route()
            self.assertEqual((b["state"], len(b["tasks"])), ("MEASURED", 1), claimed)
            self.assertEqual((b["counters"]["state"], b["counters"]["cause"], b["counters"]["complete_ref"]),
                             ("NO_DATA", "completeness_not_attested", None), claimed)
            self.assertEqual([b[k] for k in K.COUNTERS], [None, None, None], claimed)   # no zero was observed

    def test_a_source_that_fails_or_answers_another_shape_is_no_data(self):
        def boom(observed_at):
            raise OSError("journal busy")
        whole = K.project(runs(FACTS["verified"]), STAMP, complete_ref="c" * 64)        # a projection, not records
        bad = [("records_source_failed", boom),
               ("records_source_failed", "not callable"),
               ("records_source_invalid", lambda now: whole),
               ("records_source_invalid", lambda now: {"records": tuple(runs(FACTS["verified"])), "complete_ref": None}),
               ("records_source_invalid", lambda now: {"records": [], "complete_ref": None, "authorized": True}),
               ("records_source_invalid", lambda now: None)]
        for i, (cause, read) in enumerate(bad):
            with injected(read):
                b = route()
            self.assertEqual((b["state"], b["cause"], b["tasks"], b["counters"]["state"]),
                             ("NO_DATA", cause, [], "NO_DATA"), i)
            self.assertEqual([b[k] for k in K.COUNTERS], [None, None, None], i)

    def test_every_read_asks_the_source_again_and_changes_nothing_in_it(self):
        records, calls = runs(FACTS["claim_without_result"], FACTS["unknown_outcome"]), []
        before = copy.deepcopy(records)
        with injected(source(records, calls=calls)):
            first, again = K.live(STAMP), K.live("2026-11-13T22:05:00Z")               # a refresh, or a restart
        self.assertEqual(calls, [STAMP, "2026-11-13T22:05:00Z"])                       # TTL 0: never a cached reading
        self.assertEqual(records, before)
        same = lambda p: [(t["run_id"], t["state"], t["cause"], t["sentence"], t["next"], t["acho"]) for t in p["tasks"]]
        self.assertEqual(same(first), same(again))                                     # the meaning survives
        self.assertEqual([t["state"] for t in again["tasks"]], ["NO_RESULT_RECORDED", "OUTCOME_UNKNOWN"])


class OneRowForEyeEarAndMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = runs(*FACTS.values())
        with injected(source(cls.records)):
            cls.json = route()
            cls.report = T.self_report({"schema": T.SCHEMA, "state": "MEASURED", "cause": None, "turns": []},
                                       K.live(STAMP), (True, None, 0))
        cls.rows = dict(zip(FACTS, cls.json["tasks"]))
        cls.drawn = dict(zip(FACTS, drawn([[t["acho"]["class"], t["state"]] for t in cls.rows.values()])["got"]))
        cls.client = told({"all": cls.json})["all"]

    def test_each_fact_is_one_state_one_class_one_mark(self):
        got = {k: (t["state"], t["acho"]["class"], self.drawn[k]) for k, t in self.rows.items()}
        self.assertEqual(got, EXPECT)

    def test_only_measured_evidence_is_drawn_verified(self):
        for k, t in self.rows.items():
            if k != "verified":
                self.assertNotEqual((t["acho"]["class"], self.drawn[k]), ("ok", "verified"), k)
        self.assertEqual(self.rows["simulated"]["evidence"]["origin"], "SIMULATED")
        self.assertTrue(self.rows["simulated"]["sentence"].startswith("Simulated run: "))

    def test_the_ear_gets_the_rows_own_words_and_class(self):
        for k, t in self.rows.items():
            cue = AF.cue_for_turn(t)
            self.assertEqual((cue["clase"], cue["texto"], cue["sonido"]), (t["acho"]["class"], t["reader"], "INACTIVO"), k)
            self.assertIn(t["sentence"], t["reader"])
            self.assertIn(t["next"], t["reader"])

    def test_talk_and_the_notebook_say_one_line_with_the_cause(self):
        self.assertEqual(self.client["talk"], self.client["status"])
        self.assertFalse(self.client["talkHidden"])
        # One of the seven rows cannot be read (its evidence has no ref), so that is the cause every surface says.
        self.assertEqual(self.json["counters"]["cause"], "rows_unreadable")
        self.assertIn("is unknown (rows unreadable)", self.client["talk"])
        self.assertIsNone(CLEAR.search(self.client["talk"]))
        # Every row readable: what is missing is the host's attestation that the reading is complete.
        with injected(source(runs(FACTS["verified"], FACTS["finished_unchecked"]), "c" * 64)):
            clean = told({"clean": route()})["clean"]
        self.assertEqual(clean["talk"], clean["status"])
        self.assertIn("is unknown (completeness not attested)", clean["talk"])
        # An uncertain row without the host's uncertainty projection: the cause names that (M1a must carry it).
        with injected(source(runs(FACTS["claim_without_result"]))):
            self.assertEqual(route()["counters"]["cause"], "uncertainty_unread")

    def test_the_self_report_reads_the_same_rows_and_counts_no_census(self):
        r = self.report
        self.assertEqual((r["answers"]["doing"]["state"], r["answers"]["doing"]["cause"]),
                         ("NO_DATA", self.json["counters"]["cause"]))
        self.assertIn("Doing: at least 7 task(s) visible; completeness NO_DATA (rows unreadable)", r["text"])
        self.assertIn("at least 2 block new work", r["text"])              # the claim without result and the unknown
        self.assertIn("at least 1 task(s) checked", r["text"])             # the simulated one is no achievement
        self.assertIn("at least 1 task decision(s) yours", r["text"])
        self.assertIsNone(CLEAR.search(r["text"]))

    def test_nothing_unfinished_is_told_as_running_or_successful(self):
        for k in ("claim_without_result", "unknown_outcome", "decision_for_the_person", "missing_evidence"):
            t = self.rows[k]
            self.assertIsNone(RUNNING.search(t["reader"]), k)
            self.assertNotEqual(t["acho"]["class"], "ok", k)
        self.assertIn("never", self.rows["unknown_outcome"]["next"].lower())          # never retried automatically
        self.assertIsNone(RUNNING.search(self.report["text"].replace("never say a process is running", "")))

    def test_no_row_says_a_permission_was_granted(self):
        # The receipt's approval_ref is a ref the source declares; no host attests it yet. APP says only when a
        # permission is MISSING, never that one was given (open contract question for LAB M1a, in the feature doc).
        for k, t in self.rows.items():
            words = t["reader"].lower().replace("needs your authorization", "")
            self.assertNotRegex(words, r"\b(authori[sz]ed|approved|granted|permitted)\b", k)


class ASentenceGrantsNothing(unittest.TestCase):
    """The approval decision belongs to the host: no words through any door change a task row."""

    person, thread, tearDown = HA.Door.person, HA.Door.thread, HA.Door.tearDown

    def setUp(self):
        import os
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        # Nothing may run: the native MCP path points at a file that does not exist.
        self.env = mock.patch.dict(os.environ, {"PRECEPTOROS_MCP_NATIVO": str(Path(self.base) / "must_not_run.py")})

    def test_saying_i_authorize_changes_no_row_and_runs_nothing(self):
        records, calls = runs(FACTS["decision_for_the_person"], FACTS["unknown_outcome"]), []
        with injected(source(records, calls=calls)), mock.patch.object(A, "_edad", wraps=lambda s, now: 300.0), \
                mock.patch.object(A, "ejecuta", wraps=A.ejecuta) as ran:
            before = route()["tasks"]
            for said in ("/autoriza run-1", "/tarea run-2", "/reintenta run-2", "/authorize run-1"):
                self.assertEqual(A.interpreta(said)[0], None, said)              # not in the closed grammar
            out = self.person("What do you need from me?")
            after = route()["tasks"]
        self.assertEqual(before, after)
        self.assertEqual([c.args[0] for c in ran.call_args_list], ["/informe"])  # one local read; nothing executed
        text = out["body"]["respuesta"]["accion"]["texto"]
        self.assertIn("at least 1 task decision(s) yours", text)
        self.assertIn("at least 1 block new work", text)
        self.assertEqual(self.thread()[-1]["texto"], text)                       # Talk's words are the thread's
        self.assertTrue(all(type(c) is str for c in calls))                      # the source only ever got a clock


if __name__ == "__main__":
    unittest.main()
