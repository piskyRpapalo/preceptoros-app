# APP-TALK-LOCAL-01 · public local model turns

## Goal

Make the existing Talk surface use the locally selected `base` or `afinado` GGUF in the public APP, while preserving the private Hexelion station door unchanged.

## Configuration contract (before implementation)

There is no explicit public/private profile in the current APP. The existing server-side `PRECEPTOROS_HEXELION_ENDPOINT` is the configuration signal for the private station. The server will expose a read-only `talk_mode` in the existing `GET /api/cerebro` response:

- `local_gguf` when that endpoint variable is absent or empty. The public Talk posts only to the existing `/api/charla` local inference route.
- `private_hexelion` when the endpoint variable is configured. Talk retains the existing `/api/hexelion/chat` behavior. A configured but unavailable or invalid endpoint must fail closed; it must not fall back to local mode.

The browser cannot set or override `talk_mode`, provide a model path, or select a private endpoint. If the mode is missing or unknown, Talk sends no question and reports `NO_DATA(talk_mode_unavailable)`.

## Local turn behavior

`POST /api/charla` will resolve the actual turn model with `_afinado.elegir`, use `conversacion.motor_llama` only for that resolved path, and return the effective local model id/name, measured duration and existing output receipt id. It will not claim citations, tool use, grants, agent activity or `MEASURED`. A selected tuned model whose registry/path/digest is invalid is rejected; it is not silently replaced by the base for that turn. A base preference remains usable independently.

Before opening the user's SQLite for writes, the handler must use the existing read-only memory status snapshot and reject missing, corrupt, unknown, or uninitialized files without changing them. Consent remains governed by the existing per-turn capture controls.

## UI and authority boundary

The existing APP Talk form routes by the server-reported mode. Local replies are rendered as plain local-model replies; the screen reader status and Acho indicate an answer only after a valid backend reply. No citations or tool results are fabricated. The private route and action handling remain byte-for-byte behaviorally separate. Local `/api/charla` never dispatches tools or grants.

## Verification

Synthetic fixtures may test routing and validation but must not be reported as inference. Required checks cover base/afinado selection, invalid digest/registry, absent model/runtime, preservation of unknown SQLite and consent, private-route preservation, and no synthetic `MEASURED` claim. Served JS cache/version references must remain aligned.

## Known limit

This slice supports the existing registered choices (`base` and one verified `afinado`). It does not add arbitrary GGUF import or a multi-model catalog.
