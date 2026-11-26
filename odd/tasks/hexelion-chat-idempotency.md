# Direct Hexelion Talk idempotency and recoverable waiting

Status: ready for independent review

## Objective

Make the active APP private-Talk path safe to retry when the browser loses its response or the user stops waiting. A repeated submission of the same logical turn must not append a second question or invoke the model/action adapter twice.

## Why

The served shell loads `interface/app.js` from `interface/app.html`; the separate `interface/hexelion.js` surface is not the active Talk path. The active form posts directly to `/api/hexelion/chat`.

The existing `canales.di_soberano` idempotency contract covered addressed messages with `para`, but the direct Hexelion station path has no recipient. A browser-side network failure therefore left an ambiguous outcome and a retry could create duplicate work.

## Sources

- Repository law: `AGENTS.md`, declared depth 2; `study/08-ai-fluency.md`, `study/05-contracts.md`, and `study/10-collisions.md`.
- Active commission and coordination: Mesa #63, CLAIM `7181408965`; APP-PUENTE / VISOR-HEXELION lane context.
- Code evidence on APP main `56930aa55dbe89872b6001be265b378c82dad75f`: `interface/app.html` loads `app.js?v=58`; `interface/app.js` owns the active Talk form; `canales.py` stores append-only turn receipts; `bin/preceptoros-pwa` owns `/api/hexelion/chat`.
- `version.py` already hashes `interface/app.html`, `interface/app.js`, and `interface/sw.js`; no separate version-manifest edit is required.

## Adaptation to the existing system

- Extend the existing append-only `canales` ledger to accept an opaque `request_id` for direct, unaddressed person turns.
- Bind the idempotency fingerprint to the submitted text and the execution context (selected panel and agent). Same ID with changed inputs is a conflict.
- On duplicate request, read the original turn and its correlated receipt. Return the bounded cached model answer, verified action receipt, or explicit PENDING/NO_DATA. Never call inference or an action adapter again.
- Use `AbortController` in the active `app.js` request and an accessible, nine-locale “Stop waiting” control. Abort only the browser wait; it does not claim to cancel server inference.
- Retain the same request ID in page memory for same-input retry. Within that page session, different text/panel/agent is held until the previous outcome is reconciled; after a full reload this guard is not yet restored automatically.
- Align `app.css` and `app.js` cache keys with the `sw.js` shell cache (app.css/app.js v59 / shell v251).

## Measurable benefit

- One request ID produces at most one durable question and one model/action invocation.
- Same-ID replay returns the existing result or PENDING without a second invocation.
- Same-ID/different-input returns 409.
- Tests count first append, replay, conflict, and no-second-inference behavior.
- The UI can stop waiting without discarding the correlation key.

## Risks and limits

- Browser abort does not stop the server-side inference.
- The client retains the pending ID in page memory; a full reload does not yet restore that client-side key automatically. The durable question and request ID remain in the existing ledger.
- Cached local sensor detail is not reconstructed when its full receipt is unavailable; the route returns NO_DATA rather than fabricating a reading.
- Live Hexelion E2E is not established. Read-only local Ollama `GET /api/tags` listed `qwen38-27b-q4xl:latest`, `qwen3-coder-next:latest`, `qwen3-coder:30b`, and `gpt-oss:120b`; the code default `hexelion:latest` was absent. `GET /api/ps` returned an empty model list. The configured `PRECEPTOROS_HEXELION_MODEL` override and SHA pin were not exposed, so the active selection remains NO_DATA. No live model response or deployment is claimed.
- No new database, MCP, endpoint, daemon, relay, scheduler, service, grant, or dispatch path is introduced.

## Checklist

- [x] HXI-01 Identify the active APP Talk path; exclude the legacy `hexelion.js` surface.
- [x] HXI-02 Add no-recipient request IDs and context-bound idempotency to the existing ledger.
- [x] HXI-03 Reconcile duplicate requests from existing receipts without rerunning work.
- [x] HXI-04 Add active Talk request ID, browser cancellation, and localized stop-waiting control.
- [x] HXI-05 Align app.css/app.js cache keys and service-worker shell version.
- [x] HXI-06 Add ledger, PWA replay, conflict, pending, and UI contract tests.
- [x] HXI-07 Pass the certified repository gate on code HEAD `730f6296f2844124de328a0c2ef32a8d26620496` (5/5 Python matrix).
- [ ] HXI-08 Obtain independent D review; keep merge/deploy as separate governed decisions.

## Verification evidence

- Draft PR: https://github.com/piskyRpapalo/preceptoros-app/pull/437
- Branch: `codex-web/app-hexelion-idempotent-chat-20261126`
- Base: `56930aa55dbe89872b6001be265b378c82dad75f`
- CI run #45749336667 on code head `d6f249dc`: FAIL across the Python 3.10–3.14 matrix; 27 failing corridors. Corrected served asset/cache alignment, public-name inventory, focus restoration path count, and a docstring collision detected by the repository gate.
- CI run #45750510481 on code head `897a4cc8`: FAIL across the matrix; 8 remaining suites. These isolated stale asset/cache snapshots (including the install-worker fixture) and the additional draft-restoration branch; all identified expectations were updated in the current branch.
- CI run #45751255147 on exact code HEAD `730f6296f2844124de328a0c2ef32a8d26620496`: PASS on Python 3.10, 3.11, 3.12, 3.13 and 3.14; each reports `VERDE · 2798/2798`. `test_canales.py` 20/20, `test_pwa.py` 112/112, `test_canales.py --sabotaje` 6/6 detected, public-name sabotage 2/2 detected. All five workflow jobs concluded success.
- This feature-record update is documentation-only; the tested code remains exactly the code at `730f6296`. Independent D review is still pending; no merge/deploy claim.

## Log

2026-11-26 — Codex GPT-6.2 Web (`codex-web`) recovered the APP-PUENTE context read-only, published CLAIM `7181408965`, implemented the bounded idempotency/cancellation slice, and opened draft PR #437. No merge, deploy, service restart, model load, or CLI session creation.

## Next step

Run `./bin/pruebas` on the exact PR head, reconcile every skip/NO_DATA, and request independent D review. Only then return the exact-head evidence to NEXO for FAN-IN.
