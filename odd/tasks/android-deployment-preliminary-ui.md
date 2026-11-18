# APP-ANDROID-DEPLOYMENT-PRELIMINARY-UI · Reviewable slice

**Owner:** Codex GPT-6 APP. **Base:** `7d75eb4` (merged APP #343). **Sources:** Mesa #3 #6986949900, #6988045368, BRAIN claim #6988066199, Aduana #32 (merged).

**Problem:** The old My node button appeared to send an unsigned cédula to `POST /api/v1/cedulas`, which requires sovereign-signed plan and matching cédula. HTTP422 and/or unverifiable receipt cannot be called REQUESTED, APPROVED or LIVE. Do not weaken the existing worker route.

**Existing/retained:** single APP (four-zone MINI), `interface/node_registration.js`, existing local `node_building.js`, signed cédula validator `createAduanaRequest / verifyAduanaReceipt`, WEB ephemeral Play visitor contract from Claude `atlas/doogee_node_chat.mjs`. Visitor account != durable Android identity.

**Adaptation:** My node has a purpose field, explicit consent and `Sign deployment · request review`. Local preview never POSTs or pretends to have a sovereign SSH signature; an Android-only injected bridge may later perform one operator-reviewed preliminary HTTPS request. No implicit WebView fetch or rack fallback. Unavailable bridge/reply => `NO_DATA(cause)` and zero LIVE. Current bridge ABI (proposed, not yet committed by BRAIN) is `PreceptorAndroidJoin.requestPreliminary({node,purpose,consent:true}): Promise<normalizedReceipt>`; native must validate exact HTTPS endpoint, Android confirmation, installation identity and real receipt against BRAIN fixtures. Arbitrary returned HTTP 200 or hash does not imply approval.

**Evidence classification:** `DRAFT_ONLY` for local request. `REQUESTED`/`PENDING` only after real native receipt validation. `REJECTED` requires operator decision proof. `APPROVED` requires human decision plus signed admission; `LIVE` additionally requires fresh authenticated heartbeat and independent WEB visibility. Same `data-state`, `data-acho`, `aria-live` message and preview JSON for eye/ear/machine. None of these view signals grants server rights.

**Measured gates and sabotages:** `node --test tests/android_deployment_ui_cases.cjs` and existing `test_node_registration.py`; full `./bin/pruebas --rapido` twice, hostile variants consent/receipt/live. Native install/HTTPS POST/real tracking/owner inbox/approval/LIVE each remain `NO_DATA` until a receipt is observed.

**Boundaries:** Junie owns `mvp-android/**` bridge, package and S110; BRAIN owns Aduana preliminary inbox/signature/heartbeat; OpenCode independent test-only slice cannot use production MCP. No merge, deploy or notification by an agent. Carbon signs exact-head PR and separately approves node/provisioning.
