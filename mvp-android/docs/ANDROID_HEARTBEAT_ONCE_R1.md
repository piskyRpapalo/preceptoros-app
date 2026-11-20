# APP · NODE-BIRTH-PREFLIGHT / Android one-shot heartbeat R1

**Source:** APP main at `179f98f20fbec91efa040c0f9289475ca814ecb2`; Aduana `docs/nonanchor-admission-contract.md`, `src/index.js::registraLatido` at Aduana main `34e1de0`. S110's v7 installation does **not** include this proposed code. Keep user data installed; do not claim an APK update or public node.

## Problem and reuse

APP already has `DeploymentJoinBridge` / `DeploymentRequestPolicy`: its owner-controlled `POST /api/v1/deployment-requests` yields only `AWAITING_HUMAN`. Aduana already has the single authenticated `POST /api/v1/latidos` and public `GET /api/v1/latidos`; `scripts/f1_heartbeat.py` implements a Python/Termux one-shot sender. Android lacks a **native** emission path. No second service, signed-identity authority, ledger, model or credential issuer is introduced.

## Native piece

- `HeartbeatOncePolicy.java`: exact ASCII canonical 4-field `preceptoros.latido/1`; node `nodo.*`, monotonic nonnegative safe integer, UTC, 1024-B request, SHA-256 and exact server receipt check; no client LIVE verdict.
- `HeartbeatOnceBridge.java`: WebViewAssetLoader origin + main frame + verified APP page; Android system picker `ACTION_OPEN_DOCUMENT` (owner selects local application/json file), followed by an **independent native confirmation**. No JS key, broad filesystem grant, silent network, background timer/daemon, new endpoint, URL supplied by JS, HTTP downgrade or redirects. POST is HTTPS-only fixed `https://api.preceptoros.org/api/v1/latidos` with existing `x-heartbeat-key`. The raw key is used in memory for that one send only, **not** in logs/JS/SharedPreferences. Per-node next sequence is reserved durably **before** a send; no optimistic rewind after a failed POST. A server 200/202 with matching payload digest and receipt digest can show `RECEIVED`; all other results fail closed.
- `android_heartbeat_bridge.js`: Android-only button after existing My node request form; minimum 44px, keyboard click, `role=status`, `aria-live=polite`, `data-state`, `data-cause`, `data-acho` with matching visible text. No key or node ID supplied by JS. `RECEIVED` explicitly prints `NO_DATA(public_live_not_independently_verified)` and `authority=NONE`.
- This is a **one-shot** sender, not a periodic process. It neither signs the cédula nor grants property. Aduana must already have independently verified human decision, signed plan + cédula, canonical `node_requests` link, operator-provisioned per-node key hash window and map cell. Otherwise the Worker rejects.

### Owner-controlled credential transport (not a signing contract)

A local file selected by the human has exactly three fields:

```json
{"schema":"preceptoros.heartbeat-key-local/1","node":"nodo.42.contributor","key":"<64 lower-case hexadecimal characters provided privately by the authorized operator>"}
```

The placeholder is **not valid**. The selected file is under the owner's chosen Android document provider and **remains there**; Android APP does not copy or retain it. The owner/operator must secure and later revoke/delete it in the chosen provider. Java String memory does not guarantee zeroization: `NO_DATA(JVM_secret_zeroization)`. Do not share real key with LAB, GitHub, ChatGPT, Acho, app browser or public screenshots.

## Required independent first-node E2E — NOT EXECUTED BY THIS PR

1. Owner on S110 chooses identity and confirms review; measure actual `AWAITING_HUMAN` receipt after Aduana deploy and D1 reconciliation.
2. Sovereign reviews, signs SSHSIG decision, plan and cédula, separate from the Android app; approved and verified rows observed. Provision fresh 24-hour credential hash and canonical cell; independent consent and revocation plan.
3. Authorized operator delivers owner-only credential; S110 installs a **new signed APK** with same package/signing identity, preserving existing data. User selects file and explicitly confirms one heartbeat. Native verifies 200/202 receipt and exposes `RECEIVED`, not LIVE.
4. Another browser independently checks public `GET /api/v1/latidos`, matching node/cell and `LIVE` (<300 seconds), then stale expiry and revocation; separately prove one real local-model response with LAB provenance. Acho must report same observable state as visual and machine representations.
5. Only these receipts justify `VERIFIED(node_birth_E2E)`. Until then: `NO_DATA(owner_device_human_consent_or_public_live_unmeasured)`.

## Source / production caveats

- Aduana Worker D1 preflight from existing #36: migration ledger empty although schema tables already exist; public deployment request GET returns 404, **not proof of POST**. Do not run unreviewed migration, SQL write, Worker deploy or owner POST.
- One-shot sequence starts at 0 for each new APP install/node; if server has previous sequences after reinstall, 409 is fail-closed, requires owner/operator reconciliation. Skipped sequence on failed request is permissible, not delivery proof.
- Server receipt is digest-bound over fixed HTTPS, **not** an independent signed public observer. The public World reader remains independent.
- The chosen Android provider may retain the raw key. Future key protection can be layered on the existing Android Keystore if owner-approved; do not pretend this first piece has KeyStore secrets.
- No autonomous periodic send. The human must initiate each test.

## Gates and judge

`python3 -B -m unittest -q test_android_heartbeat_once` (pure Java cross-language golden vectors + synthetic Android JS state) ×2; `ANDROID_HOME=/home/pisky/android-sdk ./mvp-android/gradlew :app:compileDebugJavaWithJavac --offline --no-daemon` from `mvp-android` ×2; existing join tests ×2 and `./bin/pruebas` as available. Faro/C reviews exact-head, forges, cross-node sequences, fail-closed, owner-consent semantics. The human FIRMO and real device trial remain separate gates.
