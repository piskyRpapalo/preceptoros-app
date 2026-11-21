# ONLINE3 · Talk: Local Mini vs private orchestrator (interface)

**State: PROPOSED · HITL.** Consumes the Android contract in `odd/tasks/online3-private-talk.md` (Codex, commit
`2e08b4ee`, not yet on main). Reaches a phone only inside a new OWNER APK signed by the Sovereign.

## What the person sees
- Signed v7 and public builds (no `PreceptorPrivateTalkNative`): nothing changes.
- OWNER APK with the bridge: the existing **Choose model** dialog gains one switch beside the Mini one,
  «Use private orchestrator (Hexelion)», and «Private address…» (Android system dialog; the address never enters the page).
  The dialog button reads **Model · Local Mini** or **Model · Private Hexelion**.
- Local Mini is the default every time the APP opens. Private is an explicit tap, reversible.
- Thread rows say who answered: `MINI-LOCAL` or `Hexelion · private orchestrator`. MEASURED only with
  model, time, sources and text; anything else is `NO_DATA(stage: cause)`.
- Network lost: `NO_DATA(connection: …)`, the words go back into the box, Local Mini still answers on the phone.
  When the network returns, the next private turn is the proof; a saved address alone is never shown as connected.

## Built
- `interface/browser_mini_gate.js` (+ `?v=3`, shell cache v238): the selector, no fetch, no storage, no address.
- `tests/app_private_talk_route.browser.cjs`: real Chromium, real `app.html` under `https://preceptoros.mvp.local`,
  bridge doubles; 360/412 and 1280 px, keyboard (Space), 44 px, acho:event parity, no request off-origin.
- `test_private_talk_route.py`: pure contract for CI.

## Found while building
- `offline_mini.js` registers a capture listener on the form first; a second capture listener on the form never
  runs. The selector listens in the document's capture phase instead (sabotage: form-level → red).
- «Agents · not connected» on the v7 phones is the old plan-references label; main already says
  «Agents · plan unavailable». It is not a network reading.

## Not measured
- Physical S110/Tank3 with the OWNER APK: `NO_DATA(owner_apk_unsigned)`.
- Talk over LTE through Tailscale: `NO_DATA(owner_apk_unsigned)`.
