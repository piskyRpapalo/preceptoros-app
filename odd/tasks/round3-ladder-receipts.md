# Round 3 · My node ladder consumes the backend's lifecycle receipts

**State: PROPOSED · HITL.** Interface only; builds on #398. No API built here: `GET /api/nodo/estado` belongs to Codex
(HTTP 404 on Beelink 8742, 2026-11-21).

## What changes for the owner
- Every stage says **who acts**: `Next (you)`, `Waiting for Aduana`, `Needs a human SSH signature`, or
  `Blocked (<cause>)`. The summary starts with the last completed stage: `Done: … Stage N of 10 · … · STATE (cause). …`
  Same sentence for eye (teaser), ear (`role=status`) and machine (`data-state/acho/cause`).
- Reads `preceptoros.node-lifecycle/1` and updates on transitions: re-read when the owner opens My node, after
  identity actions, and every 15 s while My node is in view.
- Trust rules (pure, tested): a stage missing from the answer → `NO_DATA(stage_missing_in_lifecycle)`; an answer for
  another node → nothing advances (`lifecycle_node_mismatch`); unknown state words → `stage_state_unrecognized`;
  no skips. LIVE needs signature, approval, heartbeat and live all MEASURED in order.
- REFUSED/EXPIRED: «Read the cause, then send a new request». REVOKED: the ladder returns to Request admission
  (`node_revoked`). Revoke is an action that stays available, never ticked off.
- A recorded server `request` reading survives a reload (the in-page receipt does not).

## Contract delta for Codex (optional, additive)
`stages.request` `{state, cause}` from the stored Aduana receipt, so a reload keeps stage 3. For the building gate:
`stages.building.cause` should name the first missing requirement (`node_not_admitted`, `owner_identity_unverified`,
`function_not_tested`, `policy_not_authorized`, `receipt_unverifiable`).

## Tests
- `tests/node_lifecycle_cases.cjs` 9/9 — now actually run by `test_node_registration.py` (#398 claimed it was; only
  static checks had landed).
- `tests/app_node_lifecycle.browser.cjs` 2/2: (1) real APP server, identity → consent → request → receipt, 390/420/780,
  keyboard, intake POST SYNTHETIC; (2) TEST DOUBLE lifecycle answers: signature pending → Aduana → partial answer →
  foreign node → refusal.
- Sabotage 5/5 red: node mismatch accepted, skips allowed, revoke ticked, blocked hidden, server request ignored.

## Not measured
Real `/api/nodo/estado` (`NO_DATA(node_lifecycle_api_missing)`); the Sovereign's real request (`owner_gesture_pending`);
physical Android (v7 has no APP server).
