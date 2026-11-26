"""Directed fixture tests for the local conversation cursor. No production data."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

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
                ("2026-11-26T00:00:00Z", "fixture", "mensaje", "codex",
                 raw if raw is not None else json.dumps(body), "[]")).lastrowid

    def page(self, **kw):
        return C.lee_pagina("orquesta", base=self.base, **kw)

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
                   {"max_bytes": 8193}):
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


if __name__ == "__main__":
    unittest.main()
