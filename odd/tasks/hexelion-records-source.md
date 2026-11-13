# APP reads the records a host source hands it (M2a · synthetic source)

THE MARCH feature document · Claude Code · 2026-11-13. Cell A, round 10 (Mesa #3 #issuecomment-6867741447).
**Stacked on the self-report branch** (`claude/hexelion-self-report-r9-20261113`, `16e6228`), because it tests the
report too. Local only: not pushed, no PR. Its base is re-derived from `main` after the self-report merges.

**LAB owns the P2 task history. APP reads it and explains it.** Scope: the P2 catalogue only. `/ejecuta` stays a
separate path through the native MCP, so this does not make all Hexelion execution one truth.

## What was added

- **One seam:** `tareas_hexelion.RECORDS_SOURCE`, a callable `(observed_at) -> {"records", "complete_ref"}`.
  `live()` asks it on every read (never cached). With no source, `live()` is `NO_DATA(p2_mirror_not_built)`, as before.
- **Who sets it:** the host, once, when the server starts. No request, model reply or sentence can. Nothing in the
  product sets it: only the test launcher `tests/pwa_synthetic_records.py` does, for a synthetic fixture file.
- No route, served asset, database, grammar entry, worker or permission was added.

## Rules (pinned in `test_records_source`, 12 tests)

- **One row for every reader.** Talk, the Notebook, the self-report, the Acho mark, the cue text and the JSON carry
  the same state, cause and words for each of seven facts: verified, simulated, missing evidence, claim without
  result, unknown outcome, a decision for the person, finished unchecked.
- **Only MEASURED evidence is drawn verified.** A simulated result is `proposed`.
- **A completeness ref the source states about itself counts nothing.** It is not passed on: counters stay
  "at least" and no zero is said (`completeness_not_attested`).
- **A source that fails or answers another shape is NO_DATA** (`records_source_failed`, `records_source_invalid`).
- **A claim without a result is never "running" or successful. An unknown outcome is never retried.**
- **A sentence grants nothing.** "/autoriza", "/tarea", "/reintenta" are not in the grammar; asking the report
  runs one local read and changes no row.
- **No row says a permission was given.** APP says only when one is missing.

## Measured

| | Before (`16e6228`) | After |
|---|---|---|
| `test_records_source` | 6 errors (no seam) | 12/12 pass ×2 |
| Directed suites | 446 | 458 OK ×2, 1 skip |
| Browser sequence `tests/records_source.browser.cjs` (headless Chrome, own server, throw-away HOME) | not present | PASS ×2, 9 checks |

The browser sequence: a request is recorded; no permission yet; a known result (verified `ok`, simulated
`proposed`); a claim without a receipt said as unknown (Acho uncertain, dashed line); a refresh and a server
restart keep the same words, cards and rows; the source file's bytes are unchanged and no task file was written;
one live region on screen; no control on a task row; the task cue is off with and without motion.

Observed, not changed: with motion allowed, the panel sting (`interface/sting.js`) opens one audio context.

## For the LAB M1a contract (what `tareas_hexelion.project` accepts today)

| Point | APP today | Question for M1a |
|---|---|---|
| Record keys | only `run_id`, `task_sha256`, `receipt`, `replayed`, `uncertainty`; any other key makes the row NO_DATA | will `records()` add keys? |
| `run_id` | `^[a-z][a-z0-9-]{0,31}$`, once per reading; a repeated id makes every copy NO_DATA | same label rule in the journal? |
| Receipt | `preceptoros.meta-receipt/1`; `receipt_ref` hex64; `confidence_basis` known; `run_id` and `task_sha256` equal the record's | unchanged? |
| Uncertain rows | need the host's `uncertainty-ack/1` projection read within 5 s; without it the counters say `uncertainty_unread` | will each uncertain record carry it? |
| Window | the first 12 records; more gives `records_beyond_window` | which 12 come first? Unresolved ones must, or APP cannot show what blocks |
| Completeness | a ref from the source is ignored | what binds the whole snapshot, its completeness and the host generation, checkable by someone other than the source? |
| Source's own cause | the source can only raise, so LAB's cause (WAL present, not allowlisted) becomes `records_source_failed` | return `state` and `cause` so APP can say LAB's cause |
| Permission | `approval_ref` is a ref the source declares; no field says who attested it | how will an attested grant differ from a declared one? |
| Clock | the source receives APP's `observed_at` | LAB's mirror wants the host's trusted clock: who supplies it? |

## NO_DATA

- A live host journal, a real grant, the 8742 service: `NO_DATA(live_host_records_source)`. Connecting any of them
  is a separate decision of the Sovereign.
- A screen reader in use and sound heard: `NO_DATA(physical_screenreader_audio_E2E)`.
- `./bin/pruebas` ×2 on this head: not run yet (the gate is busy with the self-report and the seed).
