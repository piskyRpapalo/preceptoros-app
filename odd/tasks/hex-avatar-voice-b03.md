# HEX-AVATAR-VOICE-WEB-B-03 · Beelink local voice and authorization-state repair

**Date:** 2026-11-22 · **Owner:** Codex GPT-6 Web / Avatar-Acho · **Authority:** Soberano.
**Scope:** APP Talk at `127.0.0.1:8742`, existing avatar and existing local native reading API. Neither CineK nor TRAIN-02 is modified.

## What this PR changes

1. Reuse the **existing** `/api/voz/lectura` endpoint. Its `host-espeak-ng` engine now accepts an explicitly allowlisted `language: "es"` (or legacy `"en"`); every other language, extra key or malformed body fails before calling the engine. The Spanish WAV receipt preserves the exact SHA-256 of text and audio and separately measures `synthesis_wall_ms`. No mic, internet, shells, models, GPUs, keys or new backend routes.
2. Reuse `native_voice.js`. When the user **clicks Read** inside a genuine loopback APP origin, and the browser has **no verified local Spanish voice**, the reader falls back to the same-origin host synthesizer. A local Spanish browser voice takes priority. Other origins never get this fallback; no remote voice is selected. The reader verifies the host's language, engine, bytes and both content digests before attempting audio playback. Stop still aborts late requests.
3. Reuse `avatar_voice.js`. A new authorization denial from the **existing typed Talk status** takes priority over stale interrupted/muted/speaking UI, cancels pending local capture/reading and displays `awaiting_authorization` with `authority:none`. No permission is created by the avatar.
4. Service worker `v247` and script `avatar_voice.js?v=2` evict stale UI. Existing exact-version tests are updated, **not disabled**. `native_voice.js` remains explicitly **excluded** from the Android asset allowlist and the service-worker precache; it is fetched on demand.

## Ground truth at claim

| Layer | Status | Evidence and limits |
|---|---|---|
| LOCAL Beelink | MEASURED | `/tmp/hexelion-microfono.wav`: 3.000 s, 16000 Hz mono, 96044 B, nonzero samples, source UID 1000; not transcribed; physical audibility NO_DATA |
| APP DESPLEGADO | MEASURED | `8742/app.html`, avatar JS and image HTTP 200. Browser headless actual APP: 4 focusable 44px controls; mute/unmute/stop x2 states and text/ARIA/JSON match. |
| STT | NO_DATA(local_stt_pack_missing) | User's browser reports Spanish on-device speech pack missing. No download, remote service or Whisper inference. |
| TTS pre-PR | FAIL | `/api/voz` Piper `puede:false`, `binario:false`, `modelo:true`; existing `voz_lectura.py` supported only en. |
| TTS new branch | MEASURED(host synthesis only) | `espeak-ng` Spanish WAV 10 runs of one short fixed phrase; wall times [14.27,9.12,9.56,9.41,11.45,8.56,9.1,9.46,8.95,10.04] ms; p50 9.435 ms; **p95 nearest rank 14.27 ms** (10/10, small and non-generalizable). Last WAV 146854 B, 3329 ms, SHA256 c4b97c435c1213af88e02c669ec2c43ba98c03848b5de19c19d67403553b56ed. No physical playback. |
| Brain E0 | NO_DATA(authenticated_orchestrator_not_identified) | Ollama HTTP200: six tags, none `hexelion:latest`; no residents. Catalog alone is not a Hexelion identity or authorized channel. |
| Brain E1 | FAIL-CLOSED | Existing `hexelion_proxy.ask` tested against actual GET catalogs ×2 via restricted GET-only opener: `NO_DATA(station_model_unavailable)`, zero POST/inference. |
| End to end | NO_DATA(no_physical_witness_or_trusted_brain_turn) | No spoken user instruction → authenticated Onex brain → audible reply witnessed. No E4 action. |

Thermal Scout preflight: 86.4 °C at 20:11; before low-cost WAV 87.5 °C, unchanged after. No Whisper inference; no GPU reserved. Synthesizer process peak RSS 43900 KiB (not APP RAM delta).

## Verification gates

- Existing `tests/avatar_voice_cases.cjs` **43/43 ×2** synthetic. New test: denial after STOP retains same cause across state/ARIA/JSON and grants no authority.
- Existing `tests/native_voice_cases.cjs` **14/14 ×2** synthetic. New Spanish loopback-only host route, browser-local preference, non-loopback denial, and receipt verification.
- Existing `test_voz_lectura.py` **6/6 ×2** synthetic, including Spanish argv allowlist and invalid languages.
- Actual 8742 browser headless **not** a physical reader/mic test. Physical playback, hardware speaker and screen reader witness NO_DATA.
- CI and PR exact HEAD must be checked separately. No merge/deploy/service restart authorized by this PR.

## Concrete next step

1. Central + TRAIN-02 attest a real authenticated Onex Hexelion endpoint with model digest and policy binding; do not relabel a model or bypass S1/OS-fence.
2. Owner confirms audio output on the Beelink desktop and authorizes a deploy window **after CI and exact-head review**. The Python service must be restarted only with authorization for `voz_lectura.py` to take effect; no silent hot reload.
3. Owner presses **Read** in the real Talk, listens to the Spanish phrase, stops it, verifies text/ARIA/JSON and screen reader. It is not a model reply until E0+E1.
4. Resolve local STT via an approved on-device package or a thermally safe Whisper run; no remote fallback. Measure actual STT, model TTFT, TTS startup and E2E p50/p95 with human witnesses and enough valid samples. No E4 before E0–E3.

**Handoff to HTML owner H:** consume this receipt; do not modify the central HTML from this lane and never label host synthesis a true Hexelion conversation.
