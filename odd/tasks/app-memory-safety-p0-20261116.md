# APP Memory Safety P0 · 2026-11-16

**Base:** `1fdd525cf509f7623c2db3400993d20948d7e7e7` (`origin/main`).
**Scope:** `bin/preceptoros-pwa`, `test_pwa.py`, this receipt.

## P0-A · `/api/estado` is a read only probe

Before fix, `_estado()` called `M.abrir()` and `C.recuento()`. `M.abrir()` can create a missing file and set WAL mode; `C.recuento()` calls `C.asegurar()`, which creates/migrates the `turnos` table. The RED fixtures confirmed missing-file creation and writes/migration of an unrelated SQLite file. A fresh database with no initialized memory was reported as ordinary `ok`.

Now the route checks the existing file through SQLite `mode=ro&immutable=1` and `query_only`. A non-empty WAL is returned as `UNKNOWN / memory_wal_snapshot_unavailable`, rather than ignored as stale or opened in a way that creates sidecars. It classifies:

- `MISSING / memory_db_unavailable_file_missing` (keeps the route's existing cause namespace; `memoria_estado` carries the precise classification)
- `UNINITIALIZED / memory_schema_absent` for valid SQLite with no app schema
- `READY` for recognized memory schema; legacy memory without optional `profile` remains readable, and an absent `turnos` table is reported as zero rather than created
- `UNKNOWN / memory_schema_unrecognized` for other valid databases or incompatible schemas
- `CORRUPT / memory_database_invalid`
- A non-empty WAL is `UNKNOWN / memory_wal_snapshot_unavailable`; the endpoint does not ignore potentially committed WAL frames or create SQLite sidecars to read them.
- The main DB and WAL identity are checked before and after the immutable read. If either changes during the read, the result is `UNKNOWN / memory_changed_during_read`.

No repair or migration occurs during status reads.

## P0-B · shared local Origin guard

Before fix, a loopback peer with matching attacker-controlled `Host` and `Origin` was accepted, including arbitrary DNS hostnames, HTTPS, and a mismatched port. The helper now requires a loopback peer, an allowed literal host (`localhost`, `127.0.0.1`, `[::1]`), HTTP, exact host/origin match and the running APP port. Existing real local form is preserved. This is origin validation, not user authentication.

## Tests / evidence

- RED before production edits: P0-A isolated class reported 3 assertion failures + 2 missing-state errors, showing create/migrate and missing classifications; P0-B isolated cases reported 3 failures for rebinding hostname, HTTPS, and wrong port.
- Directed P0-A/P0-B + existing node boundary + missing-memory consumer regression: 16/16 PASS ×2 (includes a WAL appearing between snapshot inspection and SQLite connect).
- Full `python3 -B -m unittest test_pwa -q`: 107 PASS ×2.
- `./bin/pruebas`: 2,124/2,124 tests, 176 suites, 6 corridors, PASS ×2. Each pass reports 10 skips. Causes: WEB source absent in this checkout (1); guarded test lexicon absent (1); privacy sentinel not mounted (1); external T1/GitHub source lookup returned not found, so hashes/source were not read (6); and no external source for the declaration-status test (1). These tests were skipped, not counted as repaired or passing integrations.
- All seven existing full-gate sabotage groups were detected ×2 (47 detections per pass). The first pre-compatibility gate was RED only on the legacy missing-memory cause assertion; preserving the established cause prefix made the consumer test pass.
- Sabotage A: removed `immutable=1`; the READY-memory regression caught new `-wal/-shm` sidecars (failed as expected), then clean suite passed.
- Sabotage B: added `attacker.example` to the local-host allowlist; the DNS-rebinding regression failed as expected, then clean directed tests passed.
- Sabotage C: injected a WAL between the pre-read snapshot and SQLite connect; the new race test returned `UNKNOWN / memory_changed_during_read` and verified unchanged main DB and WAL bytes.
- Final `git diff --check`: PASS after the final source and receipt changes.

## Compatibility with APP #315 and #316

Both open drafts touch `bin/preceptoros-pwa` but in separate functional additions: #315 adds memory onboarding routes/guard, #316 adds Plan Store routes/guard. The narrowed helper contract remains compatible with both guards' loopback host/origin checks; `/api/estado` stays independent of their write paths. This branch does not edit either worktree. At the compatibility check, #315 is `DIRTY/CONFLICTING` against main (head `701f78b7bc84006a7f8589912b9526f5cf438bac`, based at `ddf4d873de20520d92f47b9267b77c3be2e82478`); #316 is `MERGEABLE` only against its stacked base #312 (head `cea0496f177649e55f5fc255a8c3b64cf715376a`). Intended order: exact-head review/merge this safety PR first; Claude resolves/rebases #315 onto the resulting main and repeats its gates ×2; only then reconcile #316's stack against its required #312/#314 dependencies and retest. No cross-PR E2E is claimed.

## Limits

`NO_DATA(memory_state_during_nonempty_wal)` is deliberate: an immutable read cannot safely claim it saw committed data still in a WAL. `NO_DATA(physical_APP_service_after_merge)`; no server restart or deploy was performed. Host/Origin validation does not authenticate an agent or grant a capability.
