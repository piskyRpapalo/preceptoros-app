# APP MVP · exact UI contract for Android and WEB · 2026-11-19

**Owner:** Codex GPT-6 APP/UX. This is an integration contract, not a second app or an installation certificate. Exact Git SHA is published with the PR and mirrored to private Mesa #49.

## Source and assets

Six existing tabs: Talk `#panel-conversacion`, Operations Data `#panel-cuaderno`, Lab `#panel-lab`, My node `#panel-ajustes`, Open World `#panel-modelos`, Settings `#panel-settings`.

Canonical owner-facing sources: `interface/app.html`, `interface/app.css`, `interface/app.js`, `interface/superbot_talk.js`, `interface/mvp_first_run.js`, `interface/sw.js`. Keep `interface/browser_mini_gate.js` and the existing `mvp-android/offline_mini.js` (deterministic browser router). The Android JNI/runtime is owned by the Android lane and must not be silently replaced with a static four-panel projection.

**Pinned PWA revisions:** `preceptoros-armazon-v234`; `/app.css?v=54`; `/app.js?v=56`; `/superbot_talk.js?v=3`; `/mvp_first_run.js?v=1`; canonical Open World crab body `/face/bubble/openworld_crab_body.js?v=1` (original SHA-256 `e332c81bdee87a90a3aa76e7e34dea32c5f493879b64c1f97104510a6e3404b0`). Route the new script through the existing `bin/preceptoros-pwa` static allowlist.

## First-run/storage contract

- **First-use marker**: `localStorage["preceptoros.app-first-run/1"] == "done"`, written only when the owner presses Finish introduction; reversible via Show three-step introduction again. Fresh profile shows the guide.
- **Owner-local draft**: `localStorage["preceptoros.node-public-template/1"] = JSON.stringify({schema:"preceptoros.node-public-template/1",name,description,prompt})`, written only on Keep these defaults. Name max 64 chars; description max 240; prompt max 1024. Schema-checked on reload; no secrets, network request or publish.
- **Neutral prompt**: "You are an experimental PreceptorOS companion. Answer clearly and briefly using only the capabilities available to you. Do not invent facts, tools, connections or actions. Explain uncertainty. Never disclose private information. Your owner must authorize any external action."
- **Suggested node ID**: explicit click generates `nodo.<six-digits>.<owner-name-slug>` with `crypto.getRandomValues`, fills `#node-identity-id` and an empty `#node-registration-name`; it does not save, assert uniqueness, sign, submit or overwrite an existing node ID.
- **Existing authorization**: `#node-identity-consent` and `#node-registration-consent` remain independent. The Android origin-bound `PreceptorAndroidJoin` bridge is not supplied by the APP shell. If absent, review stays blocked; a signed and fresh Aduana receipt is required before treating a request as accepted.
- **Lab entry**: `#lab-first-experiment` opens Operations Data → `#plan-escribir` and focuses `#plan-titulo`, with no automatic plan content or execution.
- **Agents**: compact line "Agents ● Not connected ▾" when no verified activity; plan references and synthetic examples are not live, so the dot stays red. The UI currently lacks a verified running-agent receipt bridge; do not fabricate green.

## Android/WEB integration gates owned by their lane

1. One APP package: preserve the six-tab shell and owner-local storage/origin on a real Android build; package with same app ID, versionCode and signing certificate constraints measured by device owner. Ensure browser first-run marker and draft survive restart/update without destructive migration.
2. Mini Orchestrator: verify bundled model asset/hash, JNI, a meaningful local reply, offline behavior and isolation from the founder's private rack. Do not equate deterministic router with trained LoRA.
3. Public page/download: `https://preceptoros.org/get-the-app/` must distribute **this six-tab APP**, not the old four-panel `bin/package_public_mini.py` output. Existing `test_public_mini_package.py` failures must be repaired in the Android/WEB lane, never skipped.
4. Admission: the Android bridge must be origin-bound and consent-gated; Aduana intake and LIVE heartbeat require actual deployed services, signed receipts and owner approval.
5. Physical evidence: clean Android install, TalkBack/speech Stop/no unsolicited audio, 360/420 viewport, offline/reopen/persistence, native inference, and a safe rollback path.

**NO_DATA:** public install verified, Android model inference quality on four phones, deployed Aduana API, signed admission, world LIVE, physical TalkBack. Private Beelink :8742 is a separate installation and must remain unchanged until exact-head gates, owner HITL and rollback.
