# PreceptorOS APP · Android Ronda 2 · Reconciled release candidate

- **Owner:** Soberano · **Author:** Codex GPT-6 · **Status:** BUILT AND SIGNED; NOT PUBLISHED.
- Base APP main: `10468550201463c7bafaf9fcf947b3ea5b3dd698` (PR #349 + #350 included).
- Delta: import **Android-only** changes from PR #351, no visual re-merge or second app. Android-specific `offline_mini.js` now uses `tab-cuaderno` for the six-panel shell.
- Product: **PreceptorOS**; model component: **Mini Orchestrator / SmolLM2-135M-Instruct Q4_K_M**. No LoRA, RAG, Hexelion weights, private rack configs, creds or admin rights.
- Package: `org.preceptoros.app`, versionName `0.3.0-mvp`, versionCode **7**. First release build SHA `a828059dba8bb3ffe327a93639442ab2fa64615d303f1705b93f9abb3ecde447`; sealed second build SHA **`9c4d227db2ba395cdb232bdd3eb6a52f83d344f3386a99bb5274d42837eebe6b`**; both 155,998,639 bytes, 160 equal ZIP entries. Signed APK bytes may vary due to signature block. **Cert SHA-256** `16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f` (owner signing config).
- Model SHA256 `ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747`; native JNI SHA256 `c167d707308b734013e7bd01ab5e8fdda08e05e4c2ad2fb2436f8124902d1504`.
- Local sealed asset: `~/sesiones/preceptoros-android-final-main-20261119/PreceptorOS-android-0.3.0-v7.apk` (0400, private; not Git-tracked). **Do not commit APK/GGUF/.so/keystore**. Owner certificate, license and zip assets verified locally.

## Installation and rollback gate

1. Verify exact APK digest/cert/version **before distribution and again after download**. The user first downloads from their own Android network, not the LAN address.
2. Read current device package and certificate on S110/Tank3. Do **not** overwrite a package with mismatched signing cert or equal/higher versionCode. Back up user preferences and the original APK before attempting `adb install -r`.
3. Preserve existing installations; install using `adb install -r <verified-file>` only with connected-owner/physical-lane clearance. Never `pm clear` or uninstall simply to make the upgrade pass.
4. Verify first launch, six tabs, onboarding, Mini native Talk output, Node identity, offline operation, preferences after force-stop/reopen; repeat twice; record sanitized receipts, no personal device identifiers.
5. Rollback only with proven data-compatible signed older APK and backup. Android can reject downgrades; avoid `adb install -r -d` without owner consent, and never promise that an APK downgrade preserves data.

## Node review versus LIVE

- My node can configure local identity and require two-level consent (APP + native Android dialog). The review bridge sends only schema/node/hashed installation seed/nonce/consent to the **fixed HTTPS** Aduana endpoint.
- `AWAITING_HUMAN` receipt proves only an intake result bound to a digest, not signed human approval, provisioning, authenticated heartbeat, Open World LIVE or remote visitor connectivity.
- Current public Aduana route has returned 404; `NO_DATA(public_reviewer_endpoint_live)`, `NO_DATA(visitor_to_android_E2E)` and `NO_DATA(five_independent_live_nodes)`.
- Personal Companion defaults: owner-local settings; neutral prompt; no public participation by default; five distinct owners each choose their own identity and do not exchange credentials.

## Release gate

**BLOCKED until:** physical Android gates ×2, external download full hash check, completion of source test suite, protected exact-head FIRMA+FIRMO; then GitHub Release new asset (~156MB), WEB `/get-the-app/` updated to actual URL, and public URL independently confirmed. Old 1.34MB artifact is NOT this app. Cloudflare Workers static assets cap 25MiB; do not upload 156MB there. Source PR alone ≠ published APK. Backend Aduana deployment requires its own protected migration and approval.

**No operational claim of public install or LIVE until real receipts.**
