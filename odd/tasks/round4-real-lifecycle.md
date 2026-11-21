# Round 4 · My node against Codex's real lifecycle API (#402) and Create building

**State: PROPOSED · HITL.** Interface + tests only. No API, ladder or panel added.

## Verified against the real service
- Beelink 8742 (2026-11-21): `GET /api/nodo/estado` HTTP 200, `preceptoros.node-lifecycle/1`, `node: null`, all ten
  stages NO_DATA. The shipped page shows exactly that: Stage 1 · NO_DATA(identidad_no_provisionada) · Next (you).
  `tests/app_node_lifecycle_live.browser.cjs` (read-only, aborts every non-GET /api/ call) ×2 at 390/420/780.
- Codex's `node_lifecycle.read` outputs (AWAITING_HUMAN, APPROVED, REJECTED, REVOKED, no intake) fed to the ladder:
  `test_node_lifecycle_ui_contract.py`. Real server + Codex `record_intake` store: stage 3 survives a reload.

## Defects found and fixed
1. A REJECTED/EXPIRED reading after an unverified signature stage left the owner on «Needs a human SSH signature»
   (signing a refused request). Now a refusal/expiry anywhere becomes the current, blocking stage. Nothing ticks.
2. With the real API, a server `request: NO_DATA` overrode the page's verified Aduana receipt. The server now wins
   only when it holds evidence (PENDING/MEASURED/…), so a failed `lifecycle_recorded` does not erase the receipt.
3. «Declare assigned building» enabled on consent alone. Now it also needs the lifecycle: SSH signature MEASURED,
   approval MEASURED, not revoked, and `stages.building` PENDING/MEASURED; otherwise
   `NO_DATA(<first missing requirement>). Next: …` (stages.building.cause explains function/policy), same text for
   eye/ear and `data-state/acho/cause`.

## Gaps for Codex (contract, not built here)
- `heartbeat` is never MEASURED in #402 (`projection_omits_exact_heartbeat_receipt`), so the ladder can never reach
  LIVE even when Aduana projects it. Needs the exact heartbeat receipt.
- `ai` and `building` have no source yet. Ask: `building` PENDING with a cause such as
  `function_tested_policy_accepted` when the function is installed+tested and the policy accepted.
- `declarar_edificio` accepts only `ASSIGNED_NODE = "primer-ancla"`, which the lifecycle's `nodo.N.x` pattern never
  projects: no lifecycle node can declare a building today.

## Not measured
Physical OpenWorld (production CSP still `frame-ancestors 'self' http://127.0.0.1:8742 http://localhost:8742`);
the Sovereign's real request (`owner_gesture_pending`).
