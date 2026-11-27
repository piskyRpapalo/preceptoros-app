"""Directed fixture tests for the local conversation cursor. No production data."""
import hashlib
import json
import math
import os
import sys
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from contextlib import closing

import canal_event as E
import canales as C


class ConversationCursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.db = C.ruta_canal(self.base)
        self.db.parent.mkdir()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.executescript(C.ESQUEMA_EVENTOS)

    def append(self, thread="orquesta", text="fixture", machine=None, raw=None):
        body = {"hilo": thread, "texto": text, "rol": "fixture",
                "sello": "DECLARADO", "maquina": machine or {}}
        with closing(sqlite3.connect(self.db)) as con, con:
            return con.execute(
                "insert into eventos (ts,maquina,tipo,actor,cuerpo_json,no_data_json)"
                " values (?,?,?,?,?,?)",
                ("2026-11-27T00:00:00Z", "fixture", "mensaje", "codex",
                 raw if raw is not None else json.dumps(body, ensure_ascii=False), "[]")).lastrowid

    def page(self, **kw):
        return C.lee_pagina("orquesta", base=self.base, **kw)

    def shared_anchor(self):
        anchor = hashlib.sha256(b"shared-event-fixture").hexdigest()
        raw = json.dumps({
            "version": 1, "ancla": anchor, "utc": "2026-11-27T00:00:00Z",
            "sello": "LIVE", "payload": {"kind": "shared-reference"},
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertLessEqual(len(raw), E.MAX_EVENT_BYTES)
        self.assertEqual(E.validate_event(raw)["ancla"], anchor)
        return anchor

    def test_reconnect_without_loss_over_legacy_window(self):
        expected = []
        for i in range(225):
            expected.append(self.append(text=str(i)))
            if i % 7 == 0:
                self.append(thread="lab", text="not in scope")
        cursor, got = 0, []
        for _ in range(225):
            p = self.page(cursor=cursor, limite=13)
            self.assertEqual(p["estado"], "MEDIDO")
            got.extend(m["n"] for m in p["mensajes"])
            if not p["complete"]:
                self.assertGreater(p["next_cursor"], cursor)
            cursor = p["next_cursor"]
            if p["complete"]:
                break
        else:
            self.fail("cursor did not finish")
        self.assertEqual(got, expected)
        self.assertEqual(self.page(cursor=cursor)["mensajes"], [])
        new = self.append()
        self.assertEqual(self.page(cursor=cursor)["next_cursor"], new)

    def test_bounds_and_scope(self):
        self.append(thread="lab")
        n = self.append(machine={"request_id": "app-" + "a" * 32,
                                 "request_fingerprint": "not exported",
                                 "private": "not exported"})
        p = self.page()
        self.assertEqual(p["next_cursor"], n)
        self.assertEqual(p["authority"], "none")
        self.assertEqual(p["mensajes"][0]["identity"], "DECLARED")
        self.assertEqual(set(p["mensajes"][0]["maquina"]), {"request_id"})
        for kw in ({"cursor": True}, {"cursor": -1}, {"cursor": 2**63},
                   {"limite": 0}, {"limite": 21}, {"max_bytes": 1023},
                   {"max_bytes": 8193}, {"conversation_id": True},
                   {"conversation_id": ""}, {"expected_ledger_id": "bad"}):
            with self.subTest(kw=kw), self.assertRaises(C.CanalRechazado):
                self.page(**kw)

    def test_utf8_budget_and_no_silent_skip(self):
        first = self.append()
        second = self.append(text="蟹" * 500)
        p = self.page(max_bytes=1024)
        self.assertEqual(p["next_cursor"], first)
        self.assertFalse(p["complete"])
        self.assertLessEqual(len(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode()), 1024)
        blocked = self.page(cursor=first, max_bytes=1024)
        self.assertEqual((blocked["estado"], blocked["causa"], blocked["next_cursor"]),
                         ("NO_DATA", "message_exceeds_budget", first))
        self.assertEqual(self.page(cursor=first)["next_cursor"], second)

    def test_corrupt_row_is_a_barrier(self):
        first = self.append()
        self.append(raw="{")
        self.append()
        self.assertEqual(self.page()["next_cursor"], first)
        p = self.page(cursor=first)
        self.assertEqual((p["estado"], p["causa"], p["next_cursor"]),
                         ("NO_DATA", "channel_row_invalid", first))

    def test_missing_db_never_created(self):
        self.db.unlink()
        self.assertEqual(self.page()["causa"], "channel_has_no_messages")
        self.assertFalse(self.db.exists())

    def test_read_does_not_mutate_ledger(self):
        self.append()
        before = self.db.read_bytes()
        self.page()
        self.assertEqual(self.db.read_bytes(), before)

    def test_conversation_scopes_share_only_the_ancla_reference(self):
        anchor = self.shared_anchor()
        a1 = self.append(machine={"conversation_id": "conv-a", "ancla": anchor,
                                  "private_payload": "must not cross the cursor"}, text="A1")
        b1 = self.append(machine={"conversation_id": "conv-b", "ancla": anchor}, text="B1")
        a2 = self.append(machine={"conversation_id": "conv-a", "ancla": anchor}, text="A2")
        b2 = self.append(machine={"conversation_id": "conv-b", "ancla": anchor}, text="B2")

        a = self.page(conversation_id="conv-a", limite=20)
        b = self.page(conversation_id="conv-b", limite=20)
        self.assertEqual([m["n"] for m in a["mensajes"]], [a1, a2])
        self.assertEqual([m["n"] for m in b["mensajes"]], [b1, b2])
        self.assertEqual(a["conversation_id"], "conv-a")
        self.assertEqual(b["conversation_id"], "conv-b")
        self.assertEqual(a["mensajes"][0]["maquina"],
                         {"conversation_id": "conv-a", "ancla": anchor})
        self.assertEqual(b["mensajes"][0]["maquina"],
                         {"conversation_id": "conv-b", "ancla": anchor})
        self.assertNotIn("private_payload", json.dumps(a, ensure_ascii=False))
        self.assertNotIn("payload", json.dumps(a, ensure_ascii=False))
        self.assertEqual(a["ledger_id"], b["ledger_id"])

    def test_unclassifiable_scoped_row_blocks_without_advancing(self):
        first = self.append(machine={"conversation_id": "conv-a"}, text="valid")
        self.append(machine={"conversation_id": 7}, text="invalid scope")
        self.append(machine={"conversation_id": "conv-a"}, text="after barrier")
        p = self.page(conversation_id="conv-a")
        self.assertEqual(p["next_cursor"], first)
        blocked = self.page(conversation_id="conv-a", cursor=first)
        self.assertEqual((blocked["estado"], blocked["causa"], blocked["next_cursor"]),
                         ("NO_DATA", "channel_row_invalid", first))

    def test_three_clients_resume_100_messages_without_loss_or_duplicates(self):
        expected = []
        for i in range(60):
            expected.append(self.append(machine={"conversation_id": "conv-live"},
                                        text=f"message-{i:03d}"))
            if i % 4 == 0:
                self.append(machine={"conversation_id": "conv-other"}, text=f"other-{i:03d}")

        # These are synthetic client labels, not authenticated physical devices.
        clients = {
            "beelink": {"cursor": 0, "ledger_id": None, "received": []},
            "tank3": {"cursor": 0, "ledger_id": None, "received": []},
            "s110": {"cursor": 0, "ledger_id": None, "received": []},
        }

        def read_pages(client, stop_after=None):
            samples = []
            pages = 0
            while True:
                kwargs = {"cursor": client["cursor"], "limite": 7,
                          "conversation_id": "conv-live"}
                if client["ledger_id"] is not None:
                    kwargs["expected_ledger_id"] = client["ledger_id"]
                started = time.perf_counter_ns()
                page = self.page(**kwargs)
                samples.append((time.perf_counter_ns() - started) / 1_000_000)
                self.assertEqual(page["estado"], "MEDIDO", page)
                if client["ledger_id"] is None:
                    client["ledger_id"] = page["ledger_id"]
                self.assertEqual(page["ledger_id"], client["ledger_id"])
                client["received"].extend(m["n"] for m in page["mensajes"])
                if not page["complete"]:
                    self.assertGreater(page["next_cursor"], client["cursor"])
                client["cursor"] = page["next_cursor"]
                pages += 1
                if page["complete"] or (stop_after is not None and pages >= stop_after):
                    break
            return samples

        with ThreadPoolExecutor(max_workers=3) as pool:
            first_pass = [
                pool.submit(read_pages, clients["beelink"], 2),
                pool.submit(read_pages, clients["tank3"], 4),
                pool.submit(read_pages, clients["s110"], 1),
            ]
            samples = [value for future in first_pass for value in future.result()]

        # One append-only writer adds the remaining messages while all clients
        # are disconnected. Each client resumes from its own delivered cursor.
        for i in range(60, 100):
            expected.append(self.append(machine={"conversation_id": "conv-live"},
                                        text=f"message-{i:03d}"))
            if i % 4 == 0:
                self.append(machine={"conversation_id": "conv-other"}, text=f"other-{i:03d}")

        with ThreadPoolExecutor(max_workers=3) as pool:
            resumed = [pool.submit(read_pages, clients[name])
                       for name in ("beelink", "tank3", "s110")]
            samples.extend(value for future in resumed for value in future.result())

        for name, client in clients.items():
            with self.subTest(client=name):
                self.assertEqual(client["received"], expected)
                self.assertEqual(len(client["received"]), 100)
                self.assertEqual(len(set(client["received"])), 100)
                final = self.page(cursor=client["cursor"], conversation_id="conv-live",
                                  expected_ledger_id=client["ledger_id"])
                self.assertEqual(final["mensajes"], [])
                self.assertTrue(final["complete"])
                self.assertEqual(final["next_cursor"], client["cursor"])

        ordered = sorted(samples)
        p50 = ordered[(len(ordered) - 1) // 2]
        p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]
        print("LOCAL_CURSOR_LATENCY_MS clients=3 messages=100 pages=%d p50=%.3f p95=%.3f max=%.3f" %
              (len(ordered), p50, p95, ordered[-1]), file=sys.stderr, flush=True)

    def test_ledger_identity_survives_appends_and_rejects_replacement(self):
        first = self.append()
        initial = self.page()
        ledger_id = initial["ledger_id"]
        self.assertEqual(initial["next_cursor"], first)
        self.append()
        same = self.page(cursor=first, expected_ledger_id=ledger_id)
        self.assertEqual(same["estado"], "MEDIDO")
        self.assertEqual(same["ledger_id"], ledger_id)

        replacement = self.db.with_name("replacement.db")
        with closing(sqlite3.connect(replacement)) as con, con:
            con.executescript(C.ESQUEMA_EVENTOS)
        os.replace(replacement, self.db)

        stale = self.page(cursor=first, expected_ledger_id=ledger_id)
        self.assertEqual((stale["estado"], stale["causa"], stale["next_cursor"]),
                         ("NO_DATA", "cursor_ledger_mismatch", first))
        fresh = self.page()
        self.assertNotEqual(fresh["ledger_id"], ledger_id)


if __name__ == "__main__":
    unittest.main()
