# Tank 3 · MINI-LOCAL offline (source & reproducibility)

**Artifact:** `org.preceptoros.app` `versionCode=4`, `versionName=0.2.0-tank3-mini`.

This is the **personal collaborator APK**, not the rack/server control APP.
It replaces an already installed package only when the installer accepts the
same application ID and signing certificate. No uninstall, no data clear.

## What works and what is not yet proven

- Offline four-zone shell, Talk, Documents, Lab, My node, Back to MVP.
- Bounded deterministic router: navigate / help / plan editor / status.
- Optional real GGUF inference through pinned `llama.cpp` ARM64 JNI. The APK
  does **not** request the Android INTERNET permission, and the inference
  bridge does not invoke any remote service or tool.
- One on-device generative turn observed on Tank 3 (model output paraphrased
  the user; not a successful reasoning-quality benchmark). This proves a
  native inference path, **not** a competent autonomous mini-orchestrator.
- **NO_DATA**: n>=2 timed inference receipts, quality thresholds, voice,
  local persistent execution journal, remote node admission, rack execution.
- **DO NOT** interpret `DRAFT_ONLY` as an action receipt or `NO_DATA` as a
  network failure if the APK intentionally has no backend.

## Model & native provenance (no binary/source duplication)

- Source: installed local checkout `/home/pisky/llama-fresco-20261011`
  at commit `f2cc7282ce0042641df55e0e563b75e824e2b647` (llama.cpp, MIT);
  the build script refuses a different revision.
- Model: locally verified `SmolLM2-135M-Instruct` base exported GGUF Q4_K_M
  from p0x LoRA experiments (upstream HuggingFaceTB, Apache-2.0). This
  experiment uses the **base** GGUF, NOT the LoRA-adapted checkpoint.
- Input model SHA-256:
  `ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747`
  (101 MB). The Android app hashes the entire model before loading.
- Native `libmini_llama.so` built on Beelink from NDK r27d for
  `arm64-v8a` and Android API 28. Reproducible from pinned checkout, not
  a stored repository binary.
- **No GGUF, keystore, passwords, or NDK artifacts committed to GitHub.**
  Gradle copies the model only when given an explicit `offlineMiniModel`
  local property. The release APK is distributed only through HITL.

## Repeat build (Beelink)

```bash
export ANDROID_HOME=/home/pisky/android-sdk
export ANDROID_SDK_ROOT=/home/pisky/android-sdk
export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.3.13750724
export ANDROID_CMAKE=$ANDROID_HOME/cmake/3.22.1/bin/cmake
export LLAMA_CPP_SRC=/home/pisky/llama-fresco-20261011
./mvp-android/native-mini/build-android.sh
cd mvp-android
./gradlew :app:assembleRelease \
  -PmvpAppId=org.preceptoros.app -PmvpVersionCode=4 \
  -PofflineMiniModel=/home/pisky/p0x/preceptor-lora/salida/guia-web-20261101/base-web-q4km.gguf \
  --offline --console=plain
```

Inspect with `aapt2 dump badging`, `apksigner verify --print-certs`,
`aapt2 dump permissions`, and SHA-256 of `assets/offline-mini.gguf`.
The signing key is the existing owner-controlled secret outside Git.

**STOP if** app ID/certificate differs, release requests INTERNET,
the model digest differs, or the native library is missing. Preserve the
owner's APK, private settings, and `403 local_origin_required`.
Never grant rack authority to the personal app.

## Ground-truth smoke probes

1. Check versionCode and `firstInstallTime` by `adb -s <SERIAL> shell
   dumpsys package org.preceptoros.app` before/after `adb install -r`.
2. Open Talk; `hola` should identify **deterministic router**.
3. Ask a free question. Require actual on-device model text and a label
   **on-device model output**, NOT `NO_DATA`, before declaring inferencing.
4. Repeat with at least two different prompts and record measured latency
   and factual quality as separate axes. The first free response was a
   paraphrase, so quality is not demonstrated.
5. In airplane mode, repeat with consent and verify no change in behavior.
   Do not toggle the owner's radios without explicit permission.
6. Do not interfere with Termux/Tailscale/SSH. Restoring the private
   rack tunnel is a **separate** workstream. `127.0.0.1` on phone ≠ rack.

## Audit at 2026-11-17 22:24Z

`adb install -r` returned Success for package versionCode 4. Activity
`org.preceptoros.app/org.preceptoros.mvp.MainActivity` opened.
The original `firstInstallTime` (2026-11-14 22:49:17) remained unchanged.
APK SHA-256: `c21db4993adc201b4b989d4a45d818f15153e894e9e20be33fc0e8f3e4d947ed`.
One real generated turn was observed on the display; response:
`"Escriba una frase sobre un cangrejo."` to a Spanish request asking for
a crab sentence. This is low-quality generation, not a verified answer.
No timed multi-run benchmark yet; second probe aborted when Termux became
foreground, rather than competing with a tunnel operator.
