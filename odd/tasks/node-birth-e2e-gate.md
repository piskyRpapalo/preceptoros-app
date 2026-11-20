# APP NODE-BIRTH · source-only E2E evidence gate R2

Date: 2026-11-20. Orchestrator: Codex GPT-6 Web A. Builder: Junie.
Branch: `codex/node-birth-e2e-a-20261120`. Base APP main: `323311a409d199b45f22d77e5c30cbfb4223ab3a`.

## Purpose and authority

A node is not LIVE merely because software returns `VERIFIED`, a receipt hash matches, a model is installed, or two synthetic turns exist. The pure Python stdlib `node_birth_e2e_gate.py` collects **twelve structural/claimed** stages; it deliberately returns `live=false` and `NO_DATA(trusted_witness_not_connected)` for authenticity, signed cédula, heartbeat and public observer until independently verified services are wired. It does **not** launch anything, mint human consent, create real nodes, visit URLs, or publish a service.

This is a **source-level review aid**, not an actual production gate or an admission API. It does not replace `nodo_app.autenticidad` or the signed Aduana receipt, and should not be called proof of node birth.

## Stages

| Stage | What is inspected | Boundary |
|---|---|---|
| `source` | Identity schema and node identifier | Format only, not who issued it |
| `owner_consent` | Supplied boolean and timestamp | Caller assertion, not independently signed human gesture |
| `preliminary` | Android wire request fields and byte limit | No POST or server acknowledgement |
| `response` | Self-consistent receipt digest | Digest does **not** prove issuer, nonce, authorization or delivery |
| `issuer_auth` | Supplied issuer data | **NO_DATA** until independent cryptographic verifier |
| `cedula` | Structural digest | **NO_DATA** until SSHSIG verified against trusted allowed_signers |
| `provision` | Supplied local provisioning result | No actual disk mutation or accepted device |
| `inference` | Supplied inference witness shape | No model process independently observed by this module |
| `lab_rag` | Supplied digest/reference | No per-hardware retrieval or freshness established |
| `cross_agent` | Supplied distinct turn names | Not two independently proven agents |
| `heartbeat` | Supplied heartbeat shape | **NO_DATA** until independently authenticated fresh observer |
| `public_live` | Supplied public claim | **NO_DATA** until network readback + identity binding |

The `observed_at` field is a local report timestamp, not a signed freshness witness. Time injected through the context is not authoritative; `now` is only a deterministic unit-test input.

## Checks and adversarial coverage

Directed suite `test_node_birth_e2e_gate.py`: **88 cases**. Combined targeted tests `test_node_birth_e2e_gate tests.test_node_building test_nodo_app`: **126 cases ×2**, with 1 skip each run. Canonical `./bin/pruebas --rapido`, after adding the new module to the suite census: **2478/2478 ×2**, 195 suites, 6 runners.

The key sabotage is a wholly self-consistent synthetic context that marks issuer, cédula, heartbeat and public observer as VERIFIED. The gate **must return `live=false`** with explicit untrusted-witness causes. A missing field, forged signature label, aged/replayed claim, invalid wire shape, unsupported model or empty public node list must not become LIVE. Tests are synthetic; no public admission was attempted.

## Real E2E still pending

- APP invitation: native consent gesture → HTTPS preliminary POST → actual server receipt `AWAITING_HUMAN`, separately judged.
- Sovereign-approved signing against trusted `allowed_signers`, preserving original SSHSIG/cédula contract.
- Provision genuine identity on one hardware target without manufacturing grant, verify installed model **and real inference**.
- LAB/RAG per-hardware query with source/digest/freshness evidence; two agent processes exchange actual turns.
- Independently authenticated 120s-fresh node heartbeat and matching public `/api/v1/latidos` readback, followed by two separate browser views and Acho visual/audio/machine parity.

Current live public deployment endpoint for native preliminary requests returns HTTP 404 in independent invalid-schema POST/read probes. APP local `/api/nodo/identity` also returned HTTP 404 in current instance. `/app/` is a WEB route and is not a source of authenticated node admission.

**Limits:** `NO_DATA(real_owner_signature)`, `NO_DATA(public_preliminary_intake)`, `NO_DATA(per_hardware_RAG)`, `NO_DATA(authenticated_public_node_LIVE)`. No new UI, APK, WEB, D1, grants or cloud deployment; exact-head HITL needed for integration.
