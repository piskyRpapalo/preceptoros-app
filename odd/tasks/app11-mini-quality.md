# APP-1.1-MINI-OFFLINE/JNI-QUALITY — Replace greedy argmax with bounded sampling

**Date:** 2026-11-20
**Voice:** Junie (native MINI quality builder)
**Status:** Complete — local commit, pending HITL review

## Problem

Tank3 (signed v7, offline, wifi=0/data=0) produced two quality failures:
1. **Repetitive text** — free Spanish prompt (poem) generated repeated output.
2. **Fake server claim** — English question about "lemons" generated a false claim of running a preceptorOS server.

**Root cause:** `mvp-android/native-mini/mini_jni.cpp` used pure greedy argmax (lines 63-65 original) for every token in the 72-step generation loop. No temperature, no top-k, no repetition penalty, no loop detection.

## Changes

### `mvp-android/native-mini/mini_jni.cpp`
- **Removed** greedy argmax scan (`for (llama_token t=1; t<count; ++t) if (logits[t] > logits[pick]) pick=t`).
- **Added** `sample_token()` — temperature-scaled softmax over top-k candidates with deterministic LCG random selection.
- **Added** `has_loop()` — bounded n-gram repetition detector on the last N generated tokens.
- **Added** `gen_tokens` vector tracking generated tokens for loop detection.
- **Parameters:** temperature=0.8, top_k=40, loop_window=12, loop_min_len=3, loop_min_count=2.
- **Loop detection** emits `[NO_DATA(mini_loop_detected)]` suffix and breaks generation.
- System prompt already contained capability refusal text (unchanged).

### `mvp-android/native-mini/mini_quality_cases.cpp` (new)
- 11 standalone C++ unit tests for `has_loop()` and `sample_token()` helpers.
- Compiles with `g++ -std=c++17`, no model or JNI required.
- Tests: loop detection (positive/negative), sampling within top-k, temperature diversity, non-argmax behavior.

### `test_android_mini_quality.py` (new)
- 11 Python unittests: 8 source-level checks + 3 binary compilation/execution checks.
- Validates: no argmax pattern, sample_token present, has_loop present, temperature/top_k constants, no forbidden calls, system prompt refusal, token tracking, sabotage detection.

## Verification

| Test | Result | Date | Machine |
|------|--------|------|---------|
| Native cases (g++ -std=c++17) | 11/11 pass | 2026-11-20 | local x86_64 |
| Python test run 1 (all 11) | 11/11 OK | 2026-11-20 | local x86_64 |
| Python test run 2 (8+3 split) | 11/11 OK | 2026-11-20 | local x86_64 |

**NOT measured (NO_DATA with cause):**
- Physical Tank3 re-test: NO_DATA(device_not_available) — Tank3 offline, no re-test possible in this session.
- Android NDK cross-compile: NO_DATA(NDK_not_configured) — ANDROID_NDK_HOME not set in this worktree.
- Live GGUF inference: NO_DATA(model_not_loaded) — no GGUF asset in worktree for runtime test.

## Limitations

- Sampling uses a simple LCG (seed=42) — deterministic but not cryptographically random. Adequate for breaking repetition patterns; not a replacement for proper entropy.
- `has_loop()` checks only the last `window` tokens; longer-period loops may slip through.
- No repetition penalty on logits (llama.cpp `penalties` sampler not used) — kept change minimal.
- Quality improvement is probabilistic; Tank3 re-test required for conformant claim.

## Files Modified
- `mvp-android/native-mini/mini_jni.cpp` — sampling + anti-loop
- `mvp-android/native-mini/mini_quality_cases.cpp` — new native tests
- `test_android_mini_quality.py` — new Python tests
- `odd/tasks/app11-mini-quality.md` — this document

## Next
- Owner re-tests on Tank3 with rebuilt `libmini_llama.so`.
- HITL PR review at exact head SHA.
- NO merge without FIRMO.
