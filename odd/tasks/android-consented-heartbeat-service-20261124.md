# Android · consented node heartbeat service

## Purpose

Keep an already admitted Android node's existing `preceptoros.latido/1` receipt fresh while the owner explicitly runs a visible native foreground service. Preserve the current one-shot sender and fixed Aduana endpoint. A receipt remains `RECEIVED`; only the independent public observer can establish `LIVE`.

## Boundaries

- The service starts only from the verified first-party APP page after Android's document picker and a native consent dialog.
- The owner may separately opt into resuming after device restart. This defaults off. A notification provides a direct revoke action that stops sends, clears consent and removes the encrypted credential.
- Store the node credential only as AES-GCM ciphertext protected by an Android Keystore key. Never expose it to JavaScript, logs, notifications, or backup. Keep sequence numbers in the existing per-node durable counter and reserve before each request.
- Send only the existing four-field canonical heartbeat to `https://api.preceptoros.org/api/v1/latidos`, every 120 seconds while the service runs. Do not add a server route or claim public LIVE.
- No work starts without a valid saved credential and active consent. Network failure leaves the service visible and retries on the next interval; revocation always wins.
- A running service can recover after process death (`START_STICKY`). Boot resume is a separate owner opt-in. No APP install, signing, human admission, deployment, or real E2E is included in this source change.

## Implementation choice

Use an Android foreground service. WorkManager's periodic work cannot keep a node fresh under the existing 300-second liveness window when its minimum periodic interval is longer. The service uses `specialUse`, because this ongoing owner-controlled presence task has no narrower foreground-service type. Android requires an explicit type for modern targets and reviews the free-form subtype for Play distribution; this repository change does not claim Play policy approval.

## Verification

Test the pure interval and consent policy, Java/JS bridge behavior, Android manifest/service compilation, and repository gate. Keep emulator/device network E2E and public `LIVE` readback as `NO_DATA` until an authorized test owner runs them.
