# HEX-TRAIN02-WEB-A-07 · Pinned station binding

**Role:** Codex GPT-6 Web, TRAIN-02. **Authority:** Soberano. **State:** BRANCH_ONLY / TEST_CANDIDATE / NO_DEPLOY / GPU_HOLD. One feature, no Forja V4.

## Problem and evidence
APP Talk selects `private_hexelion` when its server owns `PRECEPTOROS_HEXELION_ENDPOINT`. `hexelion_proxy.py` then demanded a hard-coded `hexelion:latest` tag. ONEX Ollama 0.40.3 exposed six tags, including `gpt-oss:120b` digest `714d86958b6e870a9320e78126ac1ce3477727a1cd9bf7194b8ace0d84c62fd8` and `qwen3-coder:30b` digest `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`; `hexelion:latest` was absent, `/api/ps` empty. `GET /api/cerebro` shows a *different* Qwen3 4B local GGUF. **Neither tag nor GGUF selection authenticates the main orchestrator.**

## Minimal adaptation
The existing `hexelion_proxy` now allows a restricted host-startup model selection:
- `PRECEPTOROS_HEXELION_MODEL`: exactly `hexelion:latest` (legacy default), `gpt-oss:120b`, or `qwen3-coder:30b`.
- `PRECEPTOROS_HEXELION_MODEL_SHA256`: the Ollama model-manifest digest in lowercase hex. A nonlegacy selection without the pin fails closed **before any network request**; a mismatch fails **before** `/api/generate`.
- The selected model constant remains the same object already checked by `bin/preceptoros-pwa`; this change does **not** edit that file, currently owned by Claude's APP #416.
- The existing loopback endpoint requirement is retained. The response explicitly reports `CATALOG_MATCH_NOT_OWNER_AUTH` rather than claiming cryptographic host attestation, physical blob identity, S1 authority or E2E.

## Measurable checks and limitations
Synthetic transport tests: 8 negative/positive checks, twice, with fake responses and **zero** Ollama generation. Check no network before invalid model, no generate after digest mismatch, exact model echo, loopback-only, backward-compatible absent alias. A tag digest can be re-reported by a compromised runtime and is **not an OWNER signature**. Actual physical file SHA / ROCm / memory / lease / CineK exclusivity and real dialogue remain unverified.

## Next owner-specific gate (not executed here)
C + Soberano validate actual ONEX registry digest against disk blob and an independent approved `model_ref`/policy; verify unit environment and same-host loopback proxy; ensure thermal guard and exclusive 90,000,000,000-byte OS GPU fence; obtain B/Avatar ACK for output state projection. **Only after exact-head CI review and OWNER sign/restart can the host configure a candidate.** No alias recreation. No model promotion by code merge, no secrets, no bypass to public APP.

## Sources
Mesa privada #51 A-06 #7085162280, A-07 CLAIM #7085458713; LAB `meta_harness/tool_plan_quality.py`; APP `hexelion_proxy.py` original blob b6b6d63f791e902e52ed8d90969c048f6c4bccd7; direct Ollama `/api/tags`, `/api/ps`, `/api/show` metadata readback; CineK health false. **No formal proof of model identity or transcript E2E yet.**
