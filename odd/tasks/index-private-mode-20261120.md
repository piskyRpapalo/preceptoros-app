# APP-INDEX-PRIVATE-01 · Rack index producer privacy invariant

**Owner:** APP source builder · **scope:** only `indice_rack.py::construir` and its existing `test_hexelion_shelf.py` suite.

The index at the owner's selected path includes preceptor memory and repo/PR sources. On Linux, `sqlite3.connect()` on an absent file creates it with effective process umask. On a host configured with permissive umask, private index contents can become readable by other local accounts. The first protected SCOUT-19 run correctly reported `NO_DATA(index_invalid_or_inaccessible)` when the index inode was observed as 0644.

**Source-level change:** pre-create the **temporary SQLite file** with `os.open(..., O_CREAT|O_EXCL|O_NOFOLLOW, 0600)` before connecting, then preserve the existing atomic `tmp.replace(db)` semantics. This makes the privacy requirement independent of a systemd override. This code never changes network access, index data, FTS schema, benchmarks or the APP UI.

**Evidence gates:** existing index tests with deterministic source fixtures and two new cases: index creation under umask 0002, and safe replacement of an existing 0644 old DB under umask 0022, both yielding 0600; existing index readback still works. Full `bin/pruebas --rapido` ×2 before PR merge.

**Rack containment:** the user-systemd `preceptoros-indice.service` has a local `UMask=0077` drop-in and current index was regenerated 0600; keep it until source code reaches the actual running producer. No private indexed text is included in the PR. Past access by other users is `NO_DATA(access_logs_not_verified)`; the measured defect was permissions, not demonstrated exfiltration.

**Human signature:** propose-only PR; requires exact-head HITL. No automatic deploy, deletion, credentials or changes to another user's hardware.
