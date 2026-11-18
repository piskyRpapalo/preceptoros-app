# APP-ANDROID-JOIN-CLIENT-01 · Aduana intake contract

**Owner:** APP orchestration · Codex GPT-6. **Base:** APP `b713240`.
**Standing scope:** build, isolated tests and reviewable PR only; exact-head human FIRMO gates merge. Android install, network submission, live admission and public release have separate gates.

## Existing components to reuse

- Four-zone MINI in `mvp-android`; `interface/node_registration.js` is the existing UI/client, not a second router.
- Aduana `piskyRpapalo/aduana` `origin/main=5f58d76677149518db72866504fa55c2a8436fe0`, `src/index.js`: `POST /api/v1/cedulas`, `preceptoros.cedula-nodo/1` and `preceptoros.recibo-cedula/1`.
- Existing `test_node_registration.py` covers a historic local **stub** and its unsupported proposed transport. Preserve that evidence; do not call its result a real Aduana receipt.

## Client contract built in this slice

`createAduanaRequest` requires an owner-supplied node ID, admin SHA-256 and signed-plan SHA-256, with bounded devices and a string SSH signature (empty means unsigned intake). It hashes ASCII-escaped canonical JSON exactly as Aduana does. It never manufactures an admin, plan, key or signature.

`aduanaAdapter` has no ambient `fetch` fallback. A separate native, owner-approved HTTPS transport must be injected. Strict consent, size, hash and response validation precede a pending state. The returned `recibo_sha256` proves internal receipt integrity, **not** a Sovereign signature or server authenticity. HTTP 200 may mean idempotent replay; `verificado` is not independently proven carbon APPROVED or public LIVE.

## State/evidence hierarchy

1. DRAFT: generated locally, not submitted.
2. SUBMITTED/PENDING: only after HTTP 200/202 with a matching Aduana receipt, exact node/admin/plan digests and internally valid receipt SHA.
3. APPROVED: **NO_DATA(carbon_approval_contract_not_handed_off)**; never inferred from HTTP or cédula hash.
4. LIVE: **NO_DATA(public_heartbeat_AND_visibility_not_verified)**; requires BRAIN heartbeat proof and WEB public observation.

Acho must render the same state and cause in visual, spoken and machine-readable channels. Personal MINI never inherits rack permissions. The native bridge must block all WebView internet fetches and allow only the explicitly consented HTTPS Aduana POST; permission INTERNET is capability, not blanket permission.

## Coordination and measurable gates

- Source: Mesa #3 comment #6986949900; BRAIN fixtures requested in Mesa #47 comment #6987091277.
- Junie packaging assignment: Mesa #3 comment #6987079122. Her active worktree is not touched.
- Test: `python3 -m unittest -q test_android_join_contract test_node_registration test_android_admission_policy` plus `node --test tests/android_join_contract_cases.cjs`. Repeat full `./bin/pruebas --rapido` twice.
- Native transport/APK/install/real receipt/approval/LIVE remain blocked on exact Brain fixture, Junie build and separate owner-authorized physical installation. Report each as `NO_DATA(cause)` rather than simulated success.
