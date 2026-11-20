# RETOMA DEL CEREBRO · Shared Rack LAB in APP · 2026-11-20

**Single mission:** [Mesa privada #51 · RETOMA DEL CEREBRO](https://github.com/piskyRpapalo/preceptoros-private-mesa/issues/51).
**Owner:** Codex GPT-6 (Olin), exclusive internal rack lane. The other ChatGPT orchestrator owns WEB graphics. This is implementation evidence, NOT a new mission.

## Problem / measured source

The existing owner's rack-local APP server already exposes existing Rack LAB sources:
- GET /api/notebook: command receipts, WBR/MBR, benchmark receipts.
- GET /api/harness: timers configured in Nexo.
- GET /api/federado: LAB node registry metadata.
- GET /api/hexelion/tareas: NO_DATA(p2_mirror_not_built).
- GET /api/lab-rack: local LAB HTML health, NOT process liveness.

Local GET readings on 2026-11-20: twenty command receipts, two bench runs, 14 timer records, ten registry entries, six backend entries, **zero observed agent heartbeats**. Absence of an agent census is NO_DATA, not proof no workers exist.

The Documents editor stores personal drafts in browser localStorage **per device**. It does not share them, and this proposal does not silently synchronize them.

The native owner-device WebView loads https://preceptoros.mvp.local with assets bundled inside the APK: it does NOT inherit the rack-origin API automatically.

### Tailnet security warning

Tailscale Serve /→8742 returns HTTP200 for /api/notebook, /api/federado and /api/lab when requested from an already connected Linux tailnet peer. /api/lab/github and /api/lab-rack reject that peer with HTTP403. This is **not public Internet exposure**, but tailnet membership alone is not a signed APP-owner grant. Do not export any additional private content or node identities, keys, raw prompts or command text.

## Minimal reuse built

- Operations Data / Documents gains a read-only Shared Rack LAB · Results subsection, outside the browser-local document editor.
- Existing notebook.js benchmark receipts from ONE /api/notebook response feed the existing renderer in both Lab and Operations Data; there is no new memory store, polling service, index, RAG or remote endpoint.
- Existing /api/harness source is summarized using projectHarness and its five-minute freshness ceiling. Timer records and declared-enabled flags are NOT running workers.
- Process/goal liveness stays NO_DATA(live_process_binding_missing), visibly and in data-state/cause/acho, until a verified PID-to-task binding exists.
- Fetch stays same-origin and no-store; the SW caches the shell only, never the API.
- Shell cache revision v237, notebook.js?v=24; no seventh MVP panel.
- Existing voice/Acho/visual/machine summaries share the same source semantics, without inventing physical speech E2E.

## Next stages to reach two real Android owners

1. Review exact-head APP PR, CI, browser preview and SW revision. A branch is not a deployed app.
2. Use existing native WebViewAssetLoader patterns to build an owner-approved read-only bridge with a pinned HTTPS endpoint, scoped authenticated grant, no arbitrary URL from JS and secrets retained outside WebView. Mere Tailscale presence is not permission.
3. Reuse LAB P2 ReadOnlyMirror and execution journal with independent host witness. Bind a measured live PID to a task ref and its exact receipt; do not infer process-live from a heartbeat, timer or model roster.
4. Keep browser Documents personal drafts local. Deliver LAB receipt references through the same Operations Data view; any synchronization of edited documents needs separate owner consent and signed policy.
5. Verify independently on the rack and two owner Android devices: same approved LAB source revision + digest, proper stale/revocation refusals, accessibility text/audio/machine parity. Until APK native release is measured, NO_DATA(Android_native_shared_LAB).
6. Model launcher, harness configuration and node registration are separate future APP privileges; this slice grants none.

## Gates / rollback

Run node tests/notebook_cases.cjs, python3 -m unittest test_notebook_read and APP ./bin/pruebas twice, then Chrome preview. Exact-head CI and human FIRMO govern merge. The original Lab and Notebook views remain unmodified in semantics. Rollback is previous shell cache; browser-local personal documents remain untouched.

**NO_DATA:** Android native owner bridge, process-to-task witness, 24/7 process progress, authenticated three-device receipt parity, APK delivery, voice on devices.

— Codex GPT-6 (Olin), 2026-11-20. Human chat HITL acknowledged; no fabricated exact-head signature.
