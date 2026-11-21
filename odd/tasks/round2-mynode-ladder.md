# Round 2 · My node: one ladder from the backend's own readings

**State: PROPOSED · HITL.** Interface only. No signing, admission, heartbeat or Aduana change.

## What the owner sees
The existing «Getting started» list in My node becomes ten stages, read from the APP server, never inferred:

1. Prepare node identity · 2. Owner consent · 3. Request admission · 4. Owner signature (SSH) · 5. Admission approved ·
6. Heartbeat verified · 7. LIVE in Open World · 8. Local AI on the public channel · 9. Functional building published · 10. Revoke

- The folded summary always says `Stage N of 10 · <stage> · <STATE> (<cause>). Next: <one action>`. The same sentence
  goes to the `role=status` line (`#mvp-node-state`) and to `data-state/acho/cause`, once per change.
- No skips: a later reading never counts while an earlier stage is open (`earlier_stage_unverified`).
  REFUSED, EXPIRED and REVOKED stop the ladder where they happened.
- A pending Aduana receipt closes stage 3 and says «Not a live node». Nothing marks LIVE by itself.

## Beelink can now send the request
`node_registration.js` only accepted the Android bridge, so on Beelink «Sign deployment · request review» always failed
with `native_preliminary_request_not_available`. Codex's intake (`odd/tasks/online3-pwa-intake.md`) asked for a loopback
adapter: it is in `interface/node_building.js` (`PreceptorNodeLoopback`), which the public APK and public Mini never ship
(the public profile forbids `/api/nodo/identity`). One 32-hex nonce per consented attempt, reused only to retry it;
the purpose stays local; the receipt is verified by the existing `requestDeploymentReview`.

## Minimal contract asked of Codex (read-only, loopback owner only)
`GET /api/nodo/estado` → `{"schema":"preceptoros.node-lifecycle/1","node":"…","stages":{"signature":{…},"approval":{…},
"heartbeat":{…},"live":{…},"ai":{…},"building":{…},"revoke":{…}}}`, each `{"state":"MEASURED|PENDING|REFUSED|EXPIRED|REVOKED|NO_DATA","cause":"[a-z0-9_]{1,96}"}`
from the server's own evidence (SSHSIG, D1 admission, heartbeat, world-state, measured public turn, building receipt).
Until it exists, stages 4–10 show `NO_DATA(node_lifecycle_api_missing)`: measured today on Beelink 8742 as HTTP 404.

## Tests
- `tests/node_lifecycle_cases.cjs` (pure, in `test_node_registration.py`): adapter only on plain-http loopback; exact body;
  nonce reuse; receipt never approval/LIVE; no skips; refusal stops; untrusted words rejected.
- `tests/app_node_lifecycle.browser.cjs`: real Chromium on the real APP server with a temporary HOME, 390/420/780 px,
  keyboard, 44 px, no horizontal scroll. The intake POST is answered by the test (SYNTHETIC): the server forwards it to
  production Aduana, and a real request needs a person's consent.
- Sabotage (each turns a test red): request not counted, skips allowed, adapter on any origin, no refresh on identity lock.

## Not measured
A real consented request from the Beelink APP to Aduana: `NO_DATA(owner_gesture_pending)`; physical Android: v7 has no
APP server, so the ladder says `app_server_not_on_this_device`.
